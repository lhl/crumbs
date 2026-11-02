# Crumbs — Model Inventory

Every model in the stack: size, precision, engine, memory, and measured per-item cost. This is the presentation reference; claims here must stay reproducible from worklog entries.

**Reference hardware (all measurements unless noted):** `zbook` — AMD Ryzen AI Max (Strix Halo), Radeon 8060S iGPU (gfx1151), 125 GB unified memory, CachyOS. Three identical Strix Halo APU boxes (Ryzen AI MAX+ 395, Radeon 8060S/gfx1151, 125 GB unified) are in use: `zbook` (Glimmer serving), `strixhalo` (SAM/PE runs), and `gfx1151` (DE-2.1 GGUF serving; offline since 2026-11-01, no physical access). A fourth machine, `dev` (4x RTX PRO 6000 Blackwell, 96 GB each, 219 GB RAM), has been used for Glimmer FP8 under vLLM and the fast Glimmer-DE read (0.03-0.5 s/read with prefix caching vs 2.69 s on llama.cpp); see worklog 20261101T150639. Replica start/stop state belongs in the latest worklog checkpoint, not this inventory. Models marked *planned* are design targets, not measurements; published figures for them are labeled as such. Last updated 2026-11-02.

## Measured and in use

| Model | Role in Crumbs | Params | Precision / quant | Disk (artifacts) | Runtime memory | Engine | Time per item (measured) |
|---|---|---|---|---|---|---|---|
| **Muse Glimmer 30B** (`meta-models/Muse-Glimmer-30B-GGUF`) | Triage classification and evidence extraction; Ask and visit reconciliation currently use deterministic code, not Glimmer | 30B dense multimodal | GGUF K-quant **Q4_K_M** (main) + Q4_K_M mmproj vision tower + Q4_K_M DFlash draft | 16.76 GB main + 1.40 GB mmproj + 1.63 GB dflash = **19.8 GB** | Server process RSS **≈11.9 GB** (weights memory-mapped; iGPU compute buffers draw from the same unified pool) | **llama.cpp** (HIP build, `llama-server`, `--jinja`, single slot) | Triage read: **19.4 s/photo** (1,131 prompt tok in, ~239 tok out; 19.3 tok/s generation, draft acceptance 0.61) — 440 photos in 2 h 22 min. Extraction read (selective, evidence photos): **≈30 s/photo** (67 in 34 min) |
| **DINOv3 ViT-L/16** (`dinov3-vitl16-pretrain-lvd1689m`, LVD-1689M) | Photo embeddings: similarity, dedup, grouping signal, retrieval | 303M | **fp32** as run (bf16/fp16 available) | **1.21 GB** safetensors | **≈1.4 GB** GPU-allocated (peak 1.46 GB at batch 8) | **PyTorch** via HF Transformers (ROCm/TheRock torch 2.13) | Forward ≈5 ms/img (224²); end-to-end pipeline **≈49 ms/photo** (440 in 21.5 s incl. image I/O) |
| **SAM 3.1** (`facebook/sam3.1`; dev checkpoint via `unsloth/sam3.1`) | Optional segmentation/cropping of signs, receipts, menus, dishes (E4 ablation) | 840M (848M published) | **bf16** | **1.68 GB** safetensors (FP8/INT8 third-party quants exist but do not load correctly without torchao wiring — see DISCOVERY E4) | **≈1.7 GB** weights, **≈2.2 GB** peak in forward (4.17 GB peak in the 5-prompt batch config on strixhalo) | **PyTorch** via HF Transformers (ROCm) | **≈0.5 s per text prompt** on a full-res photo after warmup (2.6 s first prompt); **2.83 s/photo for 5 prompts** (sign/menu/receipt/dish/storefront) at 1024 px over 440 photos on strixhalo (0 failures); visually verified masks on both zbook and strixhalo (checkpoint copied zbook → strixhalo `/models/sam3.1-unsloth`, md5-verified) |

Also cloned for reference on the processing box: `facebookresearch/sam3`, `facebookresearch/dinov3` (source repos, not runtimes).

## Strix Halo vs PRO 6000 (`dev`) — measured rates for the same passes

The `dev` box (4x RTX PRO 6000 Blackwell, 96 GB each) joined on 2026-11-01 as the fast serving machine. Rates below are per photo for the same model and task on both hardware classes; image size is stated where it differs, because vision-encoder cost scales with it.

