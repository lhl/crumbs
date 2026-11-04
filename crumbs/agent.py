"""Glimmer agent for Ask (AGT-02 v1): Muse Glimmer plans tool calls over the
local index and writes a short answer; the evidence comes only from tools.

Design:
- Glimmer is served by llama.cpp (`--jinja`, native tool-call parsing) or
  vLLM at GLIMMER_URL. It never sees photos or coordinates here, only the
  compact text of tool results (dates, place names with their provenance,
  dish names, photo-text names).
- Tools are the deterministic Ask functions (crumbs.ask), so the agent and
  the parser answer from the same records.
- Multi-step recall follows the skill in crumbs/skills/recall.md (loaded
  into the system prompt): classify the question, then for anchored
  questions find the anchor photo, read that day's moments, and take the
  name from photo text in the matching meal moment.
- Grounding check: the answer cites visits as [v<id>] and moments as
  [p<photo id>]. Citations of anything no tool returned are removed and
  reported; the cards shown are the cited moments and visits (or, if none
  were cited, everything the tools found). No tool results means the
  status is "unknown", whatever the text says.
- look_at_photos is the only path where Glimmer sees pixels, and only for
  photos a tool already returned; its output is labelled a model
  observation.
- If Glimmer is unreachable, the deterministic parser answers and the
  response says so; nothing is faked.
"""

import base64
import json
import re
import time
from pathlib import Path
import urllib.error
import urllib.request

from . import config
from .ask import (AREAS, _dish_search, _find_area, _latest_extractions, _terms, ask as parse_ask,
                  food_visit_cards, place_visit_cards, visit_card)
from .moments import day_visits, find_photos, moment_card, moment_line, visit_moments
from .places import haversine_m, search_name

MAX_ROUNDS = 5
MAX_CARDS = 6
MAX_MOMENTS = 18
MAX_LOOKS = 2
SKILL = (Path(__file__).parent / "skills" / "recall.md").read_text(encoding="utf-8")

SYSTEM = """You are Crumbs, a private assistant over the user's own food and travel history, \
reconstructed from their photos and location history. Use the tools to look things up; never answer \
from general knowledge.

Rules:
- Every visit, place, date, or dish you mention must come from a tool result. Cite visits as [v123].
- A place marked status "candidate" is a best guess from GPS or sign text: say "probably" or "likely". \
"confirmed" means the user confirmed it. If place is null, the place is unnamed.
- photo_text_names are words read in the photos (signs, cups, packaging), not a verified place: say "photo text reads X".
- Never infer a restaurant from what the food looks like.
- If the tools return nothing relevant, say plainly that the history has no record of it. Unknown is a fine answer.
- Search dishes with short English food words (e.g. "dumpling", "grilled fish"); try one alternative wording if the first search is empty.
- Simple questions need one tool call; anchored questions need a few. Answer in 1-3 short sentences, \
in the user's language. No lists, no markdown.

""" + SKILL


def _tool_specs(has_location: bool):
    month = {"type": "string", "description": "optional month as YYYY-MM, or year as YYYY"}
    names = ", ".join(sorted(AREAS))
    city = {"type": "string", "description": f"optional city filter; this lookup can resolve: {names} "
                                             "(a lookup list, not a list of places the user visited)"}
    specs = [
        ("search_dishes", "Find past visits whose recognized dishes or menu/sign text match food words.",
         {"terms": {"type": "string", "description": "food words, e.g. 'soup dumpling'"}, "city": city, "month": month},
         ["terms"]),
        ("food_visits_in_city", "List food visits in a city, best-evidenced first.",
         {"city": {"type": "string", "description": f"this lookup can resolve: {names}"}, "month": month}, ["city"]),
        ("visits_at_place", "Find visits to a named restaurant/cafe/shop and what was eaten there.",
         {"name": {"type": "string"}}, ["name"]),
        ("visit_details", "All recorded dishes and names for one visit.",
         {"visit_id": {"type": "integer"}}, ["visit_id"]),
        ("find_photos", "Find photos whose read text (signs, tickets, menus, place names) matches a name. "
         "Use for the anchor of an anchored question (a landmark, hotel, event).",
         {"text": {"type": "string", "description": "one distinctive name, e.g. 'Kinkakuji'"}, "city": city,
          "month": month}, ["text"]),
        ("day_timeline", "The moments of one day in time order (each usually one meal or stop) with their "
         "dishes and photo text.",
         {"date": {"type": "string", "description": "YYYY-MM-DD"}}, ["date"]),
        ("look_at_photos", "Have the vision model look at photos already returned by a tool and answer a short "
         "question about what is visible. Only for visual details the text does not cover.",
         {"photo_ids": {"type": "array", "items": {"type": "integer"}, "description": "1-2 photo_id values"},
          "question": {"type": "string"}}, ["photo_ids", "question"]),
    ]
    if has_location:
        specs.append(("visits_near_me", "Past visits within 1 km of the user's current location.", {}, []))
    return [{"type": "function", "function": {
        "name": n, "description": d,
        "parameters": {"type": "object", "properties": props, "required": req}}} for n, d, props, req in specs]


