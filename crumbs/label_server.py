"""Labeling helper (DAT-07): a tiny local web UI for fast human labels.

Design for labeling speed: one photo per screen, the model's current
classification and the visit's place candidates shown as *suggestions*,
one click (or key) to confirm/correct. Priority order puts the most
valuable items first: food photos, then model-unknowns, then everything
else. Labels are append-only rows in `labels` (field/value/source='user');
nothing is overwritten, so label history is itself auditable.

Serves only on localhost by default. This is a data-collection tool for
the corpus owner, not a product surface.

For phone labeling over a slow link, /img/ serves an optimized preview
(640 px long edge, quality 68) generated once with ImageMagick into
CRUMBS_DATA_DIR/previews/, not the 1024 px analysis JPEG. Previews are
content-addressed by hash, so they are served with immutable caching.
"""

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from . import config, db

PREVIEW_DIR_NAME = "previews"
PREVIEW_EDGE = 640

# Offline reverse geocoding (city/region/country from GPS) via the optional
# reverse-geocoder package, whose GeoNames data is local. The labeler must
# never send coordinates to a network geocoder, so when the package is not
# installed the UI falls back to coordinates + nearest cached place.
try:
    import reverse_geocoder as _rg
except Exception:  # pragma: no cover - depends on local env
    _rg = None

_CC_NAMES = {
    "JP": "Japan", "TW": "Taiwan", "US": "United States", "KR": "South Korea",
    "CN": "China", "HK": "Hong Kong", "TH": "Thailand", "VN": "Vietnam",
    "SG": "Singapore", "MY": "Malaysia", "ID": "Indonesia", "PH": "Philippines",
    "GB": "United Kingdom", "FR": "France", "DE": "Germany", "IT": "Italy",
    "ES": "Spain", "PT": "Portugal", "NL": "Netherlands", "CH": "Switzerland",
    "AT": "Austria", "CZ": "Czechia", "AU": "Australia", "NZ": "New Zealand",
    "CA": "Canada", "MX": "Mexico", "IN": "India", "AE": "UAE", "TR": "Turkey",
}
_geo_cache: dict = {}


def geolocate(conn, lat, lon) -> dict:
    """Location context for one photo: offline city/country + nearest place."""
    out = {"lat": round(lat, 5), "lon": round(lon, 5)}
    key = (round(lat, 2), round(lon, 2))
    if _rg is not None:
        if key not in _geo_cache:
            try:
                _geo_cache[key] = _rg.search([(lat, lon)], mode=1)[0]
            except Exception:
                _geo_cache[key] = None
        hit = _geo_cache.get(key)
        if hit:
            out["city"] = hit.get("name")
            out["region"] = hit.get("admin1")
            cc = hit.get("cc")
            out["country"] = _CC_NAMES.get(cc, cc)
    from .places import haversine_m

    best, best_d = None, None
    for p in conn.execute("SELECT name, kind, lat, lon FROM places"):
        d = haversine_m(lat, lon, p["lat"], p["lon"])
        if best_d is None or d < best_d:
            best, best_d = p, d
    if best is not None and best_d <= 50000:
        out["nearest_place"] = best["name"]
        out["nearest_place_m"] = round(best_d)
    return out


def preview_path(content_hash: str) -> Path:
    return config.DATA_DIR / PREVIEW_DIR_NAME / f"{content_hash}.jpg"


def ensure_preview(content_hash: str) -> Path:
    """Return a phone-sized preview of the analysis image, creating it once.

    Falls back to the analysis image itself when ImageMagick is missing
    or fails, so labeling never breaks over a preview problem.
    """
    src = config.ANALYSIS_DIR / f"{content_hash}.jpg"
    dest = preview_path(content_hash)
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["magick", str(src), "-resize", f"{PREVIEW_EDGE}x{PREVIEW_EDGE}>",
         "-strip", "-quality", "68", str(dest)],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not dest.exists():
        print(f"warn: preview failed for {content_hash}: {r.stderr.strip()[:160]}", file=sys.stderr)
        return src
    return dest

PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Crumbs labeler</title>
<style>
 body{font-family:system-ui;margin:.6rem auto;max-width:1240px;padding:0 .8rem;background:#111;color:#eee}
 img{width:100%;max-height:74vh;object-fit:contain;background:#000;border-radius:8px}
 .row{display:flex;gap:.5rem;flex-wrap:wrap;margin:.6rem 0}
 .layout{display:flex;gap:1rem;align-items:flex-start}
 .photocol{flex:1.5;min-width:0}
 .controls{flex:1;min-width:290px}
 .cols{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}
 .stack{display:flex;flex-direction:column;gap:.35rem}
 .stack button{text-align:left;padding:.45rem .6rem}
 h3{margin:.1rem 0 .4rem;font-size:.85rem;color:#aaa;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
 button{padding:.55rem .9rem;border-radius:8px;border:1px solid #555;background:#222;color:#eee;cursor:pointer;font-size:1rem}
 button.good{background:#14532d} button.bad{background:#7f1d1d}
 input{background:#222;color:#eee;border:1px solid #555;border-radius:6px;padding:.5rem;width:100%;box-sizing:border-box}
 label{display:block;margin-top:.55rem}
 .muted{color:#aaa} .card{background:#1b1b1b;border:1px solid #333;border-radius:10px;padding:.8rem}
 @media (max-width:760px){.layout{flex-direction:column}.controls{min-width:0;width:100%}img{max-height:42vh}}
</style>
<h1>🥖 Crumbs labeler <span class="muted" id="prog"></span></h1>
<div class="card">
 <div class="layout">
  <div class="photocol">
   <div id="meta" class="muted"></div>
   <img id="photo" alt="">
   <div id="suggest"></div>
   <div id="loc" class="muted"></div>
  </div>
  <div class="controls">
   <div class="cols">
    <div><h3>Category · keys 1-5</h3><div class="stack" id="cats"></div></div>
    <div><h3>Evidence · letter keys</h3><div class="stack" id="evs"></div></div>
   </div>
   <label>New evidence labels (comma-separated)<input id="evnew" placeholder="e.g. pet, screenshot, ticket"></label>
   <label>Dishes (comma-separated, if any)<input id="dishes" placeholder="e.g. grilled fish set, tonkotsu ramen"></label>
   <label>Place name (if you know it)<input id="place" placeholder="e.g. Yudofu Sagana"></label>
   <div class="row">
     <button id="back">\u2190 Back</button>
     <button class="good" id="save">Save + next (Enter)</button>
     <button id="skip">Skip (s / \u2192)</button>
   </div>
   <details><summary class="muted">Definitions &amp; examples</summary>
   <p class="muted">Category = the scene: <b>sightseeing</b> landmark/viewpoint/tourist spot · <b>trip</b> away-from-home travel context (transit, hotel, street abroad, restaurant while traveling) · <b>personal</b> everyday life at home/locally (people, home, everyday objects/restaurants — <i>not</i> 'private') · <b>food</b> dish or meal · <b>other</b> you know what it is but it fits none (object/tchotchke, screenshot, document, pet). 'unknown' is the model's word for abstaining — humans label <b>other</b> instead. A menu photo = food + menu evidence; a tchotchke at a restaurant = trip (if traveling) or personal (if local) + interior evidence. Selections start from the model's suggestion and stay highlighted until you change them.</p>
   </details>
  </div>
 </div>
</div>
<script>
let cur = null, chosen = null, evSel = new Set();
let hist = [], hidx = -1;  // visited media_ids, for Back/Forward
const CATS = ['sightseeing','trip','personal','food','other'];
const EVS = ['dish','menu','receipt','sign','storefront','interior','lodging','landmark','people','nature','document','other'];
const EVKEYS = {dish:'d',menu:'m',receipt:'c',sign:'g',storefront:'t',interior:'i',lodging:'h',landmark:'k',people:'p',nature:'n',document:'o',other:'x'};
function modelCategory(c) { return CATS.includes(c) ? c : 'other'; }
function show(d) {
  document.getElementById('prog').textContent = `— ${d.labeled} labeled / ${d.total} total`;
  if (!d.item) { document.getElementById('meta').textContent = 'Queue empty. Done!'; document.getElementById('photo').src=''; return; }
  cur = d.item;
  chosen = cur.user_category ? modelCategory(cur.user_category) : modelCategory(cur.category);
  evSel = new Set(cur.user_category ? (cur.user_evidence || []) : (cur.evidence_types || []));
  document.getElementById('photo').src = '/img/' + cur.media_id + '.jpg';
  document.getElementById('meta').textContent = `#${cur.media_id} · ${cur.captured_at || 'no time'} · ${cur.rel_path}` + (cur.user_category ? ` · your label: ${cur.user_category} (saving overwrites)` : '');
  document.getElementById('suggest').innerHTML =
    `<p>Model: <b>${cur.category}</b> · evidence: ${(cur.evidence_types||[]).join(', ') || '—'}` +
    (cur.candidates?.length ? `<br>Place candidates: ${cur.candidates.map(c=>`${c.name} (${Math.round(c.distance_m)}m)`).join(' · ')}` : '') + `</p>`;
  const L = cur.location;
  document.getElementById('loc').textContent = !L ? '📍 no GPS for this photo' :
    `📍 ${[L.city, L.region, L.country].filter(Boolean).join(', ') || 'unknown area'} · ${L.lat}, ${L.lon}` +
    (L.nearest_place ? ` · nearest place: ${L.nearest_place} (${L.nearest_place_m} m)` : '') + ' · offline approx.';
  document.getElementById('dishes').value = ''; document.getElementById('place').value = '';
  document.getElementById('evnew').value = '';
  renderCats(); renderEvs();
}
function renderEvs() {
  const el = document.getElementById('evs'); el.innerHTML = '';
  [...new Set([...EVS, ...evSel])].forEach(ev => {
    const b = document.createElement('button');
    b.textContent = (EVKEYS[ev] ? EVKEYS[ev] + ' · ' : '') + ev;
    if (evSel.has(ev)) b.className = 'good';
    b.onclick = () => { evSel.has(ev) ? evSel.delete(ev) : evSel.add(ev); renderEvs(); };
    el.appendChild(b);
  });
}
function renderCats() {
  const el = document.getElementById('cats'); el.innerHTML = '';
  CATS.forEach((c, i) => {
    const b = document.createElement('button');
    b.textContent = `${i+1} ${c}` + (c === cur.category ? ' (model)' : '');
    if (c === chosen) b.className = 'good';
    b.onclick = () => { chosen = c; renderCats(); };
    el.appendChild(b);
  });
}
async function advance() {
  if (hidx < hist.length - 1) {
    hidx++;
    const r = await fetch('/api/item/' + hist[hidx]); show(await r.json()); return;
  }
  const r = await fetch('/api/next?exclude=' + hist.join(',')); const d = await r.json();
  if (d.item) { hist.push(d.item.media_id); hidx = hist.length - 1; }
  show(d);
}
async function back() {
  if (hidx <= 0) return;
  hidx--;
  const r = await fetch('/api/item/' + hist[hidx]); show(await r.json());
}
async function next() { advance(); }
async function save() {
  if (!cur) return;
  const extra = document.getElementById('evnew').value.split(',').map(s=>s.trim().toLowerCase()).filter(Boolean);
  const body = { media_id: cur.media_id, category: chosen, evidence: [...new Set([...evSel, ...extra])],
    dishes: document.getElementById('dishes').value.split(',').map(s=>s.trim()).filter(Boolean),
    place: document.getElementById('place').value.trim() };
  await fetch('/api/label', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  advance();
}
document.getElementById('save').onclick = save;
document.getElementById('skip').onclick = advance;
document.getElementById('back').onclick = back;
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') { if (e.key === 'Enter') save(); return; }
  const i = ['1','2','3','4','5'].indexOf(e.key);
  if (i >= 0) { chosen = CATS[i]; renderCats(); return; }
  if (e.key === 'Enter') { save(); return; }
  if (e.key === 'ArrowRight') { advance(); return; }
  if (e.key === 'ArrowLeft') { back(); return; }
  if (e.key === 's') { next(); return; }
  const ev = Object.keys(EVKEYS).find(k => EVKEYS[k] === e.key.toLowerCase());
  if (ev) { evSel.has(ev) ? evSel.delete(ev) : evSel.add(ev); renderEvs(); }
});
next();
</script>"""


_ITEM_SQL = """SELECT m.id AS media_id, m.rel_path, m.captured_at, m.content_hash, m.gps_lat, m.gps_lon,
                  json_extract(c.labels_json, '$.category') AS category,
                  json_extract(c.labels_json, '$.evidence_types') AS evidence_types
           FROM media_items m
           LEFT JOIN classifications c ON c.id = (SELECT MAX(id) FROM classifications WHERE media_id = m.id)"""


def _queue(conn, exclude=()):
    rows = conn.execute(
        _ITEM_SQL + """
           WHERE NOT EXISTS (SELECT 1 FROM labels l WHERE l.media_id = m.id AND l.field = 'category')
           ORDER BY CASE json_extract(c.labels_json, '$.category')
                      WHEN 'food' THEN 0 WHEN 'unknown' THEN 1 ELSE 2 END, m.id"""
    ).fetchall()
    excl = {int(x) for x in exclude}
    return [r for r in rows if r["media_id"] not in excl]


def _build_item(conn, row):
    r = dict(row)
    r["evidence_types"] = json.loads(r["evidence_types"]) if r["evidence_types"] else []
    (visit_id,) = conn.execute(
        "SELECT visit_id FROM visit_media WHERE media_id = ?", (r["media_id"],)
    ).fetchone() or (None,)
    cands = []
    if visit_id is not None:
        cands = [dict(x) for x in conn.execute(
            """SELECT p.name, vc.distance_m, vc.evidence FROM visit_place_candidates vc
               JOIN places p ON p.id = vc.place_id WHERE vc.visit_id = ?
               ORDER BY vc.distance_m LIMIT 6""", (visit_id,))]
    r["candidates"] = cands
    r["location"] = geolocate(conn, r["gps_lat"], r["gps_lon"]) if r["gps_lat"] is not None else None
    # Latest user labeling pass, so Back can show (and correct) prior labels.
    user = conn.execute(
        "SELECT field, value FROM labels WHERE media_id = ? AND source = 'user' ORDER BY id",
        (r["media_id"],),
    ).fetchall()
    r["user_category"] = None
    r["user_evidence"] = []
    for field, value in user:
        if field == "category":
            r["user_category"] = value
            r["user_evidence"] = []
        elif field == "evidence":
            r["user_evidence"].append(value)
    return r


def _counts(conn):
    (total,) = conn.execute("SELECT COUNT(*) FROM media_items").fetchone()
    (labeled,) = conn.execute("SELECT COUNT(DISTINCT media_id) FROM labels WHERE field = 'category'").fetchone()
    return labeled, total


def make_handler(conn):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                body = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path.startswith("/img/"):
                media_id = int(self.path.split("/")[2].split(".")[0])
                (h,) = conn.execute("SELECT content_hash FROM media_items WHERE id = ?", (media_id,)).fetchone()
                f = ensure_preview(h)
                etag = f'"{h}-{f.stat().st_size}"'
                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self.end_headers()
                    return
                body = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                self.send_header("ETag", etag)
                self.end_headers()
                self.wfile.write(body)
            elif self.path.startswith("/api/item/"):
                media_id = int(self.path.split("/")[3])
                row = conn.execute(_ITEM_SQL + " WHERE m.id = ?", (media_id,)).fetchone()
                labeled, total = _counts(conn)
                if row is None:
                    self._json({"item": None, "labeled": labeled, "total": total})
                    return
                self._json({"item": _build_item(conn, row), "labeled": labeled, "total": total})
            elif self.path.startswith("/api/next"):
                from urllib.parse import parse_qs, urlparse

                qs = parse_qs(urlparse(self.path).query)
                exclude = [x for x in qs.get("exclude", [""])[0].split(",") if x.strip().isdigit()]
                q = _queue(conn, exclude)
                labeled, total = _counts(conn)
                if not q:
                    self._json({"item": None, "labeled": labeled, "total": total})
                    return
                self._json({"item": _build_item(conn, q[0]), "labeled": labeled, "total": total})
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path != "/api/label":
                self.send_error(404)
                return
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            mid = int(data["media_id"])
            conn.execute("INSERT INTO labels (media_id, field, value, source) VALUES (?, 'category', ?, 'user')",
                         (mid, data["category"]))
            for ev in data.get("evidence", []):
                conn.execute("INSERT INTO labels (media_id, field, value, source) VALUES (?, 'evidence', ?, 'user')",
                             (mid, str(ev).strip().lower()))
            for dish in data.get("dishes", []):
                conn.execute("INSERT INTO labels (media_id, field, value, source) VALUES (?, 'dish', ?, 'user')",
                             (mid, dish))
            if data.get("place"):
                conn.execute("INSERT INTO labels (media_id, field, value, source) VALUES (?, 'place', ?, 'user')",
                             (mid, data["place"]))
            conn.commit()
            self._json({"ok": True})

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8765):
    conn = db.connect(config.DB_PATH)
    db.init_schema(conn)
    HTTPServer((host, port), make_handler(conn)).serve_forever()
