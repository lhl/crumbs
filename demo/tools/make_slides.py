"""Render the demo video's model and results slides to 1920x1080 PNGs.

Every number here comes from MODELS.md (measured on our hardware, with the
worklog entries cited there); keep the two in sync. Output goes to the
git-ignored demo/video/slides/ directory.

Usage: python3 demo/tools/make_slides.py demo/video/slides
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CSS = """
* { box-sizing: border-box; margin: 0; }
body { width: 1920px; height: 1080px; background: #fbf8f3; color: #1b1b1b;
  font-family: 'Inter', 'Noto Sans', system-ui, sans-serif; padding: 72px 96px; }
h1 { font-size: 58px; font-weight: 800; letter-spacing: -0.5px; }
h1 .accent { color: #e63946; }
.sub { font-size: 26px; color: #6b6b6b; margin-top: 10px; }
table { border-collapse: collapse; width: 100%; margin-top: 36px; font-size: 27px; }
th { text-align: left; font-size: 19px; text-transform: uppercase; letter-spacing: 1.2px; color: #8a8a8a;
  font-weight: 700; padding: 0 18px 14px; border-bottom: 2px solid #1b1b1b; }
td { padding: 20px 18px; border-bottom: 1px solid #e3ddd3; vertical-align: middle; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.m { font-weight: 700; }
.role { display: block; font-size: 20px; color: #777; font-weight: 400; margin-top: 4px; }
.chip { display: inline-block; font-size: 16px; font-weight: 700; padding: 4px 10px; border-radius: 999px;
  margin-left: 10px; vertical-align: 3px; letter-spacing: .5px; }
.live { background: #e63946; color: #fff; }
.tested { background: #e9e4dc; color: #555; }
code { font-family: 'JetBrains Mono', 'Noto Sans Mono', monospace; font-size: 25px; background: #efe9df;
  padding: 2px 8px; border-radius: 6px; }
.foot { position: absolute; left: 96px; right: 96px; bottom: 56px; font-size: 19px; color: #8a8a8a; line-height: 1.5; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 72px; margin-top: 8px; }
.cols h2 { font-size: 30px; margin-top: 34px; }
.cols h2 small { font-weight: 400; color: #8a8a8a; font-size: 21px; display: block; margin-top: 4px; }
.cols table { font-size: 24px; margin-top: 18px; }
.cols td { padding: 14px 10px; white-space: nowrap; }
.cols th { padding: 0 12px 10px; font-size: 16px; }
tr.hl td { background: #fde8e9; }
.bar { display: inline-block; height: 14px; background: #e63946; border-radius: 7px; vertical-align: middle; margin-right: 12px; }
.bar.grey { background: #c9c1b5; }
.note { margin-top: 22px; font-size: 21px; color: #555; background: #f1ece4; border-radius: 12px; padding: 16px 20px; line-height: 1.45; }
"""

MODELS = f"""<html><head><style>{CSS}</style></head><body>
<h1>Open <span class="accent">Meta</span> models, on my own hardware</h1>
<div class="sub">Everything below runs locally on an AMD Strix Halo box (Radeon 8060S, 128 GB unified memory)</div>
<table>
<tr><th>Model</th><th class="num">Parameters</th><th class="num">Size (GB)</th><th>Precision</th><th>License</th></tr>
<tr><td><span class="m">Muse Glimmer 30B</span><span class="chip live">IN PIPELINE</span>
  <span class="role">Classifies photos, reads menus &amp; signs, plans Ask lookups</span></td>
  <td class="num">30B</td><td class="num">19.8</td><td><code>Q4_K_M</code> GGUF</td><td>Apache 2.0</td></tr>
<tr><td><span class="m">DINOv3 ViT-L/16</span><span class="chip live">IN PIPELINE</span>
  <span class="role">Photo embeddings: near-duplicates and similarity</span></td>
  <td class="num">303M</td><td class="num">1.21</td><td><code>FP32</code></td><td>DINOv3 License</td></tr>
<tr><td><span class="m">SAM 3.1</span><span class="chip tested">TESTED</span>
  <span class="role">Masks for signs, menus, receipts, dishes</span></td>
  <td class="num">848M</td><td class="num">1.68</td><td><code>BF16</code></td><td>SAM License</td></tr>
<tr><td><span class="m">PE-Core L14-336</span><span class="chip tested">TESTED</span>
  <span class="role">Zero-shot photo labels · parameters are the vision encoder</span></td>
  <td class="num">0.32B</td><td class="num">2.6</td><td><code>FP32</code></td><td>Apache 2.0</td></tr>
<tr><td><span class="m">PE-Core G14-448</span><span class="chip tested">TESTED</span>
  <span class="role">Zero-shot photo labels, large · parameters are the vision encoder</span></td>
  <td class="num">1.88B</td><td class="num">9.1</td><td><code>FP32</code></td><td>Apache 2.0</td></tr>
</table>
</body></html>"""


def bar(v, top=1.0, grey=False, width=110):
    return f'<span class="bar{" grey" if grey else ""}" style="width:{round(width * v / top)}px"></span>'


RESULTS = f"""<html><head><style>{CSS}</style></head><body>
<h1>Accuracy &amp; speed</h1>
<div class="cols">
<div>
<h2>Food photo F1<small>61 hand-verified food photos (from a 440-photo labeled sample)</small></h2>
<table>
<tr><th>Model</th><th>Setup</th><th></th><th class="num">F1</th></tr>
<tr class="hl"><td class="m">Muse Glimmer</td><td><code>Q4_K_M</code> · Strix Halo</td><td>{bar(0.976)}</td><td class="num">0.976</td></tr>
<tr><td class="m">Muse Glimmer</td><td><code>FP8</code> · PRO 6000</td><td>{bar(0.930)}</td><td class="num">0.930</td></tr>
<tr><td class="m">Muse Glimmer (Decision)</td><td>AnyJev</td><td>{bar(0.877)}</td><td class="num">0.877</td></tr>
<tr><td>Shisa DE-2.1 <span class="role" style="display:inline">(comparator)</span></td><td><code>Q4_K_M</code> local</td><td>{bar(0.893, grey=True)}</td><td class="num">0.893</td></tr>
<tr><td class="m">PE-Core G14</td><td>zero-shot</td><td>{bar(0.545)}</td><td class="num">0.545</td></tr>
<tr><td class="m">PE-Core L14</td><td>zero-shot</td><td>{bar(0.526)}</td><td class="num">0.526</td></tr>
</table>
<div class="note"><b>Side quest:</b> Glimmer as a decision model with AnyJev-style restricted reads, no training:
JevBench <b>76.6%</b> (raw read, 231 items) · Decision Index 0.3 skill <b>32.60</b>. Not leaderboard submissions.</div>
</div>
<div>
<h2>Seconds per photo<small>Strix Halo APU (1024 px) vs a 4× RTX PRO 6000 box (mostly 640 px)</small></h2>
<table>
<tr><th>Pass</th><th class="num">Strix Halo</th><th class="num">PRO 6000</th></tr>
<tr><td class="m">Glimmer read &amp; classify</td><td class="num">19.4</td><td class="num">0.30</td></tr>
<tr><td class="m">Glimmer decision read</td><td class="num">2.69</td><td class="num">0.19</td></tr>
<tr><td class="m">SAM 3.1, 5 prompts</td><td class="num">2.83</td><td class="num">0.24</td></tr>
<tr><td class="m">PE-Core L14 zero-shot</td><td class="num">0.14</td><td class="num">—</td></tr>
<tr><td class="m">DINOv3 ViT-L embedding</td><td class="num">0.049</td><td class="num">—</td></tr>
<tr><td class="m">Ask agent, one question</td><td class="num">17–80</td><td class="num">—</td></tr>
</table>
<div class="note">Whole library (9,669 photos) classified on the PRO 6000 box in ~12 min. Glimmer at <code>Q4_K_M</code> is 19.8 GB on disk; the other models are 1.2–9.1 GB.</div>
</div>
</div>
</body></html>"""


GEO_CSS = """
.flow { display: grid; grid-template-columns: 1fr 70px 1fr 70px 0.8fr; align-items: center; margin-top: 46px; }
.col h3 { font-size: 19px; text-transform: uppercase; letter-spacing: 1.2px; color: #8a8a8a; margin-bottom: 14px; }
.box { background: #fff; border: 1px solid #e3ddd3; border-radius: 14px; padding: 16px 20px; margin-bottom: 14px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.box b { font-size: 25px; display: block; }
.box span { font-size: 19px; color: #6b6b6b; display: block; margin-top: 3px; }
.box .n { color: #e63946; font-weight: 700; }
.box.next { background: transparent; border: 2px dashed #c9c1b5; box-shadow: none; }
.box.next b { color: #8a8a8a; }
.box.out { background: #1b1b1b; border-color: #1b1b1b; }
.box.out b { color: #fff; } .box.out span { color: #bdb6ab; }
.arrow { font-size: 54px; color: #e63946; text-align: center; font-weight: 300; }
"""

GEO = f"""<html><head><style>{CSS}{GEO_CSS}</style></head><body>
<h1>Location data</h1>
<div class="flow">
<div class="col"><h3>Sources</h3>
  <div class="box"><b>Photo EXIF</b><span>GPS + timestamps · <span class="n" style="display:inline">8,205</span> of 9,669 photos geotagged</span></div>
  <div class="box"><b>Location history</b><span>Wanderings GeoJSON · <span class="n" style="display:inline">25,165</span> points, 2018–2026</span></div>
  <div class="box"><b>OpenStreetMap</b><span>Place registry (1,619 places, cached) · local PMTiles basemap</span></div>
  <div class="box"><b>GeoNames</b><span>Offline reverse geocoding</span></div>
  <div class="box next"><b>Next: check-ins, itineraries, health activity</b><span>Each source is its own import</span></div>
</div>
<div class="arrow">→</div>
<div class="col"><h3>Crumbs builds</h3>
  <div class="box"><b>Visits &amp; trips</b><span><span class="n" style="display:inline">590</span> visits in 20 trips</span></div>
  <div class="box"><b>Stays</b><span><span class="n" style="display:inline">554</span> dwell stays from location history</span></div>
  <div class="box"><b>Time-zone fixes</b><span>8,166 photos matched to the track</span></div>
  <div class="box"><b>Place candidates</b><span>6,502 ranked by GPS distance + sign text · 335 review questions</span></div>
</div>
<div class="arrow">→</div>
<div class="col"><h3>You get</h3>
  <div class="box out"><b>Globe &amp; heatmap</b><span>Fully local map, zero external requests</span></div>
  <div class="box out"><b>Ask answers</b><span>Every place with its evidence</span></div>
</div>
</div>
</body></html>"""


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/chromium")
        page = b.new_page(viewport={"width": 1920, "height": 1080})
        for name, html in (("models", MODELS), ("results", RESULTS), ("geo", GEO)):
            page.set_content(html)
            page.wait_for_timeout(300)
            page.screenshot(path=str(out / f"{name}.png"))
            print(out / f"{name}.png")
        b.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo/video/slides")
