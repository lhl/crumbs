"""Local API — the Crumbs side of the Muse bridge (API-01 v1, PLAN
section 8). Design rules from the bridge sketch:

- Read-only over the evidence store, with one exception: the owner's
  answers to review questions (POST /v1/review/<id>), which are appended
  as user rows and never overwrite model output. Every record returned
  carries its stable local id and provenance so an external agent cites
  records, not inventions. Photos are served only as stripped previews
  (GET /v1/media/<id>/preview).
- `near=current` is resolved *server-side*: the phone/owner posts the
  current location to this server (token-gated), and external queries
  never need to handle raw coordinates for "where am I now" questions.
- Privacy tiers enforced here, not by the caller: tier 0 = aggregates
  only, tier 1 = redacted (coordinates rounded to ~1 km, file names
  stripped), tier 2 = full records. Default tier 1.
- If CRUMBS_API_TOKEN is set, all /v1/* except /v1/health require it as a
  Bearer token. CRUMBS_AGENT_TOKEN, if set, is a second token for an
  external agent (the Muse bridge): read-only (POSTs refused) and capped
  at tier 1 whatever tier the caller asks for. Binds localhost by default; a non-loopback bind requires a
  token. Remote use belongs on a trusted LAN or the owner's authenticated
  tunnel (Tailscale/Headscale), never an exposed public port.
"""

import hmac
import ipaddress
import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from . import config, db
from .places import haversine_m, nearby as places_nearby, search_name

CURRENT = {"lat": None, "lon": None, "at": None}  # set by the owner's device via POST /v1/current


def _tier_of(q) -> int:
    try:
        return max(0, min(2, int(q.get("tier", ["1"])[0])))
    except ValueError:
        return 1


def _round(coord, tier):
    return coord if tier >= 2 or coord is None else round(coord, 2)


def _media_row(r, tier):
    d = {
        "media_id": r["id"], "captured_at": r["captured_at"],
        "lat": _round(r["gps_lat"], tier), "lon": _round(r["gps_lon"], tier),
        "category": r["category"], "evidence_types": json.loads(r["evidence_types"]) if r["evidence_types"] else [],
    }
    if tier >= 2:
        d["rel_path"] = r["rel_path"]
    return d


