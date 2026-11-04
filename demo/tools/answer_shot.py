"""The demo video's answer shot: the real Crumbs answer, with camera moves.

capture: runs the question for real in the PWA (`?demo=1`, Glimmer agent on),
  waits for Glimmer's answer, expands the lookup trace, and saves a 2x
  screenshot plus the boxes of the answer, each trace line, and the first
  evidence card. Retries until the answer contains `expect` (the agent's
  wording varies between runs).
render: animates crops of that screenshot between keyframes, outlines the
  element in focus, and can cut to a zoom into one evidence photo (e.g. the
  sign the agent read). Nothing on screen is drawn except the outline; the
  text, trace, and photos are the app's own output.

Config (personal data; keep it in git-ignored demo/video/), e.g.:
  {"question": "...", "expect": "...", "map": {"center": [135.77, 35.0], "zoom": 6.5},
   "t0": 135.0, "t1": 148.8,
   "keys": [{"t": 135.0, "focus": "full"}, {"t": 137.4, "focus": "trace0"},
            {"t": 139.3, "focus": "trace1"}, {"t": 140.9, "focus": "card"},
            {"t": 142.3, "photo": 1, "box": null}, {"t": 143.4, "photo": 1, "box": [520, 615, 930, 768]},
            {"t": 146.6, "focus": "answer"}],
   "photo": 1, "blur_media": [2]}

Usage:
  python3 demo/tools/answer_shot.py capture demo/video/answer.json demo/video/answer
  python3 demo/tools/answer_shot.py render  demo/video/answer.json demo/video/answer [--audio demo/video/audio.wav]
"""

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

W, H, FPS, SCALE = 1920, 1080, 30, 2
APP = "http://localhost:5173/?demo=1"
ACCENT = (230, 57, 70)


def capture(cfg, out):
    from playwright.sync_api import sync_playwright

    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--use-gl=swiftshader"])
        for attempt in range(1, 4):
            page = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=SCALE)
            page.goto(APP, wait_until="networkidle")
            page.wait_for_function("window.__spikeMap && window.__spikeMap.loaded()", timeout=60000)
            if cfg.get("map"):
                page.evaluate("(m) => window.__spikeMap.jumpTo(m)", cfg["map"])
            page.fill("#ask-q", cfg["question"])
            page.click("#ask-btn")
            page.wait_for_selector(".agent-trace", timeout=300000)
            answer = page.inner_text(".ask-summary")
            print(f"attempt {attempt}: {answer[:160]}", flush=True)
            if cfg.get("expect", "") in answer:
                break
            page.close()
        else:
            raise SystemExit("no answer contained the expected text")
        page.click(".agent-trace summary")
        for mid in cfg.get("blur_media", []):  # privacy: people in photos are blurred in the video
            page.evaluate("(m) => document.querySelectorAll(`img[data-media='${m}']`).forEach(i => { i.style.filter = 'blur(10px)'; i.parentElement.style.overflow = 'hidden'; })", mid)
        page.wait_for_function("[...document.querySelectorAll('.ask-card img')].every(i => i.complete && i.naturalWidth > 0)",
                               timeout=30000)
        page.evaluate("new Promise(r => { const m = window.__spikeMap; m.once('idle', r); m.triggerRepaint(); setTimeout(r, 5000); })")
        page.wait_for_timeout(500)
        boxes = page.evaluate("""() => {
            const box = (el) => { const r = el.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; };
            const out = { answer: box(document.querySelector('.ask-summary')), card: box(document.querySelector('.ask-card')),
                          thumbs: box(document.querySelector('.ask-card .thumbs')), panel: box(document.getElementById('panel')) };
            document.querySelectorAll('.agent-trace > div').forEach((d, i) => { out['trace' + i] = box(d); });
            return out; }""")
        page.screenshot(path=str(out / "still.png"))
        (out / "boxes.json").write_text(json.dumps({"boxes": boxes, "answer": answer}, ensure_ascii=False, indent=1))
        print(f"saved {out / 'still.png'} with boxes {sorted(boxes)}")
        b.close()


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def fit(box, pad=40, min_w=640):
    """A 16:9 crop (CSS px) around a box, padded, never narrower than min_w."""
    x, y, w, h = box
    cw = min(W, max(min_w, w + 2 * pad, (h + 2 * pad) * W / H))  # never larger than the frame
    ch = cw * H / W
    cx, cy = x + w / 2, y + h / 2
    cx = min(max(cx, cw / 2), W - cw / 2)
    cy = min(max(cy, ch / 2), H - ch / 2)
    return [cx - cw / 2, cy - ch / 2, cw, ch]


