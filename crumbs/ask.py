"""Ask engine (AGT v1.1): answers the demo query families by composing the
local index tools over records only.

Rules (AGT-04): every factual claim in an answer is assembled from stored
records (visits, place candidates, resolutions, extractions, user answers);
unknown is a designed outcome. Intent parsing is deterministic — a Glimmer
tool-calling front-end can replace the parser later without changing the
tools or the answer contract.

Answer contract: {"status": "answered"|"unknown", "answer": text,
"evidence": {"visits", "places", "media"}, "results": [visit card, ...]}.
A visit card carries the visit date, its best place name *with where that
name came from* (you confirmed / you named / sign text + GPS / nearby GPS
candidate), names read in its photos, dishes with their basis (menu, seen,
receipt), evidence photo ids, and the open review question if one exists.

Families, in order:
  C. "what did I have last time I was here?" (with current location)
     -> past visits within 1 km of the given coordinates.
  A. "what did I have / order / eat at <place>?" -> visits linked to that
     place (candidate, confirmed, or named by the user); dishes.
  E. dish / menu-text search, optionally inside an area or month:
     "where did I have the grilled fish in Kyoto?" -> photos whose
     extracted dishes or visible text match, grouped into visits.
  B. "what did I eat in <area> (in <month year>)?" -> food visits inside the
     area, richest evidence first.
  U. "have I been to <X>?" with nothing matching -> designed unknown.
  D. keyword fallback over extraction text.
"""

import json
import re

from .places import haversine_m

# Public city/area centers and radii (geography, not personal data) for name
# anchors that are areas rather than venues.
AREAS = {
    "kyoto": (35.0116, 135.7681, 15000), "arashiyama": (35.0094, 135.6668, 3000),
    "tokyo": (35.6762, 139.6503, 25000), "taipei": (25.0330, 121.5654, 15000),
    "seattle": (47.6062, -122.3321, 20000), "sapporo": (43.0618, 141.3545, 15000),
    "okinawa": (26.2124, 127.6809, 60000),
}
MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}

# Words that carry intent, not content, for dish/text search.
STOP = set("""
a an the and or of in at on to for from with near by about this that these those it its
i me my we our us you your what whats where when which who how did do does was were is are
been have has had ate eat eating order ordered get got try tried place places restaurant
restaurants food meal meals dish dishes there here last time again good best little ever never any
""".split()) | set(MONTHS) | set(AREAS)
FOOD_INTENT = (" eat", " ate", " food", " restaurant", " dish", " meal", " order", " had ",
               " have ", " lunch", " dinner", " breakfast", " cafe", " coffee", " place")
BASIS = {"read_on_menu": "menu", "menu text": "menu", "text_on_menu": "menu",
         "read_on_receipt": "receipt", "seen": "seen", "visual": "seen",
         "visible": "seen", "visible_in_image": "seen", "visible_food": "seen"}
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]+")


# -- query parsing -----------------------------------------------------------

def _window_from_query(q: str):
    m = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})", q)
    if m:
        y, mo = int(m.group(2)), MONTHS[m.group(1)]
        return (f"{y}-{mo:02d}-01", f"{y}-{mo:02d}-31")
    m = re.search(r"\b(20\d{2})\b", q)
    if m:
        return (f"{m.group(1)}-01-01", f"{m.group(1)}-12-31")
    return None


def _find_place_in_query(conn, q: str):
    """Longest registry place name appearing in the query (if any)."""
    best = None
    for p in conn.execute("SELECT id, name, lat, lon, kind FROM places"):
        name = p["name"]
        if len(name) >= 3 and name.lower() in q and (best is None or len(name) > len(best["name"])):
            best = dict(p)
    return best


def _find_area(q: str):
    for name, (lat, lon, radius) in AREAS.items():
        if re.search(rf"\b{name}\b", q):
            return {"name": name.title(), "lat": lat, "lon": lon, "radius_m": radius}
    return None


def _terms(q: str, drop=()):
    """Content words for dish/text search: latin words >= 3 chars (light
    plural stemming) plus CJK runs, minus intent words and named anchors."""
    dropped = " ".join(drop).lower()
    out = []
    for w in re.findall(r"[a-z][a-z'-]{2,}", q):
        if w in STOP or w in dropped.split():
            continue
        if len(w) > 4 and w.endswith("es") and not w.endswith("ses"):
            w = w[:-2]
        elif len(w) > 3 and w.endswith("s"):
            w = w[:-1]
        out.append(w)
    out += [r for r in CJK.findall(q) if r not in dropped]
    return list(dict.fromkeys(out))


# -- record access -----------------------------------------------------------