| Pass | Strix Halo (APU, llama.cpp / ROCm PyTorch) | PRO 6000 (`dev`, vLLM / CUDA PyTorch) |
| --- | --- | --- |
| Glimmer generative triage | 19.4 s/photo (zbook, Q4_K_M GGUF, 1024 px, single slot) | ~0.30 s/photo per replica at c=16 (FP8, 640 px previews; 9,669 photos in ~12 min across 4 replicas). On the 440 labeled photos: food F1 0.930 vs the zbook run's 0.976 at equal recall (0.984); category agreement between the two runs 79.3%. Note: vLLM guided-JSON output intermittently pads to the token cap instead of stopping, so most dev outputs were recovered from the JSON prefix (category unaffected, evidence may truncate) |
| Glimmer-DE restricted read (640 px) | 2.69 s (zbook llama.cpp, single read) | 0.19 s at concurrency 1 (1024 px); ~12.7 photos/s aggregate at c=16 on 640 px previews across one replica — throughput is vision-encoder bound and flat in client concurrency (c=1..64 at 1024 px: 5.0-5.4 req/s) |
| SAM 3.1, 5 evidence prompts | 2.83 s (strixhalo, 1024 px) | ~0.24 s per server (640 px; 3 servers on GPU1-3 aggregate ~12.6 photos/s) |
| PE-Core-L14 zero-shot | 0.116-0.138 s (strixhalo, batch 32) | single-image smoke only (2.9 s including load); no batch rate yet |
| DINOv3 ViT-L embedding | ~0.049 s (zbook/strixhalo) | not measured |

Reading: for reading-style passes the PRO 6000 under vLLM is roughly 10-35x the Strix Halo rate, with the multiplier set by how much of the cost is vision encoding versus generation. The Strix Halo boxes remain the always-on local pipeline machines; `dev` is burst capacity that is spun up per pass and pulled down after.

## The Glimmer speculative-decoding note

Glimmer has **no integrated MTP head**. Its speed companion is the separate **DFlash draft model** (1.63 GB Q4_K_M GGUF above; 4.8 GiB in bf16 as `meta-models/Muse-Glimmer-30B-assistant`), driven by llama.cpp `--spec-type draft-dflash`. Measured draft acceptance: 0.61 median on the triage read (0.13 under 4-way slot contention — single slot is the right configuration on this APU; details in the triage worklog).

## Comparators, measured experiments, and planned upgrades