def render(cfg, out, audio=None):
    still = Image.open(out / "still.png").convert("RGB")
    meta = json.loads((out / "boxes.json").read_text())
    boxes = meta["boxes"] | {"full": [0, 0, W, H]}
    photo = None
    if cfg.get("photo"):
        from crumbs import config, db

        conn = db.connect(config.DB_PATH)
        h = conn.execute("SELECT content_hash FROM media_items WHERE id = ?", (cfg["photo"],)).fetchone()[0]
        photo = Image.open(config.ANALYSIS_DIR / f"{h}.jpg").convert("RGB")

    keys = cfg["keys"]

    def view(k):
        if "focus" in k:
            target = boxes[k["focus"]]
            return ("app", fit(target, pad=k.get("pad", 40), min_w=k.get("min_w", 640)), target)
        box = k.get("box") or [0, 0, photo.width, photo.height]
        return ("photo", box, k.get("box"))

    def draw(kind, crop):
        src_w, src_h = (W, H) if kind == "app" else photo.size
        w, h = min(crop[2], src_w), min(crop[3], src_h)
        x, y = min(max(crop[0], 0), src_w - w), min(max(crop[1], 0), src_h - h)
        if kind == "app":
            return still.resize((W, H), Image.LANCZOS, box=(x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE))
        s = min(W / w, H / h)  # letterbox the photo crop, keeping its aspect ratio
        fitted = photo.resize((round(w * s), round(h * s)), Image.LANCZOS, box=(x, y, x + w, y + h))
        img = Image.new("RGB", (W, H), (17, 17, 17))
        img.paste(fitted, ((W - fitted.width) // 2, (H - fitted.height) // 2))
        return img

    def frame_at(t):
        i = max([j for j, k in enumerate(keys) if k["t"] <= t] or [0])
        cur, prev = keys[i], keys[max(i - 1, 0)]
        (kc, cc, oc), (kp, cp, _) = view(cur), view(prev)
        f = ease((t - cur["t"]) / cur.get("move", 0.8)) if i > 0 else 1.0
        if kc == kp:  # pan/zoom between two views of the same source
            crop = [cp[n] + (cc[n] - cp[n]) * f for n in range(4)]
            img = draw(kc, crop)
        else:  # cut between app and photo: crossfade
            crop = cc
            img = draw(kc, cc)
            if f < 1:
                img = Image.blend(draw(kp, cp), img, f)
        if kc == "app" and cur.get("focus") != "full" and f > 0.5:
            ox, oy, ow, oh = oc
            x, y, w, h = crop
            sx, sy = W / w, H / h
            pad = 8
            ImageDraw.Draw(img).rounded_rectangle(
                [(ox - x) * sx - pad, (oy - y) * sy - pad, (ox - x + ow) * sx + pad, (oy - y + oh) * sy + pad],
                radius=14, outline=ACCENT, width=5)
        return img

    n = round((cfg["t1"] - cfg["t0"]) * FPS)
    video = out / "answer.video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(video)],
                           stdin=subprocess.PIPE)
    for k in range(n):
        enc.stdin.write(frame_at(cfg["t0"] + k / FPS).tobytes())
    enc.stdin.close()
    enc.wait()
    print(f"video: {video} ({n / FPS:.1f}s)")
    if audio:
        prev = out / "answer.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-ss", str(cfg["t0"]), "-t", f"{n / FPS:.2f}",
                        "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(prev)],
                       check=True)
        print(f"preview with voiceover: {prev}")


if __name__ == "__main__":
    cmd, cfg_path, out_dir = sys.argv[1:4]
    cfg = json.loads(Path(cfg_path).read_text())
    audio = sys.argv[sys.argv.index("--audio") + 1] if "--audio" in sys.argv else None
    {"capture": lambda: capture(cfg, Path(out_dir)), "render": lambda: render(cfg, Path(out_dir), audio)}[cmd]()
