"""Overlay a retimed screen recording (e.g. a chat with a Muse agent) onto part
of a rendered clip, as a floating panel, without zooming the background.

Config (JSON, kept in git-ignored demo/video/):
  {"base": "demo/video/intro.video.mp4", "out": "demo/video/intro.overlay.mp4",
   "source": "<screen recording>", "crop": [0, 864, 1874, 900], "blur_top": 0.45, "blur_until": 21.3,
   "width": 820, "pos": [1052, 70], "fade": 0.4,
   "map": [[41.6, 3.0], [42.0, 3.0], [48.4, 20.6], [49.6, 21.3], [51.0, 22.7]]}

- `map` pairs (output time, source time); between pairs the source plays at the
  implied speed, so typing can be fitted to the narration. Outside the first and
  last output times the base clip is untouched.
- `crop` is x, y, w, h in the source; `blur_top` blurs that fraction of the crop
  (older messages that should not be read) until source time `blur_until`
  (e.g. the moment the new message is sent). The panel gets rounded corners
  and a drop shadow and fades in over `fade` seconds.

Usage: python3 demo/tools/overlay_chat.py demo/video/overlay.json
"""

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W, H, FPS = 1920, 1080, 30


def frames(path, vf=None):
    args = ["ffmpeg", "-loglevel", "error", "-i", path, "-vf", vf or f"scale={W}:{H},fps={FPS}",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    return subprocess.Popen(args, stdout=subprocess.PIPE)


def src_time(m, t):
    for (t0, s0), (t1, s1) in zip(m, m[1:]):
        if t0 <= t <= t1:
            return s0 + (s1 - s0) * ((t - t0) / (t1 - t0) if t1 > t0 else 0)
    return m[-1][1]


def main(cfg_path):
    c = json.loads(Path(cfg_path).read_text())
    m = c["map"]
    t_in, t_out = m[0][0], m[-1][0]
    x, y, cw, ch = c["crop"]
    pw = c["width"]
    ph = round(ch * pw / cw)
    px, py = c["pos"]
    radius = 22

    # Decode the needed source span once, cropped and scaled, at a fine time step.
    s_lo, s_hi = min(s for _, s in m), max(s for _, s in m)
    step = 1 / 60
    src = frames(c["source"], f"trim={s_lo}:{s_hi + 0.1},setpts=PTS-STARTPTS,fps=60,crop={cw}:{ch}:{x}:{y},scale={pw}:{ph}")
    clip = []
    while True:
        buf = src.stdout.read(pw * ph * 3)
        if len(buf) < pw * ph * 3:
            break
        clip.append(Image.frombytes("RGB", (pw, ph), buf))
    src.wait()

    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=radius, fill=255)
    shadow = Image.new("L", (pw + 80, ph + 80), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([40, 48, pw + 40, ph + 48], radius=radius, fill=150)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    blur_h = round(ph * c.get("blur_top", 0))

    base = frames(c["base"])
    out = Path(c["out"])
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(out)],
                           stdin=subprocess.PIPE)
    k = 0
    while True:
        buf = base.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        t = k / FPS
        k += 1
        if t_in <= t <= t_out and clip:
            frame = Image.frombytes("RGB", (W, H), buf)
            i = min(len(clip) - 1, max(0, round((src_time(m, t) - s_lo) / step)))
            panel = clip[i].copy()
            if blur_h and src_time(m, t) < c.get("blur_until", 1e9):
                panel.paste(panel.crop((0, 0, pw, blur_h)).filter(ImageFilter.GaussianBlur(10)), (0, 0))
            a = min(1.0, (t - t_in) / c.get("fade", 0.4))
            frame.paste((0, 0, 0), (px - 40, py - 40), shadow.point(lambda v: int(v * a)))
            frame.paste(panel, (px, py), mask.point(lambda v: int(v * a)))
            buf = frame.tobytes()
        enc.stdin.write(buf)
    enc.stdin.close()
    enc.wait()
    print(f"{out} ({k / FPS:.2f}s), overlay {t_in}-{t_out}s")


if __name__ == "__main__":
    main(sys.argv[1])
