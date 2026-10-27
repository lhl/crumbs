"""Photo importer (IMP-01): scan a tree, hash-dedupe, record EXIF facts,
and render downscaled analysis JPEGs that local models can read.

Originals are never modified or copied. Analysis images (long edge 1024 px)
are the only derived media, written under CRUMBS_DATA_DIR/analysis/<hash>.jpg.
HEIC and every other source format go through ImageMagick, which the dev and
processing boxes both have; EXIF comes from exiftool in batch.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

from . import config, db
from .exif import read_exif

IMAGE_EXTS = {".heic", ".jpg", ".jpeg", ".png"}


def content_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_analysis_image(src: Path, dest: Path) -> bool:
    if dest.exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["magick", str(src), "-auto-orient", "-resize", "1024x1024>", "-quality", "85", str(dest)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"warn: analysis image failed for {src}: {r.stderr.strip()[:160]}", file=sys.stderr)
        return False
    return True


def import_photos(conn, root: Path, scope: str) -> dict:
    files = sorted(
        f for f in root.rglob("*") if f.is_file() and f.suffix.lower() in IMAGE_EXTS
    )
    exif = read_exif(files)
    cur = conn.execute(
        "INSERT INTO source_imports (kind, scope, source_ref) VALUES ('photos', ?, ?)",
        (scope, str(root)),
    )
    import_id = cur.lastrowid
    stats = {"scanned": len(files), "inserted": 0, "duplicate": 0, "analysis_failed": 0}
    for f in files:
        digest = content_hash(f)
        row = exif.get(str(f), {})
        captured = row.get("DateTimeOriginal") or row.get("CreateDate")
        if captured:  # exiftool mixes '2019:01:02 13:29:49' and ISO; normalize date part
            captured = captured[:10].replace(":", "-") + captured[10:]
        try:
            conn.execute(
                """INSERT INTO media_items
                   (content_hash, source_path, rel_path, captured_at, captured_at_source,
                    gps_lat, gps_lon, camera_model, width, height, import_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    digest, str(f), str(f.relative_to(root)), captured,
                    "exif" if captured else "none",
                    row.get("GPSLatitude"), row.get("GPSLongitude"),
                    row.get("Model"), row.get("ImageWidth"), row.get("ImageHeight"),
                    import_id,
                ),
            )
            stats["inserted"] += 1
        except Exception as e:
            if "UNIQUE" in str(e):
                stats["duplicate"] += 1
            else:
                raise
        if not make_analysis_image(f, config.ANALYSIS_DIR / f"{digest}.jpg"):
            stats["analysis_failed"] += 1
    conn.commit()
    return stats
