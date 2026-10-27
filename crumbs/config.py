"""Runtime configuration from environment, with repo-local defaults.

CRUMBS_DATA_DIR  - ignored directory holding the local database and derived
                   images (default: <repo>/data/crumbs)
CRUMBS_DB        - explicit SQLite path (default: CRUMBS_DATA_DIR/crumbs.db)
GLIMMER_URL      - llama-server base URL for classification/extraction
DINOV3_MODEL     - local DINOv3 checkpoint directory (embedding stage)
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("CRUMBS_DATA_DIR", REPO_ROOT / "data" / "crumbs"))
DB_PATH = Path(os.environ.get("CRUMBS_DB", DATA_DIR / "crumbs.db"))
ANALYSIS_DIR = DATA_DIR / "analysis"  # downscaled copies models actually read
GLIMMER_URL = os.environ.get("GLIMMER_URL", "http://127.0.0.1:18080")
DINOV3_MODEL = os.environ.get("DINOV3_MODEL", "")
