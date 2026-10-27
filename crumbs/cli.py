"""Crumbs pipeline CLI: one subcommand per stage (PLAN section 7).

  crumbs init-db
  crumbs import-photos <root> [--scope TEXT]
  crumbs stats
Stages grow here as they are implemented (embed, group, classify, export).
"""

import argparse
from pathlib import Path

from . import config, db


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="crumbs", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="create the SQLite schema")
    p_imp = sub.add_parser("import-photos", help="import a photo tree (IMP-01)")
    p_imp.add_argument("root")
    p_imp.add_argument("--scope", default="")
    sub.add_parser("stats", help="row counts per table")
    sub.add_parser("embed", help="DINOv3-embed all imported photos (EMB-01)")
    p_sim = sub.add_parser("similar", help="near-duplicate pairs from embeddings")
    p_sim.add_argument("--threshold", type=float, default=0.98)

    args = ap.parse_args(argv)
    conn = db.connect(config.DB_PATH)
    db.init_schema(conn)

    if args.cmd == "init-db":
        print(f"schema ready at {config.DB_PATH}")
    elif args.cmd == "import-photos":
        from .importer import import_photos

        root = Path(args.root).expanduser()
        stats = import_photos(conn, root, args.scope or f"photos from {root.name}")
        print("import:", stats)
    elif args.cmd == "embed":
        from .embed import embed_all

        print("embed:", embed_all(conn))
    elif args.cmd == "similar":
        from .embed import similarity_report

        report = similarity_report(conn, args.threshold)
        pairs = report.pop("pairs")
        print("similar:", report, f"| {len(pairs)} pairs")
        for a, b, s in pairs[:25]:
            print(f"  media {a} ~ {b}  cos={s}")
    elif args.cmd == "stats":
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ):
            (n,) = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()
            print(f"{name:18} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
