"""Runtime configuration from environment, with repo-local defaults.

CRUMBS_DATA_DIR  - ignored directory holding the local database and derived
                   images (default: <repo>/data/crumbs)
CRUMBS_DB        - explicit SQLite path (default: CRUMBS_DATA_DIR/crumbs.db)
GLIMMER_URL      - llama-server base URL for classification/extraction
GLIMMER_MODEL    - when set, requests carry this model id and the vLLM
                   json_schema dialect (for an OpenAI-compatible vLLM
                   endpoint instead of llama.cpp); unset = llama.cpp
DINOV3_MODEL     - local DINOv3 checkpoint directory (embedding stage)
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("CRUMBS_DATA_DIR", REPO_ROOT / "data" / "crumbs"))
DB_PATH = Path(os.environ.get("CRUMBS_DB", DATA_DIR / "crumbs.db"))
ANALYSIS_DIR = DATA_DIR / "analysis"  # downscaled copies models actually read
GLIMMER_URL = os.environ.get("GLIMMER_URL", "http://127.0.0.1:18080")
GLIMMER_MODEL = os.environ.get("GLIMMER_MODEL", "")
GLIMMER_CHECKPOINT = GLIMMER_MODEL or "gguf-q4_k_m+mmproj"
DINOV3_MODEL = os.environ.get("DINOV3_MODEL", "")


def glimmer_body(messages, max_tokens: int, schema: dict) -> dict:
    """Chat-completions body for either server dialect (see GLIMMER_MODEL)."""
    body = {
        "messages": messages,
        "max_tokens": max_tokens, "temperature": 0.8, "top_p": 0.95, "top_k": 64,
        "chat_template_kwargs": {"reasoning_effort": "none"},
    }
    if GLIMMER_MODEL:
        body["model"] = GLIMMER_MODEL
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "crumbs", "schema": schema},
        }
    else:
        body["response_format"] = {"type": "json_schema", "schema": schema}
    return body
