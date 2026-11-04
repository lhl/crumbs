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
    sub.add_parser("group", help="deterministic visit/trip grouping (REC-01)")
    p_cls = sub.add_parser("classify", help="Glimmer classification pass (needs llama-server)")
    p_cls.add_argument("--workers", type=int, default=4)
    p_exp = sub.add_parser("export-spike", help="export visits/photos GeoJSON for spike/map-globe")
    p_exp.add_argument("--out", default="-")
    p_pf = sub.add_parser("places-fetch", help="fetch OSM places around food visits (REC-07, dev lookup)")
    p_pf.add_argument("--radius", type=int, default=300)
    p_nb = sub.add_parser("nearby", help="search cached places near a coordinate")
    p_nb.add_argument("--lat", type=float, required=True)
    p_nb.add_argument("--lon", type=float, required=True)
    p_nb.add_argument("--radius", type=int, default=500)
    p_nb.add_argument("--kind", default=None)
    p_ps = sub.add_parser("place-search", help="search cached places by name")
    p_ps.add_argument("text")
    p_loc = sub.add_parser("import-locations", help="import a Wanderings locations export (GeoJSON)")
    p_loc.add_argument("path")
    sub.add_parser("stays", help="derive dwell stays from location history")
    sub.add_parser("tz", help="estimate camera UTC offsets by matching photos to the track (IMP-03)")
    p_ext = sub.add_parser("extract", help="selective Glimmer extraction over evidence photos (EXT v1)")
    p_ext.add_argument("--workers", type=int, default=4)
    p_lab = sub.add_parser("label", help="run the local labeling helper UI (DAT-07)")
    p_lab.add_argument("--port", type=int, default=8765)
    p_lab.add_argument("--host", default="127.0.0.1",
                       help="bind address (use 0.0.0.0 to label from a phone at http://<this-host>:<port>/)")
    p_api = sub.add_parser("serve", help="local API for the PWA and Muse bridge (reads + review answers)")
    p_api.add_argument("--port", type=int, default=8770)
    p_api.add_argument("--host", default="127.0.0.1",
                       help="bind address; outside localhost requires CRUMBS_API_TOKEN")
    sub.add_parser("score", help="score model output against user labels (DAT-06)")
    sub.add_parser("reconcile", help="evidence-score visits and build the review queue (REC-02)")
    p_ask = sub.add_parser("ask", help="ask the local index a question (AGT v1)")
    p_ask.add_argument("question")
    p_ask.add_argument("--lat", type=float, default=None)
    p_ask.add_argument("--lon", type=float, default=None)
    p_ask.add_argument("--agent", action="store_true", help="let Muse Glimmer (GLIMMER_URL) plan tool calls")
    sub.add_parser("demo", help="build the local demo manifest + sufficiency verdict (DEM-01)")
    sub.add_parser("correlate", help="cross-correlate photo visits with location stays")

    args = ap.parse_args(argv)
    if args.cmd == "serve":
        from .api import serve as api_serve

        print(f"Starting Crumbs API at http://{args.host}:{args.port}/v1/ (Ctrl-C to stop)")
        try:
            api_serve(host=args.host, port=args.port)
        except ValueError as e:
            ap.error(str(e))
        return 0

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
    elif args.cmd == "group":
        from .group import group_all

        print("group:", group_all(conn))
    elif args.cmd == "classify":
        from .classify import classify_all

        print("classify:", classify_all(conn, workers=args.workers))
    elif args.cmd == "export-spike":
        import json

        from .export_spike import export_geojson

        data = export_geojson(conn)
        text = json.dumps(data, ensure_ascii=False)
        if args.out == "-":
            print(text)
        else:
            Path(args.out).write_text(text)
            print(f"wrote {args.out}: {len(data['features'])} features, "
                  f"{len(data['visits'])} visits, {len(data['trips'])} trips")
    elif args.cmd == "places-fetch":
        from .places import fetch_candidates

        print("places-fetch:", fetch_candidates(conn, radius_m=args.radius))
    elif args.cmd == "nearby":
        from .places import nearby

        for p in nearby(conn, args.lat, args.lon, args.radius, args.kind):
            print(f"{p['distance_m']:7.0f} m  {p['kind'] or '?':10} {p['name']}  ({p['lat']:.5f}, {p['lon']:.5f}) [{p['source']}]")
    elif args.cmd == "place-search":
        from .places import search_name

        for p in search_name(conn, args.text):
            print(f"{p['kind'] or '?':10} {p['name']}  ({p['lat']:.5f}, {p['lon']:.5f}) [{p['source']}]")
    elif args.cmd == "import-locations":
        from .locations import import_wanderings

        print("import-locations:", import_wanderings(conn, Path(args.path)))
    elif args.cmd == "stays":
        from .locations import derive_stays

        print("stays:", derive_stays(conn))
    elif args.cmd == "tz":
        from .locations import estimate_timezones

        print("tz:", estimate_timezones(conn))
    elif args.cmd == "extract":
        from .extract import extract_all

        stats = extract_all(conn, workers=args.workers)
        print("extract:", stats)
        return 1 if stats["failed"] or stats["unattempted"] else 0
    elif args.cmd == "label":
        from .label_server import serve

        print(f"labeler at http://{args.host}:{args.port}/ (Ctrl-C to stop)")
        serve(host=args.host, port=args.port)
    elif args.cmd == "score":
        import json as _json

        from .score import score_all

        print(_json.dumps(score_all(conn), indent=2, ensure_ascii=False))
    elif args.cmd == "reconcile":
        from .reconcile import reconcile_all

        print("reconcile:", reconcile_all(conn))
    elif args.cmd == "ask":
        if args.agent:
            from .agent import run_agent

            result = run_agent(conn, args.question, lat=args.lat, lon=args.lon)
        else:
            from .ask import ask

            result = ask(conn, args.question, lat=args.lat, lon=args.lon)
        print(result["answer"])
        if args.agent:
            import json as _jsonlib

            from .ask import _card_line

            for card in result.get("results", []):
                print(_card_line(card))
            a = result.get("agent", {})
            for step in a.get("trace", []):
                if step["step"] == "tool":
                    print(f"  tool {step['tool']}({_jsonlib.dumps(step['args'], ensure_ascii=False)}) -> "
                          f"{step.get('error') or step.get('found')}")
            print("[agent:", {k: a.get(k) for k in ("used", "latency_s", "grounding", "error") if a.get(k) is not None}, "]")
        print("[evidence:", result["evidence"], "| status:", result["status"] + "]")
    elif args.cmd == "demo":
        from .demo import build_demo_manifest

        out = build_demo_manifest(conn)
        print("verdict:", out["verdict"])
        print("manifest written to data/demo/manifest.json (local only)")
    elif args.cmd == "correlate":
        from .locations import correlate

        print("correlate:", correlate(conn))
    elif args.cmd == "stats":
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ):
            (n,) = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()
            print(f"{name:18} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