def _latest_extractions(conn):
    """media_id -> parsed extraction (latest row per photo)."""
    out = {}
    for mid, data_json in conn.execute(
            "SELECT media_id, data_json FROM extractions WHERE id IN (SELECT MAX(id) FROM extractions GROUP BY media_id)"):
        try:
            out[mid] = json.loads(data_json)
        except (TypeError, ValueError):
            continue
    return out


def _visit_media(conn, visit_id):
    return [r[0] for r in conn.execute(
        "SELECT vm.media_id FROM visit_media vm JOIN media_items m ON m.id = vm.media_id "
        "WHERE vm.visit_id = ? ORDER BY m.captured_at", (visit_id,))]


def _food_media(conn, visit_id):
    return {r[0] for r in conn.execute(
        """SELECT vm.media_id FROM visit_media vm
           JOIN classifications c ON c.id = (SELECT MAX(id) FROM classifications WHERE media_id = vm.media_id)
           WHERE vm.visit_id = ? AND json_extract(c.labels_json, '$.category') = 'food'""", (visit_id,))}


def _visit_dishes(conn, visit_id, ex=None):
    ex = ex if ex is not None else _latest_extractions(conn)
    dishes, seen = [], set()
    for mid in _visit_media(conn, visit_id):
        for d in (ex.get(mid) or {}).get("dish_candidates", []) or []:
            name = (d.get("name") or "").strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                dishes.append({"name": name, "basis": BASIS.get(d.get("basis"), d.get("basis") or "seen")})
    # Menu-read names first: they are text evidence, not appearance guesses.
    return sorted(dishes, key=lambda d: d["basis"] != "menu")


def _visit_text_names(conn, visit_id, ex):
    names = []
    for mid in _visit_media(conn, visit_id):
        for p in (ex.get(mid) or {}).get("place_name_candidates", []) or []:
            n = (p.get("name") or "").strip()
            if n and n not in names:
                names.append(n)
    return names


def _place_name(conn, place_id):
    r = conn.execute("SELECT name FROM places WHERE id = ?", (place_id,)).fetchone()
    return r[0] if r else None


def visit_place(conn, visit_id):
    """Best place for a visit and where that answer came from. A user's
    answer outranks the model; a rejected candidate is never shown as the
    place. Returns {name, place_id, source, status, rejected}."""
    user = conn.execute(
        "SELECT top_place_id, status, reasons_json FROM visit_resolutions WHERE visit_id = ? AND created_by = 'user'",
        (visit_id,)).fetchone()
    rejected = None
    if user:
        why = json.loads(user["reasons_json"] or "{}")
        if user["status"] == "confirmed":
            return {"name": _place_name(conn, user["top_place_id"]), "place_id": user["top_place_id"],
                    "source": "you confirmed", "status": "confirmed", "rejected": None}
        if user["status"] == "named":
            return {"name": why.get("name"), "place_id": None, "source": "you named it",
                    "status": "confirmed", "rejected": None}
        if user["status"] == "rejected":
            rejected = user["top_place_id"]
    algo = conn.execute(
        "SELECT top_place_id, status, reasons_json FROM visit_resolutions "
        "WHERE visit_id = ? AND created_by != 'user' ORDER BY id DESC LIMIT 1", (visit_id,)).fetchone()
    if algo and algo["top_place_id"] and algo["status"] in ("candidate-strong", "candidate-weak") \
            and algo["top_place_id"] != rejected:
        ranked = (json.loads(algo["reasons_json"] or "{}") or {}).get("ranked", [])
        why = " ".join(ranked[0]["why"]) if ranked else ""
        source = "sign text + GPS" if "signage" in why else "nearby (GPS)"
        return {"name": _place_name(conn, algo["top_place_id"]), "place_id": algo["top_place_id"],
                "source": source, "status": algo["status"], "rejected": _place_name(conn, rejected) if rejected else None}
    return {"name": None, "place_id": None, "source": None, "status": "unknown",
            "rejected": _place_name(conn, rejected) if rejected else None}


def visit_card(conn, visit_id, ex=None, matched_media=(), match=None):
    ex = ex if ex is not None else _latest_extractions(conn)
    dishes = _visit_dishes(conn, visit_id, ex)
    if match:
        # Dishes that matched the question first, so the card shows why it is here.
        dishes.sort(key=lambda d: -sum(t in d["name"].lower() for t in match))
    v = conn.execute("SELECT * FROM visits WHERE id = ?", (visit_id,)).fetchone()
    food = _food_media(conn, visit_id)
    ordered = list(dict.fromkeys(list(matched_media) +
                                 [m for m in _visit_media(conn, visit_id) if m in food or m in ex]))
    q = conn.execute("SELECT id, question FROM review_questions WHERE visit_id = ? AND status = 'open' "
                     "ORDER BY id LIMIT 1", (visit_id,)).fetchone()
    place = visit_place(conn, visit_id)
    return {
        "visit_id": visit_id,
        "date": (v["started_at"] or "")[:10] or None,
        "place": place,
        "text_names": _visit_text_names(conn, visit_id, ex)[:3],
        "dishes": dishes[:6],
        "media": ordered[:4],
        "food_photos": len(food),
        "match": match,
        "review": {"question_id": q["id"], "question": q["question"]} if q and place["status"] != "confirmed" else None,
    }


