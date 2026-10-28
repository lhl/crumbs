"""Selective extraction pass (EXT v1): long-form reads only where evidence
is likely — food-category photos and photos whose triage saw evidence types.

Output per photo (stored parsed + raw): full visible-text transcription,
dish candidates (seen vs read), place-name candidates with where the name
appeared, and explicit cannot-determine. Place names are then matched
against registry places near the photo (name similarity + <=500 m); a match
creates a `signage-text` PlaceCandidate for the photo's visit — the first
evidence kind that can promote a candidate beyond GPS proximity, though it
still does not confirm anything by itself.
"""

import base64
import json
import urllib.request
from difflib import SequenceMatcher

from . import config
from .classify import MODEL
from .places import haversine_m

CHECKPOINT = "gguf-q4_k_m+mmproj"
ALGO_MATCH = "extract-v1(signage-match)"

SCHEMA = {
    "type": "object",
    "properties": {
        "visible_text": {"type": "string"},
        "dish_candidates": {"type": "array", "items": {
            "type": "object",
            "properties": {"name": {"type": "string"},
                           "basis": {"type": "string", "enum": ["seen", "read_on_menu", "read_on_receipt"]}},
            "required": ["name", "basis"]}},
        "place_name_candidates": {"type": "array", "items": {
            "type": "object",
            "properties": {"name": {"type": "string"},
                           "basis": {"type": "string", "enum": ["signage", "menu", "receipt", "other_text"]}},
            "required": ["name", "basis"]}},
        "cannot_determine": {"type": "boolean"},
    },
    "required": ["visible_text", "dish_candidates", "place_name_candidates", "cannot_determine"],
}

PROMPT = (
    "Extract evidence from this photo for a food/travel history. JSON only, matching the schema. "
    "visible_text: transcribe ALL legible text exactly (menus, signs, receipts, labels), preserving "
    "the original language; empty string if none. dish_candidates: dishes you can see plated or read "
    "named on a menu/receipt, with basis. place_name_candidates: business/place names that appear as "
    "TEXT in the image (signage, menu header, receipt header) with basis — never guess a place from "
    "what the food looks like. cannot_determine: true when the image holds no usable evidence."
)

EVIDENCE_EVIDENCE = {"menu", "receipt", "sign", "storefront", "dish", "document"}


def extraction_targets(conn):
    rows = conn.execute(
        """SELECT DISTINCT m.id, m.content_hash, m.gps_lat, m.gps_lon FROM media_items m
           JOIN classifications c ON c.media_id = m.id AND c.model = ?
           LEFT JOIN extractions e ON e.media_id = m.id AND e.model = ? AND e.checkpoint = ?
           WHERE e.id IS NULL ORDER BY m.id""",
        (MODEL, MODEL, CHECKPOINT),
    ).fetchall()
    out = []
    for r in rows:
        (lj,) = conn.execute(
            "SELECT labels_json FROM classifications WHERE media_id = ? AND model = ? ORDER BY id DESC LIMIT 1",
            (r["id"], MODEL),
        ).fetchone()
        labels = json.loads(lj)
        ev = set(labels.get("evidence_types", []))
        if labels.get("category") == "food" or ev & EVIDENCE_EVIDENCE:
            out.append(r)
    return out


def extract_one(image_path) -> dict:
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    body = {
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": PROMPT},
        ]}],
        "max_tokens": 1100, "temperature": 0.8, "top_p": 0.95, "top_k": 64,
        "chat_template_kwargs": {"reasoning_effort": "none"},
        "response_format": {"type": "json_schema", "schema": SCHEMA},
    }
    req = urllib.request.Request(
        f"{config.GLIMMER_URL}/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"},
    )
    resp = json.load(urllib.request.urlopen(req, timeout=900))
    content = resp["choices"][0]["message"]["content"]
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON in extraction output: {content[:120]!r}")
    return {"parsed": json.loads(content[start:end + 1]), "content": content, "timings": resp.get("timings", {})}


def _name_sim(a: str, b: str) -> float:
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.9
    return SequenceMatcher(None, a, b).ratio()


def match_place_names(conn) -> dict:
    """Promote candidates: extraction place-names vs registry places near the photo."""
    rows = conn.execute(
        """SELECT e.media_id, e.data_json, m.gps_lat, m.gps_lon, vm.visit_id
           FROM extractions e JOIN media_items m ON m.id = e.media_id
           LEFT JOIN visit_media vm ON vm.media_id = m.id
           WHERE e.model = ? AND e.checkpoint = ? AND m.gps_lat IS NOT NULL""",
        (MODEL, CHECKPOINT),
    ).fetchall()
    places = conn.execute("SELECT id, name, lat, lon FROM places").fetchall()
    made = 0
    for r in rows:
        if r["visit_id"] is None:
            continue
        names = [c["name"] for c in json.loads(r["data_json"]).get("place_name_candidates", [])]
        for name in names:
            best, best_sim, best_d = None, 0.0, None
            for p in places:
                d = haversine_m(r["gps_lat"], r["gps_lon"], p["lat"], p["lon"])
                if d > 500:
                    continue
                s = _name_sim(name, p["name"])
                if s > best_sim:
                    best, best_sim, best_d = p, s, d
            if best is not None and best_sim >= 0.75:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO visit_place_candidates (visit_id, place_id, distance_m, evidence, score, created_by) "
                    "VALUES (?, ?, ?, 'signage-text', ?, ?)",
                    (r["visit_id"], best["id"], round(best_d, 1), round(best_sim, 3), ALGO_MATCH),
                )
                made += cur.rowcount
    conn.commit()
    return {"signage_matched_candidates": made}


def extract_all(conn) -> dict:
    targets = extraction_targets(conn)
    done = failed = 0
    for r in targets:
        try:
            result = extract_one(config.ANALYSIS_DIR / f"{r['content_hash']}.jpg")
        except Exception as e:
            failed += 1
            print(f"media {r['id']} failed: {type(e).__name__}: {e}", flush=True)
            continue
        conn.execute(
            "INSERT INTO extractions (media_id, model, checkpoint, data_json, raw_text) VALUES (?, ?, ?, ?, ?)",
            (r["id"], MODEL, CHECKPOINT, json.dumps(result["parsed"], ensure_ascii=False), result["content"]),
        )
        done += 1
        if done % 5 == 0:
            conn.commit()
            print(f"extracted {done}/{len(targets)}", flush=True)
    conn.commit()
    matched = match_place_names(conn)
    return {"extracted": done, "failed": failed, "targets": len(targets), **matched}
