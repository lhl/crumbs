"""Assemble the demo video on the voiceover's timeline.

Timeline (JSON, kept in git-ignored demo/video/) lists contiguous segments:
  {"audio": "demo/video/audio.wav", "out": "demo/video/crumbs-demo.mp4", "tail": 1.0,
   "segments": [
     {"video": "demo/video/intro.video.mp4", "dur": 51.0},
     {"still": "demo/video/slides/models.png", "dur": 29.0, "zoom": [1.0, 1.04]},
     {"still": "demo/video/slides/results.png", "dur": 8.5, "crop": [[0, 0, 1920, 1080], [10, 541, 1000, 562.5]]},
     ...]}

- video: the clip from its start, trimmed or held on its last frame to `dur`.
- still: an image with a slow push-in (`zoom` [from, to], centered) or an eased
  pan between two crops (`crop`, x/y/w/h in image pixels).
- The last segment fades to black over `tail` extra seconds; the voiceover is
  muxed from 0 and padded with silence to the video's length.

Usage: python3 demo/tools/assemble.py demo/video/timeline.json
"""

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

W, H, FPS = 1920, 1080, 30


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def still_frames(seg, n):
    img = Image.open(seg["still"]).convert("RGB")
    iw, ih = img.size
    if "crop" in seg:
        a, b = seg["crop"]
        hold = seg.get("move", 1.2) * FPS
        for k in range(n):
            f = ease(k / hold)
            x, y, w, h = (a[i] + (b[i] - a[i]) * f for i in range(4))
            yield img.resize((W, H), Image.LANCZOS, box=(x, y, x + w, y + h))
    else:
        z0, z1 = seg.get("zoom", [1.0, 1.0])
        for k in range(n):
            z = z0 + (z1 - z0) * (k / max(1, n - 1))
            w, h = iw / z, ih / z
            x, y = (iw - w) / 2, (ih - h) / 2
            yield img.resize((W, H), Image.LANCZOS, box=(x, y, x + w, y + h))


def video_frames(seg, n):
    raw = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", seg["video"], "-vf", f"scale={W}:{H},fps={FPS}",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    last = None
    for _ in range(n):
        buf = raw.stdout.read(W * H * 3)
        if len(buf) == W * H * 3:
            last = Image.frombytes("RGB", (W, H), buf)
        yield last  # holds the last frame if the clip is shorter than `dur`
    raw.stdout.close()
    raw.kill()


def main(timeline_path):
    t = json.loads(Path(timeline_path).read_text())
    out = Path(t["out"])
    video = out.with_name(out.stem + ".video.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                            "-pix_fmt", "yuv420p", str(video)], stdin=subprocess.PIPE)
    total = 0
    segs = t["segments"]
    tail = round(t.get("tail", 0) * FPS)
    for i, seg in enumerate(segs):
        n = round(seg["dur"] * FPS)
        last = i == len(segs) - 1
        frames = still_frames(seg, n + (tail if last else 0)) if "still" in seg else video_frames(seg, n + (tail if last else 0))
        for k, fr in enumerate(frames):
            if last and k >= n - FPS // 2:  # fade to black over the final half second of narration + tail
                fr = Image.blend(fr, Image.new("RGB", (W, H)), ease((k - (n - FPS // 2)) / (FPS // 2 + tail)))
            enc.stdin.write(fr.tobytes())
        total += n + (tail if last else 0)
        print(f"{total / FPS:7.2f}s  {seg.get('video') or seg.get('still')}", flush=True)
    enc.stdin.close()
    enc.wait()
    dur = total / FPS
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", t["audio"], "-filter_complex",
                    f"[1:a]apad,atrim=0:{dur:.3f}[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", str(out)], check=True)
    print(f"{out} ({dur:.2f}s)")


if __name__ == "__main__":
    main(sys.argv[1])
