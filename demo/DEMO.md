# Crumbs — Demo Script (working draft)

Three minutes, Must-scope only, every beat backed by a working feature. Concrete record IDs live in the local demo manifest (`crumbs demo` → `data/demo/manifest.json`, ignored — it names the owner's real visits). This file stays generic so it can live in the public repo.

## Beats

1. **The problem (0:00–0:25).** Scrolling a camera roll, failing to name a restaurant from a food photo. Cut to the offline globe: clusters of real trips, rebuilt locally. *Feature: PWA-06 globe + real corpus export.*
2. **The pipeline, self-hosted (0:25–1:10).** Import → classify → group on screen with the model inventory beside it (MODELS.md): photos become categories, evidence, visits. Disclose whether inference uses a local APU or the separate dev GPU box, and whether cached place lookup data came from Overpass. The blocked-network globe test proves offline map rendering, not that every pipeline stage is network-free. Feature a visit combining visible text with nearby place candidates only after the current reconciliation verifies it. *Features: IMP-01, EMB, REC-01/02/07, EXT.*
3. **Ask (1:10–1:50).** Food-first: ask about a dish ("where did I have soup dumplings in <city>?") and get visit cards. Each card shows the date, the best place *with where that name came from* (you confirmed / sign text + GPS / nearby GPS candidate / text read in the photo), menu-read and seen dishes, and the evidence photos. Follow with "what did I have at <place>?" or "what did I eat in <city>?". *Feature: AGT v1.1 (`crumbs ask`, `/v1/ask`, PWA Ask panel cards).*
4. **Correction + honest unknown (1:50–2:25).** On a card with an open review question, press **Yes** (or **No**, or type a name). The card turns "✓ you confirmed" and later answers use it. The model's own resolution row is kept, not overwritten. Then ask about somewhere never visited ("have I been to <city>?") to show the designed unknown. *Features: REC-02 review answers (`POST /v1/review/<id>`), Ask unknowns.*
5. **Close on measurement (2:25–3:00).** The APU and dev rate tables (MODELS.md), plus the actual privacy boundary: self-hosted model inference, offline tiles where configured, development-only hosted comparison and Overpass calls disclosed. Do not claim that remote dev processing stayed on the importing device. *Features: MODELS.md, bridge tiers.*

## Measured results (presentation material, 2026-11-01)

All figures below were measured on the 440-photo sample on our own hardware and are reproducible from the worklog entries named in MODELS.md. Two kinds of numbers appear, and the distinction matters:

- **Speed** is measured directly (seconds per photo, wall clock).
- **Agreement** compares two systems against each other. It is not accuracy. Accuracy requires human ground truth, which exists so far only for the food category (last table).

### Speed: what each pass costs per photo

| Pass | Model | s/photo | Where it ran |
| --- | --- | ---: | --- |
| Embeddings | DINOv3 ViT-L/16 | 0.05 | strixhalo |
| Zero-shot classification | PE-Core-L14-336 | 0.14 | strixhalo |
| Zero-shot classification | PE-Core-G14-448 | 1.88 | strixhalo |
| Segmentation (5 prompts) | SAM 3.1 | 2.83 | strixhalo |
| Decision questions (9 per photo) | Shisa DE-2.1, hosted API | 2.89 (4 concurrent) | API (development only) |
| Decision questions (9 per photo) | Shisa DE-2.1, Q4_K_M GGUF | 8.47 (sequential) | gfx1151 box, llama.cpp |
| Triage classification | Muse Glimmer 30B | 19.4 | zbook, llama.cpp |
| Selective extraction | Muse Glimmer 30B | ~30 (evidence photos only) | zbook, llama.cpp |

These sample rates are historical APU measurements, not forecasts for the full run. The imported corpus now contains 9,669 distinct photos; both dev Glimmer classification passes cover it completely. Generative dev triage took about 12 minutes across four FP8 vLLM replicas using 640 px previews. That is a different quantization, resolution, and concurrency setup from the single-slot APU baseline; use MODELS.md for the caveats and measured food-quality difference. Selective extraction remains a separate pass whose completion is recorded in the latest worklog.

### Agreement between classifiers (category, 440 photos)

| Pair | Agree |
| --- | ---: |
| Glimmer ↔ DE-2.1 (API) | 68.0% |
| Glimmer ↔ DE-2.1 (local GGUF) | 66.1% |
| DE-2.1 local ↔ DE-2.1 API | 92.5% |
| Glimmer ↔ PE-Core-L14 / G14 | 44.3% / 43.2% |
| PE-L14 ↔ PE-G14 | 67.7% |
| All four systems | 25.5% |

Reading: the local Q4_K_M DE-2.1 build reproduces its hosted BF16 reference closely (92.5%), so quantization is not the accuracy bottleneck. PE's two sizes agree with each other far more than with either generative model, and the extra 13.6x compute of PE-G over PE-L buys no agreement. DE-2.1 abstains much more than Glimmer (category 'unknown' on 204 of 440 photos, vs 94).

### Accuracy on the verified food slice (61 photos)

The corpus owner labeled all 440 photos by hand. Outside food, most labels confirm the model's suggested default, so they cannot score the suggesting model fairly. The 61 food photos were individually verified, and on that slice the ranking is real:

| System | Recall | Precision | F1 |
| --- | ---: | ---: | ---: |
| Muse Glimmer (generative read) | 0.984 | 0.968 | 0.976 |
| Shisa DE-2.1 (hosted API) | 0.869 | 0.930 | 0.898 |
| Shisa DE-2.1 (local GGUF) | 0.820 | 0.980 | 0.893 |
| PE-Core-G14-448 (zero-shot) | 0.393 | 0.889 | 0.545 |
| PE-Core-L14-336 (zero-shot) | 0.410 | 0.735 | 0.526 |

PE's low recall is a calibration failure, not missing signal: its 'unknown' prompt wins the five-way argmax on most true-food photos, while food is still its top non-unknown category on 45 of 61. Thresholding the food probability at 0.1 lifts PE-L to F1 ≈ 0.64 — better, still below DE-2.1. One caveat applies to every recall in this table: a food photo that no system flagged, and the owner therefore never inspected, would be invisible here, so recalls are upper bounds.

## Full processing pipeline (as built)

This is the pipeline implemented in the `crumbs` package. It processed the sample corpus end to end; full-corpus stage completion and failures are recorded separately in the worklog. Every stage is a `crumbs` subcommand; stages with no model are deterministic code. The Ask parser and visit reconciliation are deterministic today, not a Glimmer agent loop.

| # | Stage | Command | Model / engine | Box |
| --- | --- | --- | --- | --- |
| 1 | Photo import | `import-photos` | exiftool (EXIF time/GPS) + ImageMagick (1024 px analysis copies); SHA-256 dedupe; originals untouched | strixhalo |
| 2 | Location import | `import-locations`, `stays`, `tz`, `correlate` | Wanderings location export → dwell stays, camera-timezone estimates, photo↔stay correlation | strixhalo |
| 3 | Embed | `embed` | DINOv3 ViT-L/16 (PyTorch/ROCm); vectors stored in SQLite | zbook / strixhalo |
| 4 | Classify | `classify` | Muse Glimmer 30B generated category/evidence JSON; original GGUF sample and full dev FP8 results retained with distinct checkpoint metadata. No-training restricted-read comparison results are also imported | zbook / dev |
| 5 | Group | `group` | Deterministic time/GPS grouping into visits and trips | any |
| 6 | Extract | `extract` | Glimmer long-form reads on selected food/evidence photos; full text transcription, dish and text-based place-name candidates; names matched to nearby registry places. Use `GLIMMER_MODEL` for vLLM and inspect failure/remaining counts | zbook / dev |
| 7 | Place candidates | `places-fetch`, `nearby`, `place-search` | OpenStreetMap Overpass at development time, cached in SQLite; per-visit candidates ranked check-in > signage text > GPS proximity | strixhalo |
| 8 | Reconcile | `reconcile` | Evidence scoring over visits; builds the review queue of targeted questions | any |
| 9 | Ask / serve | `ask`, `serve` | Deterministic intent parsing over the local index: dish/menu-text search, place and city food queries, designed unknowns. Answers are visit cards with place provenance, dishes, and evidence photos (served as stripped previews). The API is read-only except review answers, which are stored as separate user rows | strixhalo + zbook |
| 10 | Label / score | `label`, `score` | Human labeling UI (phone-friendly) and scoring of model output against those labels | strixhalo |

The initial pipeline ran on the Strix Halo boxes; full-corpus Glimmer/SAM work also transferred previews to the self-hosted `dev` GPU box. A hosted DE-2.1 comparison sent photos to an external model API by lead decision, and development Overpass lookups expose queried areas. These are not an on-device-only development history. Do not describe optional voice transcription as built: the current API has no transcription route.

## Comparative measurements on the original sample

These models were evaluated on the same 440 photos. Their sample results inform the proposed routing roles below. Full-corpus PE and Glimmer-DE outputs have since been imported, but that does not mean automatic confidence-based routing or SAM crop integration is implemented.

| Candidate | What we measured | Verdict |
| --- | --- | --- |
| SAM 3.1 (bf16, local) | Ran over all 440 photos with 5 evidence prompts (sign/menu/receipt/dish/storefront): 2.83 s/photo, 47.3% of photos hit at least one prompt; masks visually verified | Promising evidence pre-filter and crop source for extraction; not integrated — whether its crops improve Glimmer's reading (the EXT-04 test) is still unmeasured |
| PE-Core-L14-336 (zero-shot, local) | 0.138 s/photo; category agreement with Glimmer 44.3%; food F1 0.526 (unknown-prompt calibration failure; ≈0.64 with probability thresholding) | Fast enough to be the bulk first pass; needs thresholded probabilities, not argmax, and prompt work before it can route |
| PE-Core-G14-448 (zero-shot, local) | 1.882 s/photo (13.6x the L model); agreement and food F1 (0.545) essentially unchanged from L | Not used — the extra compute buys nothing on this taxonomy |
| Shisa DE-2.1 via hosted API | 9 decision questions per photo at 2.89 s/photo wall; category agreement with Glimmer 68.0%; food F1 0.898 | Best non-Glimmer classifier measured; development-only comparator (photos leave the machine), never a product component |
| Shisa DE-2.1 as local Q4_K_M GGUF | Same questions via llama.cpp on the gfx1151 box: 8.47 s/photo; 92.5% category agreement with the API build; food F1 0.893, best precision (0.980) | Proves a DE-style local classifier is practical and that quantization costs little; its role is the design pattern for a future Glimmer-DE, not a shipped dependency |
| DE-2.1 on hipEngine | hipEngine (our HIP inference engine) does have a Gemma 4 image tower (added 2026-10-23, validated on gfx1100) and leads llama.cpp on Gemma 4 text prefill (up to 1.59x at 512 tokens); but the DE GGUF's Q5_0 tensors are outside its loader's supported layouts, and the target box's disk was 98% full | Skipped for now by decision; revisit if a supported quantization is produced |
| Glimmer-DE, no-training (ours) | Raw restricted reads over all 440 (640 px, assistant-prefill scaffold): 2.69 s/read; food F1 0.877; full-category accuracy 0.814 (human 'other' mapped to model 'unknown'); accuracy rises with the answer-mass floor (mass ≥ 0.5: 40% coverage at 0.927) | Worth building as the bulk category classifier with mass-gated escalation to the generative read; LoRA training is now an upgrade to justify, not a prerequisite |
| DINOv3 classification head | Embeddings for all 440 exist, but a trained head needs labeled training data; labels only arrived 2026-11-01 | Open; similarity/dedup remains DINOv3's shipped job |
| Perception Language Model, PE-Lang/Spatial, Meta CLIP 2, SAM FP8 quant | Reviewed on paper in DISCOVERY.md; SAM's third-party FP8 checkpoint was load-tested and silently corrupts weights without torchao wiring | Not run — no measured reason to prefer them over the measured set; the FP8 quant is explicitly not used |

## How each model should be used (the measured assignment)

The built pipeline above uses Glimmer for every reading job. The measurements support a cheaper assignment, which is the direction for the next pipeline revision: each model takes the job its numbers justify, cheapest first, and slower stages run only where earlier ones say the photo earns it. This section is the target state; the two sections before it are what exists and what was evaluated to get here.

| Stage | Model | Job | Why this model |
| --- | --- | --- | --- |
| Embed | DINOv3 ViT-L/16 | One vector per photo for similarity, near-duplicates, retrieval | 0.05 s/photo; it cannot read, so it never classifies alone |
| Segment | SAM 3.1 | Masks for sign / menu / receipt / dish / storefront | Prompted masks are a cheap evidence-presence test (47.3% of the sample hit at least one prompt); a mask locates evidence but does not read it |
| Classify (bulk) | PE-Core-L14-336 or a DE-style single-question read | First-pass category over the whole library | PE-L costs 0.14 s/photo; a DE category read costs ~1 s/photo locally at food F1 0.89. PE-G is not used: 13.6x PE-L's cost for the same agreement |
| Classify (reference) | Muse Glimmer | Category where accuracy matters, and the standard other systems are scored against | Best measured food F1 (0.976); at 19.4 s/photo it is the escalation target, not the bulk pass, at library scale |
| Extract | Muse Glimmer (selective) | Read menus, receipts, signs; transcribe text; propose dishes and place names | The only measured model that reads; runs only on photos the earlier stages mark as evidence-bearing (~30 s each) |
| Decide (pattern) | Shisa DE-2.1 locally; a future Glimmer-DE | Fast yes/no and multiple-choice routing with probabilities (route to extraction, ask the user, mark unknown) | A restricted read returns a probability distribution in one forward pass instead of generated text; DE-2.1's local build matches its API reference (92.5% category agreement) at ~0.94 s per question |

Three rules the measurements produced:

1. **No model names a place from food appearance.** Dish identity supports a visit; place identity comes from check-ins, GPS candidates, and text read in the photo (signage, menus, receipts), ranked by evidence strength.
2. **Abstention is a routing signal, not an error.** Glimmer abstains on ~21% of photos and DE-2.1 on more; abstained photos go to the review queue or stay 'unnamed place near <area>' with their candidates listed.
3. **Probabilities come from restricted reads, not generated text.** Glimmer's generative JSON carries no usable per-category probability (its confidence field is unreliable in practice, and llama.cpp does not enforce the schema). Letter-coded next-token logprob readout is now measured on llama.cpp and vLLM and has full-corpus imported outputs. This no-training experiment is not a trained/calibrated Glimmer-DE: LoRA, held-out calibration, and an automatic escalation policy remain unbuilt.

Known limits, stated for the presentation: non-food categories have no independent ground truth yet (the efficient fix is adjudicating only photos where systems disagree); Glimmer's evidence-type list is its weak output (recall 0.138 against owner evidence labels), which is why SAM masks and DE evidence questions carry that axis; and the DE-2.1 numbers come from a general-purpose decision model used as a comparator — a Glimmer-DE trained on Crumbs labels is the planned replacement, not a shipped feature.

## Sufficiency verdict (from `crumbs demo`, current store)

- The **sample previously carried an end-to-end pipeline demo**. Rebuild `crumbs demo` after full-corpus extraction and reconciliation and inspect the resulting local manifest; do not carry forward sample record IDs or claim a text-backed strong candidate until the current store supports it.
- **Not public-video ready**: accuracy numbers exist only for the food slice (the other categories' labels mostly confirm the model default), trips over-merge at sample sparsity (feature visits, not trip narratives), and any public footage needs the owner's consented subset or the synthetic set.
- A fresher iPhone/iCloud sync is **not required** for the demo; it would mainly buy a cleaner multi-day trip storyline.
