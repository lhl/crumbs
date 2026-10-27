"""SQLite evidence store.

Design rules from PLAN.md section 6 / AGENTS.md: source data is never
overwritten by derived data; every derived row names its model/algorithm and
is versioned (a re-run inserts new rows, it does not update in place);
provenance is explicit (`observed` for source facts, `inferred` for model or
algorithm output, `lookup`/`confirmed` reserved for later stages).

Only the entities the current pipeline stages need are implemented; the rest
of PLAN section 6 lands with its stage.
"""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_imports (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,             -- photos | foursquare | google
    scope TEXT NOT NULL,            -- human description of what was imported
    source_ref TEXT NOT NULL,       -- root path/dir the import scanned
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    provenance TEXT NOT NULL DEFAULT 'observed'
);
CREATE TABLE IF NOT EXISTS media_items (
    id INTEGER PRIMARY KEY,
    content_hash TEXT NOT NULL UNIQUE,   -- sha256 of file bytes
    source_path TEXT NOT NULL,           -- where the original lives (read-only)
    rel_path TEXT NOT NULL,
    captured_at TEXT,                    -- EXIF local datetime, may be NULL
    captured_at_source TEXT,             -- exif | filename | file_mtime
    gps_lat REAL, gps_lon REAL,
    camera_model TEXT,
    width INTEGER, height INTEGER,
    import_id INTEGER NOT NULL REFERENCES source_imports(id),
    provenance TEXT NOT NULL DEFAULT 'observed'
);
CREATE TABLE IF NOT EXISTS classifications (
    id INTEGER PRIMARY KEY,
    media_id INTEGER NOT NULL REFERENCES media_items(id),
    model TEXT NOT NULL,
    checkpoint TEXT NOT NULL,            -- quant/config string, e.g. gguf-q4_k_m
    labels_json TEXT NOT NULL,           -- {category, evidence_types, ...}
    raw_json TEXT,                       -- full model response for audit
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    provenance TEXT NOT NULL DEFAULT 'inferred'
);
CREATE TABLE IF NOT EXISTS embeddings (
    media_id INTEGER NOT NULL REFERENCES media_items(id),
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL,                -- little-endian float32
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (media_id, model)
);
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY,
    started_at TEXT, ended_at TEXT,
    center_lat REAL, center_lon REAL,
    photo_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'inferred',  -- inferred | confirmed | rejected
    created_by TEXT NOT NULL,            -- algorithm + params, e.g. group-v1(gap=6h)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    provenance TEXT NOT NULL DEFAULT 'inferred'
);
CREATE TABLE IF NOT EXISTS visit_media (
    visit_id INTEGER NOT NULL REFERENCES visits(id),
    media_id INTEGER NOT NULL REFERENCES media_items(id),
    PRIMARY KEY (visit_id, media_id)
);
CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY,
    name TEXT,
    started_at TEXT, ended_at TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    provenance TEXT NOT NULL DEFAULT 'inferred'
);
CREATE TABLE IF NOT EXISTS trip_visits (
    trip_id INTEGER NOT NULL REFERENCES trips(id),
    visit_id INTEGER NOT NULL REFERENCES visits(id),
    PRIMARY KEY (trip_id, visit_id)
);
CREATE INDEX IF NOT EXISTS idx_media_captured ON media_items(captured_at);
CREATE INDEX IF NOT EXISTS idx_class_media ON classifications(media_id);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
