#!/usr/bin/env python3
"""Sample photos evenly across each month of a YYYY/MM/DD photo tree.

Reads EXIF via exiftool (batch JSON) and copies a systematic sample
(evenly spaced over the month's chronologically sorted photos, so trip
bursts and quiet weeks are represented in proportion) into a destination
tree mirroring MM/DD, plus a manifest.csv and summary.json.

Personal data tool: destination must be an ignored directory (e.g. data/).
No file content leaves the machine; the manifest records paths and EXIF.

Usage:
  python3 scripts/sample_corpus.py --source /path/to/YYYY --dest data/sample-2019 --per-month 40
"""

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

IMAGE_EXTS = {".heic", ".jpg", ".jpeg", ".png"}


def exif_for(files):
    """Batch-read EXIF for a list of files via exiftool JSON output."""
    if not files:
        return {}
    cmd = [
        "exiftool", "-json", "-n",
        "-DateTimeOriginal", "-CreateDate", "-GPSLatitude", "-GPSLongitude",
        "-Model", "-ImageWidth", "-ImageHeight", "-FileModifyDate",
    ] + [str(f) for f in files]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    rows = json.loads(out)
    return {r["SourceFile"]: r for r in rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, help="Year directory (YYYY) containing MM/DD folders")
    ap.add_argument("--dest", required=True, help="Destination (ignored) directory")
    ap.add_argument("--per-month", type=int, default=40)
    args = ap.parse_args()

    source, dest = Path(args.source), Path(args.dest)
    if not source.is_dir():
        sys.exit(f"source not found: {source}")
    dest.mkdir(parents=True, exist_ok=True)

    manifest_rows, summary = [], {}
    for month_dir in sorted(p for p in source.iterdir() if p.is_dir()):
        files = sorted(
            f for f in month_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS
        )
        exif = exif_for(files)

        def sort_key(f):
            r = exif.get(str(f), {})
            return r.get("DateTimeOriginal") or r.get("CreateDate") or r.get("FileModifyDate") or f.name

        files.sort(key=sort_key)
        n = min(args.per_month, len(files))
        if len(files) <= n:
            picked = files
        else:
            step = len(files) / n
            picked = [files[int(i * step)] for i in range(n)]

        with_dt = sum(1 for f in picked if exif.get(str(f), {}).get("DateTimeOriginal"))
        with_gps = sum(1 for f in picked if exif.get(str(f), {}).get("GPSLatitude") is not None)
        for f in picked:
            r = exif.get(str(f), {})
            rel = f.relative_to(month_dir)
            out_path = dest / month_dir.name / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out_path)
            manifest_rows.append({
                "month": month_dir.name, "dest": str(out_path), "source": str(f),
                "datetime_original": r.get("DateTimeOriginal", ""),
                "gps_lat": r.get("GPSLatitude", ""), "gps_lon": r.get("GPSLongitude", ""),
                "model": r.get("Model", ""), "width": r.get("ImageWidth", ""), "height": r.get("ImageHeight", ""),
            })
        summary[month_dir.name] = {
            "photos_in_source": len(files), "sampled": len(picked),
            "sample_with_datetime": with_dt, "sample_with_gps": with_gps,
        }
        print(f"{month_dir.name}: {len(files)} photos -> sampled {len(picked)} (datetime {with_dt}, gps {with_gps})")

    with open(dest / "manifest.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest_rows[0].keys()))
        w.writeheader()
        w.writerows(manifest_rows)
    (dest / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    total = sum(s["sampled"] for s in summary.values())
    print(f"total sampled: {total} -> {dest}/ (+ manifest.csv, summary.json)")


if __name__ == "__main__":
    main()