def make_handler(conn):
    token = os.environ.get("CRUMBS_API_TOKEN", "").strip()
    agent_token = os.environ.get("CRUMBS_AGENT_TOKEN", "").strip()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", "*")  # local dev surfaces (PWA on another port)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _role(self):
            """'owner', 'agent', or None (unauthorized)."""
            supplied = self.headers.get("Authorization", "").encode()
            if agent_token and hmac.compare_digest(supplied, f"Bearer {agent_token}".encode()):
                return "agent"
            if not token and not agent_token:
                return "owner"  # localhost dev: no tokens configured
            if token and hmac.compare_digest(supplied, f"Bearer {token}".encode()):
                return "owner"
            return None

        def _authed(self):
            return self._role() is not None

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.end_headers()

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            path = u.path.rstrip("/")
            if path == "/v1/health":
                counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                          for t in ("media_items", "classifications", "extractions", "visits", "places", "stays")}
                return self._json({"status": "ok", "counts": counts})
            if not self._authed():
                return self._json({"error": "unauthorized"}, 401)
            tier = _tier_of(q)
            if self._role() == "agent":
                tier = min(tier, 1)  # an external agent never gets exact coordinates or file paths
            try:
                if path == "/v1/search":
                    return self._json(self._search(q, tier))
                if path == "/v1/nearby":
                    return self._json(self._nearby(q, tier))
                if path == "/v1/visits":
                    return self._json(self._visits(q, tier))
                if path.startswith("/v1/visit/"):
                    return self._json(self._visit(int(path.split("/")[3]), tier))
                if path == "/v1/places":
                    return self._json({"places": search_name(conn, q.get("q", [""])[0])})
                if path == "/v1/anchor":
                    return self._json(self._anchor(q, tier))
                if path.startswith("/v1/media/") and path.endswith("/preview"):
                    return self._preview(int(path.split("/")[3]))
                if path == "/v1/review":
                    from .review import open_questions

                    return self._json({"questions": open_questions(conn, limit=min(int(q.get("limit", ["20"])[0]), 100))})
                if path == "/v1/ask":
                    from .ask import ask as ask_engine

                    lat = float(q["lat"][0]) if "lat" in q else (CURRENT["lat"] if q.get("near", [""])[0] == "current" else None)
                    lon = float(q["lon"][0]) if "lon" in q else (CURRENT["lon"] if q.get("near", [""])[0] == "current" else None)
                    if q.get("agent", ["0"])[0] in ("1", "true"):
                        from .agent import run_agent

                        return self._json(run_agent(conn, q.get("q", [""])[0], lat=lat, lon=lon))
                    return self._json(ask_engine(conn, q.get("q", [""])[0], lat=lat, lon=lon))
                return self._json({"error": "not found"}, 404)
            except Exception as e:
                return self._json({"error": f"{type(e).__name__}: {e}"}, 500)

        def _origin_ok(self):
            """Writes without a token accept only same-machine pages, so an
            arbitrary website cannot answer review questions via localhost."""
            origin = self.headers.get("Origin")
            if token or not origin:
                return True
            host = urlparse(origin).hostname or ""
            return host in ("127.0.0.1", "localhost", "::1")

        def _bytes(self, body, ctype, code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "private, max-age=3600")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            u = urlparse(self.path)
            path = u.path.rstrip("/")
            if not self._authed():
                return self._json({"error": "unauthorized"}, 401)
            if self._role() == "agent":
                return self._json({"error": "the agent token is read-only"}, 403)
            if not self._origin_ok():
                return self._json({"error": "cross-origin write refused"}, 403)
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except ValueError:
                return self._json({"error": "body must be JSON"}, 400)
            if path == "/v1/current":
                CURRENT.update(lat=float(data["lat"]), lon=float(data["lon"]),
                               at=datetime.now().isoformat(timespec="seconds"))
                return self._json({"ok": True, "current_set": True})
            if path.startswith("/v1/review/"):
                try:
                    qid = int(path.split("/")[3])
                except ValueError:
                    return self._json({"error": "bad question id"}, 400)
                from .review import answer_question

                try:
                    return self._json(answer_question(conn, qid, data.get("answer", ""), data.get("name")))
                except ValueError as e:
                    return self._json({"error": str(e)}, 400)
            return self._json({"error": "not found"}, 404)

        # -- endpoints -------------------------------------------------
        def _preview(self, media_id):
            """Stripped, phone-sized JPEG of a photo's analysis copy (the
            original is never served). Bearer-protected like every /v1 route."""
            from .label_server import ensure_preview

            r = conn.execute("SELECT content_hash FROM media_items WHERE id = ?", (media_id,)).fetchone()
            if r is None:
                return self._json({"error": "no such media"}, 404)
            f = ensure_preview(r["content_hash"])
            if not f.exists():
                return self._json({"error": "no analysis image for this media"}, 404)
            return self._bytes(f.read_bytes(), "image/jpeg")

        def _search(self, q, tier):
            text = q.get("q", [""])[0]
            cat = q.get("category", [None])[0]
            limit = min(int(q.get("limit", ["20"])[0]), 100)
            rows = conn.execute(
                """SELECT m.id, m.rel_path, m.captured_at, m.gps_lat, m.gps_lon,
                          json_extract(c.labels_json, '$.category') AS category,
                          json_extract(c.labels_json, '$.evidence_types') AS evidence_types,
                          e.data_json AS extraction
                   FROM media_items m
                   LEFT JOIN classifications c ON c.id = (SELECT MAX(id) FROM classifications WHERE media_id = m.id)
                   LEFT JOIN extractions e ON e.id = (SELECT MAX(id) FROM extractions WHERE media_id = m.id)
                   ORDER BY m.captured_at"""
            ).fetchall()
            out = []
            for r in rows:
                if cat and r["category"] != cat:
                    continue
                if text:
                    hay = " ".join(filter(None, [r["rel_path"], r["extraction"] or ""])).lower()
                    if text.lower() not in hay:
                        continue
                out.append(_media_row(r, tier))
            if tier == 0:
                return {"count": len(out)}
            return {"results": out[:limit]}

        def _nearby(self, q, tier):
            near = q.get("near", [""])[0]
            if near == "current":
                if CURRENT["lat"] is None:
                    return {"error": "current location not set (owner device posts /v1/current)"}
                lat, lon = CURRENT["lat"], CURRENT["lon"]
            else:
                lat, lon = float(q["lat"][0]), float(q["lon"][0])
            radius = int(q.get("radius_m", ["1000"])[0])
            places = places_nearby(conn, lat, lon, radius, q.get("kind", [None])[0])
            if tier == 0:
                return {"count": len(places)}
            for p in places:
                p["lat"], p["lon"] = _round(p["lat"], tier), _round(p["lon"], tier)
            return {"places": places, "current_location_at": CURRENT["at"] if near == "current" else None}

        def _visits(self, q, tier):
            frm, to = q.get("from", [None])[0], q.get("to", [None])[0]
            rows = conn.execute("SELECT * FROM visits ORDER BY started_at").fetchall()
            out = []
            for v in rows:
                if frm and v["ended_at"] < frm:
                    continue
                if to and v["started_at"] > to:
                    continue
                d = dict(v)
                d["center_lat"], d["center_lon"] = _round(d["center_lat"], tier), _round(d["center_lon"], tier)
                out.append(d)
            return {"count": len(out)} if tier == 0 else {"visits": out}

        def _visit(self, visit_id, tier):
            v = conn.execute("SELECT * FROM visits WHERE id = ?", (visit_id,)).fetchone()
            if v is None:
                return {"error": "no such visit"}
            photos = conn.execute(
                """SELECT m.id, m.rel_path, m.captured_at, m.gps_lat, m.gps_lon,
                          json_extract(c.labels_json, '$.category') AS category,
                          json_extract(c.labels_json, '$.evidence_types') AS evidence_types
                   FROM visit_media vm JOIN media_items m ON m.id = vm.media_id
                   LEFT JOIN classifications c ON c.id = (SELECT MAX(id) FROM classifications WHERE media_id = m.id)
                   WHERE vm.visit_id = ? ORDER BY m.captured_at""", (visit_id,)).fetchall()
            cands = conn.execute(
                """SELECT p.name, p.kind, p.cuisine, vc.distance_m, vc.evidence, vc.status
                   FROM visit_place_candidates vc JOIN places p ON p.id = vc.place_id
                   WHERE vc.visit_id = ? ORDER BY vc.distance_m LIMIT 15""", (visit_id,)).fetchall()
            stays = conn.execute(
                "SELECT stay_id, center_distance_m, time_relation FROM visit_stays WHERE visit_id = ?", (visit_id,)).fetchall()
            d = dict(v)
            d["center_lat"], d["center_lon"] = _round(d["center_lat"], tier), _round(d["center_lon"], tier)
            return {"visit": d, "photos": [_media_row(r, tier) for r in photos],
                    "place_candidates": [dict(c) for c in cands], "stay_matches": [dict(s) for s in stays]}

        def _anchor(self, q, tier):
            """The demo query: 'what else was near <anchor> during <window>?'
            Anchor resolves by place-search name (or lat/lon); returns visits
            in the window whose center is within radius of the anchor, each
            with its candidate restaurants and photo categories."""
            name = q.get("name", [""])[0]
            radius = int(q.get("radius_m", ["1500"])[0])
            if name:
                hits = search_name(conn, name)
                if not hits:
                    return {"error": f"no cached place matching {name!r}; run places-fetch for that area or pass lat/lon"}
                anchor = hits[0]
                lat, lon = anchor["lat"], anchor["lon"]
            else:
                lat, lon = float(q["lat"][0]), float(q["lon"][0])
                anchor = {"name": "coordinate anchor", "lat": lat, "lon": lon}
            frm, to = q.get("from", ["0000"])[0], q.get("to", ["9999"])[0]
            visits = []
            for v in conn.execute("SELECT * FROM visits WHERE center_lat IS NOT NULL ORDER BY started_at"):
                if not (frm <= v["started_at"][:10] and v["ended_at"][:10] <= to):
                    continue
                d = haversine_m(lat, lon, v["center_lat"], v["center_lon"])
                if d > radius:
                    continue
                cands = conn.execute(
                    """SELECT p.name, p.kind, vc.distance_m, vc.evidence FROM visit_place_candidates vc
                       JOIN places p ON p.id = vc.place_id WHERE vc.visit_id = ? ORDER BY vc.distance_m LIMIT 5""",
                    (v["id"],)).fetchall()
                cats = conn.execute(
                    """SELECT json_extract(c.labels_json, '$.category') AS cat, COUNT(*) AS n
                       FROM visit_media vm JOIN classifications c ON c.media_id = vm.media_id
                       WHERE vm.visit_id = ? GROUP BY cat""", (v["id"],)).fetchall()
                visits.append({"visit_id": v["id"], "started_at": v["started_at"], "ended_at": v["ended_at"],
                               "distance_to_anchor_m": round(d), "photo_count": v["photo_count"],
                               "categories": {r["cat"]: r["n"] for r in cats},
                               "candidates": [dict(c) for c in cands]})
            return {"anchor": anchor, "radius_m": radius, "window": [frm, to],
                    "visits": visits if tier > 0 else [], "visit_count": len(visits)}

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8770):
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host == "localhost"
    if not loopback and not os.environ.get("CRUMBS_API_TOKEN", "").strip():
        raise ValueError("CRUMBS_API_TOKEN is required when binding the API outside localhost")
    conn = db.connect(config.DB_PATH)
    try:
        db.init_schema(conn)
        with HTTPServer((host, port), make_handler(conn)) as server:
            server.serve_forever()
    finally:
        conn.close()
