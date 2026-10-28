# Crumbs — Model Inventory

Every model in the stack: size, precision, engine, memory, and measured per-item cost. This is the presentation reference; claims here must stay reproducible from worklog entries.

**Reference hardware (all measurements unless noted):** `zbook` — AMD Ryzen AI Max (Strix Halo), Radeon 8060S iGPU (gfx1151), 125 GB unified memory, CachyOS. Models marked *planned* are design targets, not measurements; published figures for them are labeled as such. Last updated 2026-10-28.

## Measured and in use

| Model | Role in Crumbs | Params | Precision / quant | Disk (artifacts) | Runtime memory | Engine | Time per item (measured) |
|---|---|---|---|---|---|---|---|
| **Muse Glimmer 30B** (`meta-models/Muse-Glimmer-30B-GGUF`) | Triage classification, evidence extraction, visit reconciliation, agent reasoning | 30B dense multimodal | GGUF K-quant **Q4_K_M** (main) + Q4_K_M mmproj vision tower + Q4_K_M DFlash draft | 16.76 GB main + 1.40 GB mmproj + 1.63 GB dflash = **19.8 GB** | Server process RSS **≈11.9 GB** (weights memory-mapped; iGPU compute buffers draw from the same unified pool) | **llama.cpp** (HIP build, `llama-server`, `--jinja`, single slot) | Triage read: **19.4 s/photo** (1,131 prompt tok in, ~239 tok out; 19.3 tok/s generation, draft acceptance 0.61) — 440 photos in 2 h 22 min. Extraction read (selective, evidence photos): **≈30 s/photo** (67 in 34 min) |
| **DINOv3 ViT-L/16** (`dinov3-vitl16-pretrain-lvd1689m`, LVD-1689M) | Photo embeddings: similarity, dedup, grouping signal, retrieval | 303M | **fp32** as run (bf16/fp16 available) | **1.21 GB** safetensors | **≈1.4 GB** GPU-allocated (peak 1.46 GB at batch 8) | **PyTorch** via HF Transformers (ROCm/TheRock torch 2.13) | Forward ≈5 ms/img (224²); end-to-end pipeline **≈49 ms/photo** (440 in 21.5 s incl. image I/O) |
| **SAM 3.1** (`facebook/sam3.1`; dev checkpoint via `unsloth/sam3.1`) | Optional segmentation/cropping of signs, receipts, menus, dishes (E4 ablation) | 840M (848M published) | **bf16** | **1.68 GB** safetensors (FP8/INT8 third-party quants exist but do not load correctly without torchao wiring — see DISCOVERY E4) | **≈1.7 GB** weights, **≈2.2 GB** peak in forward | **PyTorch** via HF Transformers (ROCm) | **≈0.5 s per text prompt** on a full-res photo after warmup (2.6 s first prompt); visually verified masks |

Also cloned for reference on the processing box: `facebookresearch/sam3`, `facebookresearch/dinov3` (source repos, not runtimes).

## The Glimmer speculative-decoding note

Glimmer has **no integrated MTP head**. Its speed companion is the separate **DFlash draft model** (1.63 GB Q4_K_M GGUF above; 4.8 GiB in bf16 as `meta-models/Muse-Glimmer-30B-assistant`), driven by llama.cpp `--spec-type draft-dflash`. Measured draft acceptance: 0.61 median on the triage read (0.13 under 4-way slot contention — single slot is the right configuration on this APU; details in the triage worklog).

## Planned / not yet measured

| Model | Intended role | Published size (not our measurement) | Precision / engine planned | Status |
|---|---|---|---|---|
| Perception Encoder (PE-Core) | Zero-shot taxonomy classification + text-query image retrieval (E1 comparator vs DINOv3 head) | Checkpoint-dependent (Tiny→Giant) | Apache 2.0 weights; PyTorch | Not run yet (EMB-02) |
| Perception Language Model (PLM-3B / 8B) | High-volume extraction comparator; possible Glimmer-DE distillation target (System-1) | 3B / 8B class | FAIR Research License; PyTorch (HF) | Not run yet (EXT-02, GDE-07) |
| Glimmer-DE (ours to build) | Calibrated System-1 decision layer: LoRA on Glimmer + restricted-logprob readout | Base = Glimmer above + LoRA adapter (rank 16) | LoRA (Axolotl/TRL), vision tower frozen; readout via llama.cpp/vLLM logprobs | Feasibility probes not run yet (GDE-01); per-photo prefill (~1,131 tok at ~88 tok/s full-res, ~20 s at 1024 px) is the cost to design around |
| Muse Glimmer bf16 on RTX PRO 6000 | Reference-hardware serving arm (vLLM vs SGLang) | bf16 ≈60 GB weights, ≈72 GB VRAM to serve (vendor figures) | bf16; vLLM/SGLang (CUDA) | Deferred by lead decision (GLM-01/02); the zbook triage numbers above are the comparison baseline |
| SeamlessM4T v2 / MMS | Local ASR for voice input (would remove the cloud voice exception) | ~2.3B (v2 large) | CC BY-NC 4.0; PyTorch | Probe only (VOI-01) |

## Non-model components (for the same slide)

| Component | What | Cost |
|---|---|---|
| exiftool + ImageMagick | EXIF read; HEIC→1024 px analysis JPEG | ~0.3 s/photo conversion; import of 440 photos in ~72 s total |
| SQLite evidence store | All records, embeddings (fp32 BLOB), places, stays | 440 photos → analysis images 66 MB; DB well under 100 MB at this scale |
| Protomaps PMTiles (local) | Offline basemap: globe z0–5 + regional extracts | 15 MB planet backdrop + 40 MB demo regions + 15 MB fonts (fetched, never committed) |
| Overpass (OSM), dev only | Place-registry population, cached locally | 58 area queries ≈ 2,100 cached places; shipped path is PMTiles POI ingestion (no coordinates leave the device) |

## Sources

Measurements: worklogs 20261027T203902 (Glimmer/zbook), 20261027T210818 (SAM/DINOv3), 20261027T214029 (embeddings), 20261028T002750 (triage rates), 20261028T043838 (places). Catalog facts and license status: [DISCOVERY.md](DISCOVERY.md).