| Model | Intended role | Published size (not our measurement) | Precision / engine planned | Status |
|---|---|---|---|---|
| Perception Encoder (PE-Core) | Zero-shot taxonomy classification + text-query image retrieval (E1 comparator vs DINOv3 head) | L14-336: 0.32B vision, 2.6 GB checkpoint; G14-448: 1.88B vision, 9.1 GB | Apache 2.0 weights; PyTorch via `perception_models` | **Measured 2026-11-01 on strixhalo over 440 photos: L = 0.138 s/photo (3.72 GB peak), G = 1.882 s/photo (13.10 GB peak); category agreement with Glimmer 44.3% (L) / 43.2% (G). On the owner-verified food slice (61 photos): F1 0.526 (L) / 0.545 (G), recall limited by the argmax unknown prompt; see worklogs 20261101T095719 and 20261101T133805** |
| Shisa DE-2.1 (comparator, not shipped) | Restricted-readout decision model (Gemma 4 26B A4B + LoRA soup, Apache 2.0): the pattern reference for a future Glimmer-DE; also an E1/E2b comparator | 25.8B BF16 (51.6 GB); Q4_K_M GGUF 16.8 GB + F16 mmproj 1.2 GB | Hosted Shisa API and llama.cpp GGUF (latest build, gfx1151 box) | **Both arms measured 2026-11-01 over 440 photos, 9 questions/photo: API (development-only, photos sent to the API by lead decision) 2.89 s/photo wall at 4 concurrent, Glimmer agreement 68.0%; local GGUF on gfx1151 8.47 s/photo sequential single-slot, Glimmer agreement 66.1%, agreement with the API arm 92.5% (quantization delta small). On the owner-verified food slice (61 photos): F1 0.898 (API) / 0.893 (local, precision 0.980); see worklog 20261101T133805** |
| Perception Language Model (PLM-3B / 8B) | High-volume extraction comparator; possible Glimmer-DE distillation target (System-1) | 3B / 8B class | FAIR Research License; PyTorch (HF) | Not run yet (EXT-02, GDE-07) |
| Glimmer-DE, no-training restricted read | One-token category decisions from base Glimmer logprobs; not a trained or calibrated DE model | Base Glimmer 30B; no adapter | Q4_K_M/llama.cpp and FP8/vLLM | **Measured:** 440-photo raw read at 2.69 s/photo on zbook; food F1 0.877. Full dev run: 9,669 unique corpus photos, zero recorded errors, all imported as `glimmer-de` / `fp8-vllm-rawread-640`. JevBench public 231-item run: raw 177/231 (76.62%, 4.0 s), cyclic option-rotation averaging 171/231 (74.03%, 17.5 s), both zero errors. This is a custom restricted-read scaffold, not an official leaderboard submission. Decision Index is tracked separately in the worklog. |
| Glimmer-DE training/calibration upgrade | Proposed calibrated decision layer: LoRA on Glimmer + restricted-logprob readout | Base = Glimmer above + proposed LoRA adapter (rank 16) | LoRA (Axolotl/TRL), vision tower frozen; readout via llama.cpp/vLLM logprobs | Feasibility and no-training corpus reads are complete; LoRA training, held-out calibration, and calibrated escalation policy remain unbuilt. Do not describe raw option mass as calibrated confidence. |
| Muse Glimmer bf16 on RTX PRO 6000 | Reference-hardware serving arm (vLLM vs SGLang) | bf16 ≈60 GB weights, ≈72 GB VRAM to serve (vendor figures) | bf16; vLLM/SGLang (CUDA) | Deferred by lead decision (GLM-01/02); the zbook triage numbers above are the comparison baseline |
| SeamlessM4T v2 / MMS | Local ASR for voice input (would remove the cloud voice exception) | ~2.3B (v2 large) | CC BY-NC 4.0; PyTorch | Probe only (VOI-01) |

## Non-model components (for the same slide)

| Component | What | Cost |
|---|---|---|
| exiftool + ImageMagick | EXIF read; HEIC→1024 px analysis JPEG | ~0.3 s/photo conversion; import of 440 photos in ~72 s total |
| SQLite evidence store | All records, embeddings (fp32 BLOB), places, stays | 440 photos → analysis images 66 MB; DB well under 100 MB at this scale |
| Protomaps PMTiles (local) | Offline basemap: globe z0–5 + regional extracts | 15 MB planet backdrop + 40 MB demo regions + 15 MB fonts (fetched, never committed) |
| Overpass (OSM), dev only | Place-registry population, cached locally | 58 area queries ≈ 2,100 cached places; shipped path is PMTiles POI ingestion (no coordinates leave the device) |

## Operational and evidence limits

- The photo corpus contains 9,669 distinct media items. Both full Glimmer classification outputs cover all 9,669 hashes. SAM's 9,672-row dev output covers those same photos plus three auxiliary-frame artifacts; line count is not corpus size. PE currently covers 9,665 database media items, not the full corpus.
- Selective extraction is a separate generative pass, not implied by completed classification. It selects food/evidence photos from the latest generative classification; missing evidence types in recovered classification prefixes can leave non-food text photos unrouted. SAM-derived routing is not integrated.
- Dev inference is self-hosted on a separate machine. Photos/previews are transferred there; do not describe that development run as on-device processing. The earlier hosted DE-2.1 comparison also sent photos to an external model API by lead decision. Overpass development lookups reveal queried areas to that provider. Offline-map testing does not establish a network audit of the entire pipeline.
- Glimmer tool-calling readiness and voice transcription are separate checks. The current Ask implementation composes local records deterministically; neither a structured-output test nor a benchmark proves a shipped agentic loop or voice UI.

## Sources

Measurements: worklogs 20261027T203902 (Glimmer/zbook), 20261027T210818 (SAM/DINOv3), 20261027T214029 (embeddings), 20261028T002750 (triage rates), 20261028T043838 (places), 20261101T082831 (SAM batch), 20261101T095719 (PE/DE agreement). Catalog facts and license status: [DISCOVERY.md](DISCOVERY.md).
