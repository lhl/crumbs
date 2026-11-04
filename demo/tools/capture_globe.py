"""Capture the PWA globe shot for the demo video, frame by frame.

Drives the real app (`?demo=1`, local tiles, real heatmap) in headless
Chromium: each frame sets the camera, positions food callouts at the photos'
real map positions, optionally types the Ask question in sync with the
voiceover, waits for the map to render, and saves a JPEG. Frame-by-frame
capture keeps motion smooth even with software WebGL.

The shot config (photo ids, labels, timings) is personal data and lives in
the git-ignored demo/video/ directory. Example:

    {"t0": 31.1, "t1": 51.0, "fps": 30,
     "camera": [{"t": 31.1, "center": [150, 25], "zoom": 1.8},
                {"t": 41.0, "center": [128, 31], "zoom": 3.1}],
     "callouts": [{"t": 32.5, "media_id": 1, "lon": 135.7, "lat": 35.0,
                   "label": "shaved ice", "sub": "Kyoto · Nov 2025", "dx": 1, "dy": -1, "out": 38.0}],
     "callouts_out": 41.0,
     "type": {"text": "...", "from": 42.0, "to": 48.5, "submit": 49.6}}

Usage: python3 demo/tools/capture_globe.py demo/video/globe.json demo/video/frames/globe
Needs: Vite dev server (spike/map-globe) and `crumbs serve` for photo previews.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = "http://localhost:5173/?demo=1"
API = "http://127.0.0.1:8770"

OVERLAY_CSS = """
#callouts { position: absolute; inset: 0; pointer-events: none; z-index: 5; }
.co { position: absolute; transition: none; }
.co .dot { position: absolute; width: 14px; height: 14px; margin: -7px 0 0 -7px; border-radius: 50%;
  background: #e63946; border: 3px solid #fff; box-shadow: 0 1px 4px rgba(0,0,0,.4); }
.co svg { position: absolute; left: 0; top: 0; overflow: visible; }
.co .card { position: absolute; width: 190px; background: #fff; border-radius: 10px; padding: 6px;
  box-shadow: 0 6px 22px rgba(0,0,0,.28); font: 600 15px/1.25 system-ui, sans-serif; color: #111; }
.co .card img { width: 178px; height: 178px; object-fit: cover; border-radius: 6px; display: block; }
.co .card .l { margin: 6px 2px 0; }
.co .card .s { margin: 1px 2px 2px; font-weight: 400; font-size: 13px; color: #666; }
"""


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def camera_at(keys, t):
    if t <= keys[0]["t"]:
        return keys[0]["center"], keys[0]["zoom"]
    for a, b in zip(keys, keys[1:]):
        if t <= b["t"]:
            f = ease((t - a["t"]) / (b["t"] - a["t"]))
            c = [a["center"][i] + (b["center"][i] - a["center"][i]) * f for i in (0, 1)]
            return c, a["zoom"] + (b["zoom"] - a["zoom"]) * f
    return keys[-1]["center"], keys[-1]["zoom"]


def main(config_path, out_dir):
    cfg = json.loads(Path(config_path).read_text())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fps = cfg.get("fps", 30)
    n = round((cfg["t1"] - cfg["t0"]) * fps)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--use-gl=swiftshader"])
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(APP, wait_until="networkidle")
        page.wait_for_function("window.__spikeMap && window.__spikeMap.loaded()", timeout=60000)
        page.add_style_tag(content=OVERLAY_CSS)
        page.evaluate("""([api, callouts]) => {
            const box = document.createElement('div'); box.id = 'callouts';
            document.getElementById('map').appendChild(box);
            for (const [i, c] of callouts.entries()) {
              const el = document.createElement('div'); el.className = 'co'; el.id = 'co' + i; el.style.opacity = 0;
              el.innerHTML = `<svg width="1" height="1"><line stroke="#e63946" stroke-width="3"/></svg><div class="dot"></div>
                <div class="card"><img src="${api}/v1/media/${c.media_id}/preview"><div class="l"></div><div class="s"></div></div>`;
              el.querySelector('.l').textContent = c.label; el.querySelector('.s').textContent = c.sub || '';
              box.appendChild(el);
            }
        }""", [API, cfg.get("callouts", [])])
        page.wait_for_function("[...document.querySelectorAll('#callouts img')].every(i => i.complete && i.naturalWidth > 0)",
                               timeout=30000)
        typing = cfg.get("type")
        submitted = False
        for k in range(n):
            t = cfg["t0"] + k / fps
            center, zoom = camera_at(cfg["camera"], t)
            states = []
            for c in cfg.get("callouts", []):
                a = ease((t - c["t"]) / 0.5) * (1 - ease((t - c.get("out", cfg.get("callouts_out", 1e9))) / 0.6))
                states.append({"lon": c["lon"], "lat": c["lat"], "a": a, "dx": c.get("dx", 1), "dy": c.get("dy", -1)})
            text = None
            if typing and t >= typing["from"]:
                f = min(1.0, (t - typing["from"]) / (typing["to"] - typing["from"]))
                text = typing["text"][: round(len(typing["text"]) * f)]
            page.evaluate("""async ([center, zoom, states, text]) => {
                const m = window.__spikeMap;
                m.jumpTo({ center, zoom });
                states.forEach((s, i) => {
                  const el = document.getElementById('co' + i);
                  const pt = m.project([s.lon, s.lat]);
                  const ox = s.dx * 120, oy = s.dy * 150;
                  el.style.opacity = s.a;
                  el.style.left = pt.x + 'px'; el.style.top = pt.y + 'px';
                  const card = el.querySelector('.card');
                  const cx = ox - (s.dx < 0 ? 202 : 0), cy = oy - (s.dy < 0 ? 230 : 0);
                  card.style.left = cx + 'px'; card.style.top = cy + 'px';
                  card.style.transform = `scale(${0.85 + 0.15 * s.a})`;
                  const line = el.querySelector('line');
                  line.setAttribute('x1', 0); line.setAttribute('y1', 0);
                  line.setAttribute('x2', ox); line.setAttribute('y2', oy);
                });
                if (text !== null) document.getElementById('ask-q').value = text;
                await new Promise((r) => { m.once('idle', r); m.triggerRepaint(); setTimeout(r, 4000); });
            }""", [center, zoom, states, text])
            if typing and not submitted and t >= typing.get("submit", 1e9):
                page.click("#ask-btn")
                submitted = True
            page.screenshot(path=str(out / f"{k:05d}.jpg"), type="jpeg", quality=92)
            if k % 60 == 0:
                print(f"frame {k}/{n}", flush=True)
        browser.close()
    print(f"{n} frames -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