def _card_line(c):
    p = c["place"]
    if p["name"]:
        place = f"{p['name']}" + (" ✓" if p["status"] == "confirmed" else "?") + f" ({p['source']})"
    elif c["text_names"]:
        place = f"unconfirmed — photo text reads '{c['text_names'][0]}'"
    else:
        place = "unnamed place"
    dishes = ", ".join(f"{d['name']} [{d['basis']}]" for d in c["dishes"][:4])
    return f"- {c['date'] or 'undated'} · {place}" + (f" — {dishes}" if dishes else "")


def _answer(header, cards, extra_evidence=None):
    evidence = {"visits": [c["visit_id"] for c in cards],
                "places": [c["place"]["place_id"] for c in cards if c["place"]["place_id"]],
                "media": [m for c in cards for m in c["media"]]}
    if extra_evidence:
        evidence.update(extra_evidence)
    return {"status": "answered", "answer": "\n".join([header] + [_card_line(c) for c in cards]),
            "evidence": evidence, "results": cards}


def _unknown(text):
    return {"status": "unknown", "answer": text, "evidence": {"visits": [], "places": [], "media": []}, "results": []}


def _in_scope(v, area, window):
    if window and not (v["started_at"] and window[0] <= v["started_at"][:10] <= window[1]):
        return False
    if area:
        if v["center_lat"] is None:
            return False
        return haversine_m(area["lat"], area["lon"], v["center_lat"], v["center_lon"]) <= area["radius_m"]
    return True


def _scope_text(area, window):
    text = f" in {area['name']}" if area else ""
    if window:
        whole_year = window[0][5:] == "01-01" and window[1][5:] == "12-31"
        text += f" ({window[0][:4]})" if whole_year else f" ({window[0][:7]})"
    return text


# -- families ----------------------------------------------------------------

def _dish_search(conn, terms, area, window, ex):
    """Photos whose extracted dish names (weight 2) or visible text (1) match
    the terms, grouped into visits; every term must match somewhere in the
    visit so 'grilled fish' does not return every grilled thing."""
    per_visit = {}
    media_visit = dict(conn.execute("SELECT media_id, visit_id FROM visit_media").fetchall())
    for mid, data in ex.items():
        vid = media_visit.get(mid)
        if vid is None:
            continue
        dish_text = " ".join((d.get("name") or "") for d in data.get("dish_candidates", []) or []).lower()
        text = (data.get("visible_text") or "").lower()
        hit_terms, score = set(), 0
        for t in terms:
            if t in dish_text:
                hit_terms.add(t); score += 2
            elif t in text:
                hit_terms.add(t); score += 1
        if len(terms) > 1 and hit_terms == set(terms):
            score += 4 * len(terms)  # the whole phrase in one photo beats terms spread over a visit
        if hit_terms:
            agg = per_visit.setdefault(vid, {"score": 0, "terms": set(), "media": []})
            agg["score"] += score
            agg["terms"] |= hit_terms
            agg["media"].append(mid)
    ranked = []
    for vid, agg in per_visit.items():
        if agg["terms"] != set(terms):
            continue
        v = conn.execute("SELECT * FROM visits WHERE id = ?", (vid,)).fetchone()
        if v is None or not _in_scope(v, area, window):
            continue
        ranked.append((agg["score"], v["started_at"] or "", vid, agg["media"]))
    ranked.sort(key=lambda r: (-r[0], r[1]))
    return [(vid, media) for _, _, vid, media in ranked]


def place_visit_cards(conn, place, ex):
    """(visits whose best place is `place`, close-candidate food visits)."""
    vids = [r[0] for r in conn.execute(
        """SELECT DISTINCT v.id FROM visits v
           WHERE v.id IN (SELECT visit_id FROM visit_place_candidates WHERE place_id = ?)
              OR v.id IN (SELECT visit_id FROM visit_resolutions WHERE top_place_id = ?)
           ORDER BY v.started_at""", (place["id"], place["id"]))]
    close = {r[0] for r in conn.execute(
        "SELECT visit_id FROM visit_place_candidates WHERE place_id = ? AND (distance_m <= 120 OR evidence != 'gps')",
        (place["id"],))}
    cards = [visit_card(conn, vid, ex) for vid in vids]
    primary = [c for c in cards if c["place"]["place_id"] == place["id"]]
    near = [c for c in cards if c["place"]["place_id"] != place["id"] and c["visit_id"] in close and c["food_photos"]]
    return primary, near


