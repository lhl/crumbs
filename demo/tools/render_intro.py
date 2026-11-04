"""Render the demo video's opening: a grid of food photos, then a swipe up
into the captured globe shot.

- Food photos are those whose latest classification is "food", read from the
  local analysis images (never committed). They fill the grid in time order;
  tiles pop in at random, then the grid slowly zooms in.
- At --swipe seconds the grid slides up and the globe frames (from
  capture_globe.py) slide in from below, then play out.
- Writes video-only and a preview with the voiceover muxed in, both in the
  git-ignored demo/video/ directory.

Usage:
  python3 demo/tools/render_intro.py --globe demo/video/frames/globe \\
      --audio demo/video/audio.wav --out demo/video/intro.mp4 --swipe 30.3
"""

import argparse
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageFilter

from crumbs import config, db

W, H, FPS = 1920, 1080, 30


def food_photos(conn):
    return [r[0] for r in conn.execute(
        """SELECT m.content_hash FROM media_items m
           JOIN classifications c ON c.id = (SELECT MAX(id) FROM classifications WHERE media_id = m.id)
           WHERE json_extract(c.labels_json, '$.category') = 'food' ORDER BY m.captured_at, m.id""")]


def tile(content_hash, size):
    im = Image.open(config.ANALYSIS_DIR / f"{content_hash}.jpg")
    im.draft("RGB", (size * 2, size * 2))
    im = im.convert("RGB")
    s = min(im.size)
    left, top = (im.width - s) // 2, (im.height - s) // 2
    return im.crop((left, top, left + s, top + s)).resize((size, size), Image.LANCZOS)


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--globe", required=True, help="directory of globe frames (00000.jpg ...)")
    ap.add_argument("--audio", help="voiceover wav to mux into a preview")
    ap.add_argument("--out", required=True)
    ap.add_argument("--swipe", type=float, default=30.3, help="seconds: grid slides up here")
    ap.add_argument("--swipe-dur", type=float, default=0.8)
    ap.add_argument("--cols", type=int, default=64)
    ap.add_argument("--rows", type=int, default=36)
    ap.add_argument("--popin", type=float, default=3.5, help="seconds for all tiles to appear")
    ap.add_argument("--zoom", type=float, default=1.3, help="grid zoom reached at the swipe")
    ap.add_argument("--zoom-start", type=float, default=None, help="seconds: hold the full grid until here (default: end of pop-in)")
    ap.add_argument("--blur", type=float, nargs=3, metavar=("START", "FULL", "RADIUS"), default=None,
                    help="seconds and px: blur ramps from START to FULL, reaching RADIUS")
    ap.add_argument("--fade", type=float, nargs=3, metavar=("START", "FULL", "LEVEL"), default=None,
                    help="seconds: brightness ramps down from START to FULL, ending at LEVEL (0-1)")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    conn = db.connect(config.DB_PATH)
    hashes = food_photos(conn)
    n = a.cols * a.rows
    if len(hashes) > n:  # even sample across time, keeping time order
        hashes = [hashes[round(i * (len(hashes) - 1) / (n - 1))] for i in range(n)]
    print(f"{len(hashes)} food photos for a {a.cols}x{a.rows} grid")

    # 2x canvas so the zoom stays sharp; 1 px gutter at output scale.
    cell = 2 * W // a.cols
    canvas_w, canvas_h = cell * a.cols, cell * a.rows
    tiles = [tile(h, cell - 2) for h in hashes]
    rng = random.Random(a.seed)
    appear = [rng.random() * (a.popin - 0.3) for _ in tiles]
    full = Image.new("RGB", (canvas_w, canvas_h), (17, 17, 17))
    for i, t in enumerate(tiles):
        full.paste(t, ((i % a.cols) * cell + 1, (i // a.cols) * cell + 1))

    def grid_frame(t):
        if t < a.popin:
            img = Image.new("RGB", (canvas_w, canvas_h), (17, 17, 17))
            for i, tl in enumerate(tiles):
                f = ease((t - appear[i]) / 0.3)
                if f <= 0:
                    continue
                x, y = (i % a.cols) * cell + 1, (i // a.cols) * cell + 1
                if f < 1:
                    s = max(2, round((cell - 2) * (0.6 + 0.4 * f)))
                    o = (cell - 2 - s) // 2
                    img.paste(tl.resize((s, s)), (x + o, y + o))
                else:
                    img.paste(tl, (x, y))
        else:
            img = full
        z0 = a.popin if a.zoom_start is None else a.zoom_start
        z = 1 + (a.zoom - 1) * ease((t - z0) / max(0.1, a.swipe - z0))
        cw, ch = canvas_w / z, canvas_h / z
        left, top = (canvas_w - cw) / 2, (canvas_h - ch) / 2
        out = img.resize((W, H), Image.LANCZOS, box=(left, top, left + cw, top + ch))
        if a.blur:
            r = a.blur[2] * ease((t - a.blur[0]) / max(0.1, a.blur[1] - a.blur[0]))
            if r > 0.3:
                out = out.filter(ImageFilter.GaussianBlur(r))
        if a.fade:
            level = 1 - (1 - a.fade[2]) * ease((t - a.fade[0]) / max(0.1, a.fade[1] - a.fade[0]))
            if level < 1:
                out = Image.blend(Image.new("RGB", (W, H), (17, 17, 17)), out, level)
        return out

    globe = sorted(Path(a.globe).glob("*.jpg"))
    out = Path(a.out)
    video_only = out.with_name(out.stem + ".video.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                            "-crf", "18", "-pix_fmt", "yuv420p", str(video_only)], stdin=subprocess.PIPE)
    n_grid = round(a.swipe * FPS)
    n_swipe = round(a.swipe_dur * FPS)
    last_grid = None
    for k in range(n_grid):
        last_grid = grid_frame(k / FPS)
        enc.stdin.write(last_grid.tobytes())
        if k % 150 == 0:
            print(f"grid {k}/{n_grid}", flush=True)
    first_globe = Image.open(globe[0]).convert("RGB")
    for k in range(n_swipe):
        e = ease((k + 1) / n_swipe)
        frame = Image.new("RGB", (W, H))
        frame.paste(last_grid, (0, -round(H * e)))
        frame.paste(first_globe, (0, H - round(H * e)))
        enc.stdin.write(frame.tobytes())
    for g in globe:
        enc.stdin.write(Image.open(g).convert("RGB").tobytes())
    enc.stdin.close()
    enc.wait()
    total = (n_grid + n_swipe + len(globe)) / FPS
    print(f"video: {video_only} ({total:.1f}s)")
    if a.audio:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_only), "-i", a.audio, "-t", f"{total:.2f}",
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
        print(f"preview with voiceover: {out}")


if __name__ == "__main__":
    main()