def _window(month):
    if not month:
        return None
    m = re.fullmatch(r"\s*(\d{4})(?:-(\d{1,2}))?\s*", str(month))
    if not m:
        return None
    if m.group(2):
        return (f"{m.group(1)}-{int(m.group(2)):02d}-01", f"{m.group(1)}-{int(m.group(2)):02d}-31")
    return (f"{m.group(1)}-01-01", f"{m.group(1)}-12-31")


def _compact(card):
    p = card["place"]
    return {"visit_id": card["visit_id"], "date": card["date"],
            "place": p["name"], "place_status": "confirmed" if p["status"] == "confirmed" else
            ("candidate" if p["name"] else None), "place_source": p["source"],
            "photo_text_names": card["text_names"][:2],
            "dishes": [f"{d['name']} ({d['basis']})" for d in card["dishes"][:5]]}


class Tools:
    def __init__(self, conn, lat=None, lon=None, vision=None):
        self.conn, self.lat, self.lon = conn, lat, lon
        self.vision = vision or _vision
        self.ex = _latest_extractions(conn)
        self.cards = {}  # visit_id -> full card, everything any tool returned
        self.photos = set()  # photo ids any tool returned (citable as [p<id>])

    def _keep(self, cards):
        for c in cards[:MAX_CARDS]:
            self.cards.setdefault(c["visit_id"], c)
        return {"visits": [_compact(c) for c in cards[:MAX_CARDS]], "total_found": len(cards)}

    def _area(self, city):
        if not city:
            return None, None
        area = _find_area(f" {city.lower()} ")
        if area is None:
            return None, {"error": f"the city lookup cannot resolve '{city}' (it only knows {', '.join(sorted(AREAS))}); "
                                   "that does not mean the user never went there. Retry without a city."}
        return area, None

    def search_dishes(self, terms="", city=None, month=None):
        if isinstance(terms, list):
            terms = " ".join(map(str, terms))
        words = _terms(f" {terms.lower()} ")
        if not words:
            return {"error": "no searchable food words"}
        area, err = self._area(city)
        if err:
            return err
        hits = _dish_search(self.conn, words, area, _window(month), self.ex)
        return self._keep([visit_card(self.conn, vid, self.ex, matched_media=m, match=words) for vid, m in hits[:MAX_CARDS]]
                          ) | {"total_found": len(hits)}

    def food_visits_in_city(self, city="", month=None):
        area, err = self._area(city)
        if err or area is None:
            return err or {"error": "city required"}
        return self._keep(food_visit_cards(self.conn, area, _window(month), self.ex))

    def visits_at_place(self, name=""):
        name = (name or "").strip()
        if len(name) < 2:
            return {"error": "name required"}
        hits = search_name(self.conn, name)
        if hits:
            primary, near = place_visit_cards(self.conn, hits[0], self.ex)
            if primary or near:
                out = self._keep(primary or near)
                out["matched_place"] = hits[0]["name"]
                out["note"] = None if primary else "no visit resolves to this place; these visits have it as a close candidate"
                return out
        # Names read from signs/menus in the user's own photos (unverified).
        needle = name.lower()
        media_visit = dict(self.conn.execute("SELECT media_id, visit_id FROM visit_media").fetchall())
        vids = []
        for mid, data in self.ex.items():
            names = " ".join((p.get("name") or "") for p in data.get("place_name_candidates", []) or []).lower()
            if needle in names and media_visit.get(mid) not in vids and mid in media_visit:
                vids.append(media_visit[mid])
        if not vids:
            return {"visits": [], "total_found": 0, "note": f"no visit or photo text matches '{name}'"}
        out = self._keep([visit_card(self.conn, v, self.ex) for v in vids])
        out["note"] = "matched by text read in the user's photos (unverified)"
        return out

    def visit_details(self, visit_id=0):
        try:
            vid = int(visit_id)
        except (TypeError, ValueError):
            return {"error": "visit_id must be an integer"}
        if not self.conn.execute("SELECT 1 FROM visits WHERE id = ?", (vid,)).fetchone():
            return {"error": "no such visit"}
        card = visit_card(self.conn, vid, self.ex)
        self.cards.setdefault(vid, card)
        full = _compact(card)
        full["dishes"] = [f"{d['name']} ({d['basis']})" for d in card["dishes"]]
        return full

    def find_photos(self, text="", city=None, month=None):
        text = (text or "").strip()
        if len(text) < 2:
            return {"error": "text required"}
        area, err = self._area(city)
        if err:
            return err
        hits = find_photos(self.conn, self.ex, text, area, _window(month))
        self.photos.update(h["photo_id"] for h in hits)
        out = {"photos": hits, "total_found": len(hits)}
        if not hits:
            out["note"] = f"no photo text matches '{text}'; try another spelling or language once"
        return out

    def day_timeline(self, date=""):
        m = re.fullmatch(r"\s*(\d{4}-\d{2}-\d{2})\s*", str(date or ""))
        if not m:
            return {"error": "date must be YYYY-MM-DD"}
        moments = []
        for vid in day_visits(self.conn, m.group(1)):
            self.cards.setdefault(vid, visit_card(self.conn, vid, self.ex))
            moments += [x for x in visit_moments(self.conn, vid, self.ex)
                        if x["date"] == m.group(1) and (x["food"] or x["names"] or x["dishes"])]
        self.photos.update(x["photo_id"] for x in moments[:MAX_MOMENTS])
        return {"date": m.group(1), "moments": [moment_line(x) for x in moments[:MAX_MOMENTS]],
                "total_found": len(moments),
                "note": "each moment is photos close in time; photo_id cites it as [p<photo_id>]. If a moment "
                        "matches the question, answer now in 1-2 sentences: no further lookups are needed."}

    def look_at_photos(self, photo_ids=(), question=""):
        if isinstance(photo_ids, (int, str)):
            photo_ids = [photo_ids]
        try:
            ids = [int(p) for p in photo_ids][:MAX_LOOKS]
        except (TypeError, ValueError):
            return {"error": "photo_ids must be integers"}
        unknown = [p for p in ids if p not in self.photos]
        if not ids or unknown:
            return {"error": "only photo_id values returned by find_photos or day_timeline can be looked at"}
        out = []
        for pid in ids:
            card = moment_card(self.conn, self.ex, pid)
            looks = card["media"][:1] if card else [pid]  # the moment's best food photo
            try:
                seen = self.vision(self.conn, looks[0], question or "What is visible?")
            except Exception as e:  # vision is best-effort evidence, never fatal
                seen = f"(could not look: {type(e).__name__})"
            out.append({"photo_id": pid, "looked_at": looks[0], "seen": seen})
        return {"observations": out, "total_found": len(out),
                "note": "model observation of the photo, not a verified fact"}

    def visits_near_me(self):
        if self.lat is None:
            return {"error": "current location unknown"}
        vids = []
        for v in self.conn.execute("SELECT * FROM visits WHERE center_lat IS NOT NULL ORDER BY started_at DESC"):
            if haversine_m(self.lat, self.lon, v["center_lat"], v["center_lon"]) <= 1000:
                vids.append(v["id"])
        return self._keep([visit_card(self.conn, v, self.ex) for v in vids])

    def call(self, name, args):
        fn = getattr(self, name, None) if name in {"search_dishes", "food_visits_in_city", "visits_at_place",
                                                  "visit_details", "visits_near_me", "find_photos",
                                                  "day_timeline", "look_at_photos"} else None
        if fn is None:
            return {"error": f"unknown tool {name}"}
        try:
            return fn(**(args or {}))
        except TypeError as e:
            return {"error": f"bad arguments: {e}"}