def food_visit_cards(conn, scope, window, ex):
    """Food visits inside an area/window, best-evidenced first."""
    picked = []
    for v in conn.execute("SELECT * FROM visits WHERE center_lat IS NOT NULL ORDER BY started_at"):
        if _in_scope(v, scope, window):
            c = visit_card(conn, v["id"], ex)
            if c["food_photos"] or c["dishes"]:
                picked.append(c)
    picked.sort(key=lambda c: (-(c["place"]["status"] == "confirmed") - bool(c["place"]["name"]) - bool(c["dishes"]),
                               c["date"] or ""))
    return picked


def ask(conn, question: str, lat=None, lon=None) -> dict:
    q = " " + question.lower().strip() + " "
    ex = _latest_extractions(conn)

    # Family C: last time I was here (needs the owner's current location)
    if ("last time" in q or "was here" in q or "near me" in q) and lat is not None:
        rows = []
        for v in conn.execute("SELECT * FROM visits WHERE center_lat IS NOT NULL ORDER BY started_at DESC"):
            if haversine_m(lat, lon, v["center_lat"], v["center_lon"]) <= 1000:
                rows.append(v["id"])
                if len(rows) >= 5:
                    break
        if not rows:
            return _unknown("No past visits found within 1 km of your current location.")
        return _answer("Your past visits near here:", [visit_card(conn, vid, ex) for vid in rows])

    place = _find_place_in_query(conn, q)
    area = _find_area(q)
    window = _window_from_query(q)

    # Family A: what did I have at <place>
    if place and any(w in q for w in (" have ", " had ", " order", " eat ", " ate ")):
        primary, close = place_visit_cards(conn, place, ex)
        if primary:
            return _answer(f"Your visits to {place['name']} (✓ = you confirmed; ? = best candidate):", primary[:8],
                           {"places": [place["id"]]})
        if not close:
            return _unknown(f"No visits are linked to {place['name']} yet.")
        return _answer(f"No visit resolves to {place['name']}, but it is a close candidate for these food visits:",
                       close[:8], {"places": [place["id"]]})

    # Family E: dish / menu-text search
    terms = _terms(q, drop=[place["name"]] if place else [])
    been_to = re.search(r"\bbeen (?:to|in)\s+([a-z][a-z .'-]+?)[ ?!.]*$", q.strip())
    if terms and not been_to:
        hits = _dish_search(conn, terms, area, window, ex)
        if hits:
            cards = [visit_card(conn, vid, ex, matched_media=media, match=terms) for vid, media in hits[:6]]
            return _answer(f"Visits whose dishes or menu text mention {' + '.join(repr(t) for t in terms)}"
                           f"{_scope_text(area, window)}:", cards)
        if area or window or any(w in q for w in FOOD_INTENT):
            return _unknown(f"Nothing in your extracted dishes or menu text mentions {' + '.join(repr(t) for t in terms)}"
                            f"{_scope_text(area, window)}. That doesn't prove you never had it — only food photos "
                            "with readable menus or visible dishes are indexed.")

    # Family B: food visits in an area / window
    if (area or place) and (window or any(w in q for w in FOOD_INTENT)):
        scope = area or {"name": place["name"], "lat": place["lat"], "lon": place["lon"], "radius_m": 2000}
        picked = food_visit_cards(conn, scope, window, ex)
        if not picked:
            return _unknown(f"No food visits found{_scope_text(scope, window)}.")
        return _answer(f"Food visits{_scope_text(scope, window)} ({len(picked)} found; best-evidenced first):", picked[:8])

    # Family U: "have I been to X?" with nothing to anchor it
    if been_to and not (area or place):
        target = been_to.group(1).strip()
        return _unknown(f"I have no visit, known place, or photo text matching '{target}' in your history.")
    if been_to and area:
        n = sum(1 for v in conn.execute("SELECT * FROM visits WHERE center_lat IS NOT NULL") if _in_scope(v, area, window))
        if not n:
            return _unknown(f"No visits{_scope_text(area, window)} in your history.")
        return {"status": "answered", "answer": f"Yes — {n} visits{_scope_text(area, window)}.",
                "evidence": {"visits": [], "places": [], "media": []}, "results": []}

    # Family D: keyword fallback across extraction text
    words = [w for w in re.findall(r"[a-z]{4,}", q) if w not in STOP]
    hits = [mid for mid, data in ex.items() if words and any(w in json.dumps(data, ensure_ascii=False).lower() for w in words)]
    if hits:
        return {"status": "answered",
                "answer": f"Found {len(hits)} photos whose extracted text mentions {', '.join(words[:3])}.",
                "evidence": {"visits": [], "places": [], "media": hits[:10]}, "results": []}
    return _unknown("I don't have records that answer that yet. Try a dish, a place name, a city, or a month and year.")
