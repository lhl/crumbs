"""DINOv3 embedding stage (EMB-01/05): embed every analysis image and store
float32 vectors in SQLite. Runs on the processing box (ROCm torch).

Model is env-selected (DINOV3_MODEL) so mirror/official checkpoints can be
swapped without code changes; the model string stored per row records which
checkpoint produced the vectors.
"""

import os
import struct
import time
from pathlib import Path

from . import config

MODEL_LABEL = "dinov3-vitl16-lvd1689m"  # keep in sync with DINOV3_MODEL used


def embed_all(conn, batch_size: int = 32) -> dict:
    import torch
    from PIL import Image
    from transformers import DINOv3ViTImageProcessor, DINOv3ViTModel

    model_dir = config.DINOV3_MODEL
    if not model_dir:
        raise SystemExit("DINOV3_MODEL env var must point at a local DINOv3 checkpoint")
    model = DINOv3ViTModel.from_pretrained(model_dir, dtype=torch.float32).to("cuda").eval()
    proc = DINOv3ViTImageProcessor.from_pretrained(model_dir)

    rows = conn.execute(
        """SELECT m.id, m.content_hash FROM media_items m
           LEFT JOIN embeddings e ON e.media_id = m.id AND e.model = ?
           WHERE e.media_id IS NULL ORDER BY m.id""",
        (MODEL_LABEL,),
    ).fetchall()
    done, t0 = 0, time.time()
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        # convert("RGB"): grayscale-source photos otherwise produce 1-channel
        # tensors and crash the batch stack (found on the 2025/2026 corpus).
        imgs = [Image.open(config.ANALYSIS_DIR / f"{r['content_hash']}.jpg").convert("RGB") for r in chunk]
        inputs = proc(images=imgs, return_tensors="pt").to("cuda")
        with torch.no_grad():
            out = model(**inputs).pooler_output.float().cpu()
        for r, vec in zip(chunk, out):
            blob = struct.pack(f"<{vec.numel()}f", *vec.tolist())
            conn.execute(
                "INSERT OR REPLACE INTO embeddings (media_id, model, dim, vector) VALUES (?, ?, ?, ?)",
                (r["id"], MODEL_LABEL, int(vec.numel()), blob),
            )
        conn.commit()
        done += len(chunk)
    dt = time.time() - t0
    return {"embedded": done, "seconds": round(dt, 1), "img_per_s": round(done / dt, 1) if dt else None}


def similarity_report(conn, threshold: float = 0.98) -> dict:
    """Near-duplicate / near-identical pairs by cosine similarity (dedup signal)."""
    import numpy as np

    rows = conn.execute(
        "SELECT media_id, vector FROM embeddings WHERE model = ? ORDER BY media_id", (MODEL_LABEL,)
    ).fetchall()
    ids = [r["media_id"] for r in rows]
    mat = np.stack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows])
    mat = mat / np.linalg.norm(mat, axis=1, keepdims=True)
    sims = mat @ mat.T
    pairs = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if sims[i, j] >= threshold:
                pairs.append((ids[i], ids[j], round(float(sims[i, j]), 4)))
    return {"vectors": len(ids), "threshold": threshold, "pairs": pairs}
