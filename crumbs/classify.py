"""Glimmer classification/extraction stage: one structured read per photo.

Talks to a local OpenAI-compatible server (GLIMMER_URL) only. The prompt asks for a
closed category set plus evidence typing and visible text, with explicit
abstention ("unknown" / empty candidates) — per PLAN, an unknown is a valid
result and a confident guess is a defect. Responses are stored raw alongside
the parsed labels so every inference stays auditable and re-parseable.
"""

import base64
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config

MODEL = "muse-glimmer-30b"
CHECKPOINT = config.GLIMMER_CHECKPOINT

# Triage read (System-1 shape): deliberately small output. Transcription and
# dish/place candidate extraction are a separate selective pass over evidence
# photos (PLAN stage 3), not part of this per-photo read — long generations
# are what makes this stage expensive on local hardware.
SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": ["sightseeing", "trip", "personal", "food", "unknown"]},
        "evidence_types": {
            "type": "array",
            "items": {"type": "string", "enum": ["dish", "menu", "receipt", "sign", "storefront",
                                                 "interior", "lodging", "landmark", "people",
                                                 "nature", "document", "other"]},
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["category", "evidence_types", "confidence"],
}

PROMPT = (
    "You are cataloguing one photo from a personal travel/food history. "
    "Reply with JSON only, matching the schema. Rules: category is the single best fit "
    "(sightseeing = landmark/viewpoint/tourist scene; trip = travel context like transit, hotel, "
    "street abroad; personal = people/everyday life at home; food = dish, meal, menu, receipt, "
    "restaurant food context; unknown = none fits). evidence_types lists what is visibly present. "
    "Leave the list empty rather than guessing."
)


EVIDENCE_ENUM = ["dish", "menu", "receipt", "sign", "storefront", "interior",
                 "lodging", "landmark", "people", "nature", "document", "other"]
_EVIDENCE_HINTS = [
    ("menu", "menu"), ("receipt", "receipt"), ("sign", "sign"), ("storefront", "storefront"),
    ("shop front", "storefront"), ("interior", "interior"), ("indoor", "interior"),
    ("hotel", "lodging"), ("lodging", "lodging"), ("room", "lodging"),
    ("landmark", "landmark"), ("temple", "landmark"), ("shrine", "landmark"), ("castle", "landmark"),
    ("people", "people"), ("person", "people"), ("portrait", "people"), ("selfie", "people"),
    ("nature", "nature"), ("landscape", "nature"), ("mountain", "nature"), ("beach", "nature"),
    ("document", "document"), ("ticket", "document"), ("dish", "dish"), ("food", "dish"),
    ("meal", "dish"), ("plate", "dish"),
]


def normalize_labels(parsed: dict) -> dict:
    """The server's JSON-schema mode does not constrain Glimmer's free-text
    evidence labels; map them onto the closed enum and keep the originals."""
    out = dict(parsed)
    if out.get("category") not in ("sightseeing", "trip", "personal", "food", "unknown"):
        out["category_raw"] = out.get("category")
        out["category"] = "unknown"  # closed set; invented labels (e.g. 'sighting') abstain
    raw_types = parsed.get("evidence_types", [])
    mapped = []
    for item in raw_types:
        low = str(item).lower()
        hit = next((enum for hint, enum in _EVIDENCE_HINTS if hint in low), "other")
        if hit not in mapped:
            mapped.append(hit)
    out["evidence_types"] = mapped
    out["evidence_types_raw"] = raw_types
    return out


def _extract_json(content: str) -> dict:
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON object in model output: {content[:120]!r}")
    return json.loads(content[start : end + 1])


def classify_one(image_path: Path) -> dict:
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    # reasoning_effort=none is measured to cut this read from ~51 s to ~25 s
    # on text-heavy photos; the template still emits a short reasoning trace.
    body = config.glimmer_body(
        [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": PROMPT},
        ]}], 512, SCHEMA)
    req = urllib.request.Request(
        f"{config.GLIMMER_URL}/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"},
    )
    resp = json.load(urllib.request.urlopen(req, timeout=900))
    content = resp["choices"][0]["message"]["content"]
    return {"parsed": normalize_labels(_extract_json(content)), "raw": resp, "content": content}


def classify_all(conn, workers: int = 4) -> dict:
    rows = conn.execute(
        """SELECT m.id, m.content_hash FROM media_items m
           LEFT JOIN classifications c ON c.media_id = m.id AND c.model = ? AND c.checkpoint = ?
           WHERE c.id IS NULL ORDER BY m.id""",
        (MODEL, CHECKPOINT),
    ).fetchall()

    def work(r):
        try:
            return r["id"], classify_one(config.ANALYSIS_DIR / f"{r['content_hash']}.jpg"), None
        except Exception as e:  # keep the run alive; failures are counted and resumable
            return r["id"], None, f"{type(e).__name__}: {e}"

    done, failed = 0, 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for media_id, result, err in ex.map(work, rows):
            if err is not None:
                failed += 1
                print(f"media {media_id} failed: {err}", flush=True)
                continue
            with conn:
                conn.execute(
                    "INSERT INTO classifications (media_id, model, checkpoint, labels_json, raw_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (media_id, MODEL, CHECKPOINT,
                     json.dumps(result["parsed"], ensure_ascii=False),
                     json.dumps({"content_text": result.get("content", ""),
                                 "timings": result["raw"].get("timings", {})}, ensure_ascii=False)),
                )
            done += 1
            if done % 20 == 0:
                print(f"classified {done}/{len(rows)}", flush=True)
    conn.commit()
    return {"classified": done, "failed": failed, "pending_before": len(rows)}
