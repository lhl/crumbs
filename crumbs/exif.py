"""Batch EXIF reads via exiftool (one process per directory tree)."""

import json
import subprocess
from pathlib import Path

TAGS = [
    "-DateTimeOriginal", "-CreateDate", "-GPSLatitude", "-GPSLongitude",
    "-Model", "-ImageWidth", "-ImageHeight", "-OffsetTimeOriginal",
]


def read_exif(files: list[Path]) -> dict[str, dict]:
    """Return {str(path): exif-dict} for the given files (numeric GPS)."""
    if not files:
        return {}
    cmd = ["exiftool", "-json", "-n", *TAGS, *[str(f) for f in files]]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return {row["SourceFile"]: row for row in json.loads(out)}
