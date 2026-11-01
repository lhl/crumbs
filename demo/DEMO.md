# Crumbs — Demo Script (working draft)

Three minutes, Must-scope only, every beat backed by a working feature. Concrete record IDs live in the local demo manifest (`crumbs demo` → `data/demo/manifest.json`, ignored — it names the owner's real visits). This file stays generic so it can live in the public repo.

## Beats

1. **The problem (0:00–0:25).** Scrolling a camera roll, failing to name a restaurant from a food photo. Cut to the offline globe: clusters of real trips, rebuilt locally. *Feature: PWA-06 globe + real corpus export.*
2. **The pipeline, visibly local (0:25–1:10).** Import → classify → group on screen with the model inventory beside it (MODELS.md): photos become categories, evidence, visits — no API calls (the blocked-network globe test is the proof). One food visit resolves only by combining menu text + GPS candidates. *Features: IMP-01, EMB, REC-01/02/07, EXT.*
3. **Ask (1:10–1:50).** The anchor query: "what was the dashi restaurant near <anchor area> in <trip month>?" — answered from visits and ranked candidates with evidence. Then "what did I have at <candidate place>?" for dishes. *Feature: AGT v1 (CLI + `/v1/ask`).*
4. **Correction + honest unknown (1:50–2:25).** One review-queue question answered (candidate confirmed/rejected, resolution updates); one question about a place never visited → designed unknown. *Features: REC-02 queue, labels.*
5. **Close on measurement (2:25–3:00).** The zbook rate table (MODELS.md) and the privacy statement: every model on the box, tiles offline, location history never leaves. *Features: MODELS.md, bridge tiers.*

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

At these rates, the full 9,199-photo iCloud library costs about 8 minutes of DINOv3 embedding, 21 minutes of PE-L classification, 7.2 hours of SAM segmentation, or roughly 50 hours of Glimmer triage. The pipeline order in the next section follows from these numbers.

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

This is the pipeline that exists in the `crumbs` package today and processed the sample corpus end to end. Every stage is a `crumbs` subcommand; stages with no model are deterministic code.

| # | Stage | Command | Model / engine | Box |
| --- | --- | --- | --- | --- |
| 1 | Photo import | `import-photos` | exiftool (EXIF time/GPS) + ImageMagick (1024 px analysis copies); SHA-256 dedupe; originals untouched | strixhalo |
| 2 | Location import | `import-locations`, `stays`, `tz`, `correlate` | Wanderings location export → dwell stays, camera-timezone estimates, photo↔stay correlation | strixhalo |
| 3 | Embed | `embed` | DINOv3 ViT-L/16 (PyTorch/ROCm); vectors stored in SQLite | zbook / strixhalo |
| 4 | Classify | `classify` | Muse Glimmer 30B (Q4_K_M GGUF + vision projector + DFlash draft) via llama.cpp: category + evidence types as generated JSON, 19.4 s/photo | zbook |
| 5 | Group | `group` | Deterministic time/GPS grouping into visits and trips | any |
| 6 | Extract | `extract` | Glimmer long-form reads, only on food/evidence photos: full text transcription, dish and place-name candidates; place names matched to nearby registry places (signage evidence) | zbook |
| 7 | Place candidates | `places-fetch`, `nearby`, `place-search` | OpenStreetMap Overpass at development time, cached in SQLite; per-visit candidates ranked check-in > signage text > GPS proximity | strixhalo |
| 8 | Reconcile | `reconcile` | Evidence scoring over visits; builds the review queue of targeted questions | any |
| 9 | Ask / serve | `ask`, `serve` | Evidence-linked answers over the local index, every claim tied to its records; read-only local API | strixhalo + zbook |
| 10 | Label / score | `label`, `score` | Human labeling UI (phone-friendly) and scoring of model output against those labels | strixhalo |

Everything runs on the three local Strix Halo boxes (each: Ryzen AI MAX+ 395, Radeon 8060S, 125 GB unified memory). No photo, location record, or derived result leaves these machines in the built pipeline.

## Also reviewed (measured, not in the built pipeline)

These models were downloaded, run over the same 440 photos, and scored — then deliberately left out of the pipeline for the reasons given. They are the comparison set behind the role assignments in the next section, and the presentation can show them as the evaluated alternatives.

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
3. **Probabilities come from restricted reads, not generated text.** Glimmer's generative JSON carries no usable per-category probability (its confidence field is unreliable in practice, and llama.cpp does not enforce the schema). The llama.cpp server does return token logprobs — verified 2026-11-01 — so a DE-style logprob readout on Glimmer (letter-coded options, one token, normalized distribution) is feasible; it is the Glimmer-DE item in IMPLEMENTATION.md (GDE), not yet built.

Known limits, stated for the presentation: non-food categories have no independent ground truth yet (the efficient fix is adjudicating only photos where systems disagree); Glimmer's evidence-type list is its weak output (recall 0.138 against owner evidence labels), which is why SAM masks and DE evidence questions carry that axis; and the DE-2.1 numbers come from a general-purpose decision model used as a comparator — a Glimmer-DE trained on Crumbs labels is the planned replacement, not a shipped feature.

## Sufficiency verdict (from `crumbs demo`, current store)

- The **pipeline demo is fully buildable from the current sample** (extraction hero, signage-confirmed candidate, review question, anchor visit all exist as real records).
- **Not public-video ready**: accuracy numbers exist only for the food slice (the other categories' labels mostly confirm the model default), trips over-merge at sample sparsity (feature visits, not trip narratives), and any public footage needs the owner's consented subset or the synthetic set.
- A fresher iPhone/iCloud sync is **not required** for the demo; it would mainly buy a cleaner multi-day trip storyline.