def _chat(messages, tools, tool_choice="auto", timeout=180):
    body = {"messages": messages, "max_tokens": 700,
            "temperature": 0.2, "chat_template_kwargs": {"reasoning_effort": "none"}}
    if tools:
        # With no tools offered, nothing is sent: llama.cpp's tool-call parser rejects
        # (HTTP 500) a turn where Glimmer still tries a call under tool_choice "none".
        body |= {"tools": tools, "tool_choice": tool_choice}
    if config.GLIMMER_MODEL:
        body["model"] = config.GLIMMER_MODEL
    req = urllib.request.Request(config.GLIMMER_URL.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)["choices"][0]["message"]


def _vision(conn, media_id, question, timeout=120):
    """One photo, one question, answered by Glimmer's vision (local preview only)."""
    from .label_server import ensure_preview  # local import: keeps agent import light
    h = conn.execute("SELECT content_hash FROM media_items WHERE id = ?", (media_id,)).fetchone()
    if not h:
        return "(no such photo)"
    b64 = base64.b64encode(ensure_preview(h[0]).read_bytes()).decode()
    messages = [{"role": "system", "content": "Describe only what is visible in the photo. Answer in one short "
                 "sentence. Copy any visible shop or restaurant name exactly; do not guess names."},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": question}]}]
    return _clean(_chat(messages, [], timeout=timeout).get("content"))


def _clean(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    return text.strip()


def run_agent(conn, question: str, lat=None, lon=None, chat=_chat, vision=None) -> dict:
    t0 = time.time()
    tools = Tools(conn, lat, lon, vision=vision)
    specs = _tool_specs(lat is not None)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    trace, text, error = [], "", None

    def ask_model(choice):
        for attempt in (1, 2):  # one retry: llama.cpp occasionally 500s on a turn
            try:
                if choice == "none":  # answer-only turn: offer no tools at all
                    return chat(messages + [{"role": "user", "content": "Answer now from the tool results above."}],
                                [], tool_choice="none")
                return chat(messages, specs, tool_choice=choice)
            except urllib.error.HTTPError:
                if attempt == 2:
                    raise

    try:
        for rnd in range(MAX_ROUNDS + 1):
            last = rnd == MAX_ROUNDS
            t = time.time()
            msg = ask_model("none" if last else "auto")
            calls = [] if last else (msg.get("tool_calls") or [])
            if not calls:
                text = _clean(msg.get("content"))
                if not text and not last:  # empty answer: ask once more for the text only
                    text = _clean(ask_model("none").get("content"))
                trace.append({"step": "answer", "ms": round((time.time() - t) * 1000)})
                break
            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            trace.append({"step": "plan", "ms": round((time.time() - t) * 1000)})
            for c in calls:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except ValueError:
                    args = {}
                result = tools.call(name, args)
                found = result.get("total_found", 1 if name == "visit_details" and "error" not in result else None)
                if name == "look_at_photos":
                    trace.append({"step": "look", "seen": [o["seen"] for o in result.get("observations", [])]})
                trace.append({"step": "tool", "tool": name, "args": args, "found": found, "error": result.get("error")})
                messages.append({"role": "tool", "tool_call_id": c.get("id", name), "name": name,
                                 "content": json.dumps(result, ensure_ascii=False)})
    except (urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as e:
        error = f"Glimmer unavailable ({type(e).__name__}: {e})"
        if not tools.cards:
            fallback = parse_ask(conn, question, lat=lat, lon=lon)
            fallback["agent"] = {"used": False, "error": error + "; answered by the deterministic parser", "trace": trace}
            return fallback
        text = "Glimmer did not finish an answer; these are the visits its tool calls found."

    cited = [int(v) for v in re.findall(r"\[v(\d+)\]", text)]
    cited_p = [int(p) for p in re.findall(r"\[p(\d+)\]", text)]
    unsupported = sorted({v for v in cited if v not in tools.cards})
    unsupported_p = sorted({p for p in cited_p if p not in tools.photos})
    for v in unsupported:
        text = text.replace(f"[v{v}]", "")
    for p in unsupported_p:
        text = text.replace(f"[p{p}]", "")
    moment_cards = [c for c in (moment_card(conn, tools.ex, p) for p in dict.fromkeys(cited_p) if p in tools.photos) if c]
    moment_cards.sort(key=lambda c: not c["dishes"])  # the meal first, the anchor after it
    shown = [v for v in dict.fromkeys(cited) if v in tools.cards]
    if not shown and not moment_cards:
        shown = list(tools.cards)[:MAX_CARDS]
    cards = (moment_cards + [tools.cards[v] for v in shown])[:MAX_CARDS]
    status = "answered" if cards else "unknown"
    if not cards and not text:
        text = "I couldn't find anything about that in your history."
    return {
        "status": status,
        "answer": text,
        "evidence": {"visits": [c["visit_id"] for c in cards],
                     "places": [c["place"]["place_id"] for c in cards if c["place"]["place_id"]],
                     "media": [m for c in cards for m in c["media"]]},
        "results": cards,
        "agent": {"used": True, "model": config.GLIMMER_MODEL or "muse-glimmer-30b (llama.cpp)",
                  "trace": trace, "latency_s": round(time.time() - t0, 1), "error": error,
                  "grounding": {"cited": sorted(set(cited)), "cited_photos": sorted(set(cited_p)),
                                "unsupported_removed": unsupported, "unsupported_photos_removed": unsupported_p}},
    }
