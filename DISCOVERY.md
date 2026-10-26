# Discovery: Meta models for Crumbs — what to test, in what order

Status: pre-plan discovery, 2026-10-27. This document decides **what to test** before [BRAINSTORMING.md](BRAINSTORMING.md)'s direction becomes a PLAN.md. Product direction and use cases live in BRAINSTORMING.md; this file covers the Meta model catalog as it applies to Crumbs, the local-hardware question, and the experiments with pass/kill criteria.

Facts below are from Meta's own pages, fetched 2026-10-27 (sources in §7). Anything not verified there is marked **to test** — do not quote it as a capability until the experiment runs.

## 1. The question

Crumbs needs five kinds of machine perception/reasoning:

1. **Triage and classification** of every photo (food / sightseeing / trip / personal, plus evidence types: dish, menu, receipt, sign, storefront, interior, lodging, landmark) — high volume, privacy-sensitive, ideally local.
2. **Visual similarity** — duplicate/burst detection, same dish or same storefront across different photos and visits.
3. **Evidence extraction** — reading signs, menus, receipts, and identifying dishes well enough to support place resolution (never to prove a place from food appearance alone).
4. **Cross-photo reconstruction** — reconciling a cluster of photos plus check-in/location records into a visit, with uncertainty stated.
5. **Agentic retrieval** — answering "near X, what did I enjoy / order before?" over the reconstructed history, and keeping a factual taste profile (what recurs, what the user confirmed liking).

Each Meta model below is evaluated only against these five jobs.

## 2. Model catalog (verified)

| Model | Access | Verified facts (2026-10-27) | Crumbs jobs | Notes / risks |
|---|---|---|---|---|
| **Muse Spark 1.3** (`muse-spark-1.3`) | Meta Model API | Text, image, video, audio, PDF in; text out; 1,048,576-token context; reasoning effort up to `"max"`; tool calling, structured output, search grounding. Recommended version for new work; 1.2/1.1 also available. Audio understanding in 1.3 is degraded — docs direct audio to 1.2 or Voice Transcribe. Standard mode: content not used for training; Contributor mode (`-contributor` ID) is discounted and may train on content. | 3, 4, 5 (cloud ceiling / escalation) | Cloud means photos leave the device; use Standard mode for real collections, and only for clusters that need it (see §4). Cost/latency at collection scale is **to test**. |
| **Muse Wonder** (`muse-wonder-1.0`) | Meta Model API (preview) | Most capable line; same inputs/context as Spark; long-horizon agentic work, sub-agent orchestration, computer use. API variant is Standard-mode only; the higher-capability Wonder Full is Muse Code-only, not API. Not available in South Korea on API or Muse Code. | 4, 5 only if Spark demonstrably fails | Preview status + likely cost; do not design the pipeline around it. Escalation candidate for the hardest reconstruction cases, tested head-to-head against Spark (E5). |
| **Muse Glimmer** | Open weights (Apache 2.0), self-hosted | 30B dense multimodal (text+image in, text out), distilled from Muse Spark; 128K-token default context; 100+ languages; built for local, always-on agentic tool use. bf16 weights ≈60 GB, ≈72 GB VRAM to serve under vLLM; published quantized builds 17–20 GB. Runtimes: vLLM, SGLang, llama.cpp, ExecuTorch, Ollama, LM Studio, Unsloth, HF Transformers. Only the bf16 checkpoint takes images under SGLang; llama.cpp's GGUF build ships a ~1.4 GB vision projector (`mmproj`) alongside the ~17 GB Q4_K_M text model. | 1, 3, 4, 5 — **the local core candidate** | The privacy story and the open-weight bonus both ride on this model. Whether it runs *multimodally* at usable speed on Strix Halo is the single most important unknown (E2). Glimmer docs warn against greedy decoding; use published sampling settings. |
| **Muse Spark Open** | Open weights, self-host or partner-hosted | 816B MoE, 42B active; text/image/video/audio in; BF16 and NVFP4 checkpoints; serve via SGLang/vLLM/TensorRT-LLM/llama.cpp or hosted providers (Baseten model ID `meta-models/muse-spark-open-1026`). | 4, 5 (hosted escalation) | Not a local model for us. Relevant as a hosted open-weight escalation and for the open-weight bonus (README §10) if self-hosted Glimmer falls short — hosted still counts as open-weight for the bonus per the guide ("on your own hardware or partner inference"). |
| **SAM 3.1** (`sam-3.1`) | Meta Model API only | Text prompt + image/video in; boxes and pixel-accurate masks out; also point/box-prompted segmentation; tracks objects across video frames. | Supports 3: crop signs, receipts, menus, dishes before extraction | Segmentation is not identification: a mask around a sign does not read it. Value is unproven until the ablation (E4) shows crops beat whole-image or model-guided crops. Cloud-only, so sending photos to SAM has the same privacy cost as sending them to Spark — prefer local cropping alternatives unless E4 shows a clear win. |
| **DINOv3** | Open weights under the **DINOv3 License** (not Apache; weights via request/Hugging Face) | Meta FAIR self-supervised vision backbones; frozen backbones produce high-quality dense features without fine-tuning; lightweight adapters/heads can be trained on small labeled sets. Family: ViT-S/16 21M, ViT-S+/16 29M, ViT-B/16 86M, ViT-L/16 300M, ViT-H+/16 840M, ViT-7B, plus ConvNeXt Tiny 29M → Large 198M. HF Transformers ≥4.56 and `timm` ≥1.0.20 support; reference repo includes dense/sparse patch-matching and k-NN/linear-probe evaluation code. License requires "Built with DINOv3" display if redistributed and governs derivative works — read it before shipping anything built on it. | 1, 2 — **the local embedding workhorse candidate** | No language understanding: it cannot read a sign or name a dish. Its outputs are similarity and features; labels come from a small trained head or from a multimodal model. Small variants (21–86M) are trivially cheap locally, including on integrated graphics or CPU. **Eligibility caveat:** the hackathon's open-weight bonus names Muse Glimmer / Muse Spark Open only, and Stage One asks for Meta Model API and/or Meta open-weight model use (README §§9–10). DINOv3 is supporting infrastructure — it must not be our *only* Meta model story. |
| **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`) | Meta Model API | Streaming + file ASR; diarization, endpointing/VAD, keyword biasing; 25 evaluated languages with code-switching; turn-level timestamps (no word-level timestamps). | Stretch: spoken recollections / voice search | Language list not confirmed to include Japanese — check before any demo promise. Not needed for the core workflow. |
| **Muse Image** (`muse-image-1.0`) | Meta Model API | Text/image in, image out; generation and editing. | None in the core | Generated imagery must never be presented as historical evidence. At most a clearly-labeled presentation extra; defer. |
| **Muse Code** | Coding agent | The build tool; mentioned in the submission. | — | Already in use; no experiment needed. |

Non-Meta pieces Crumbs still needs (not discovery questions here): EXIF/metadata parsing, a map/place lookup provider (terms/attribution still open in BRAINSTORMING's next checks), and storage/indexing. Place identity should come from check-ins, GPS, and lookups — models supply evidence, not verdicts.

## 3. The local question (Strix Halo)

Target box: AMD Strix Halo (Ryzen AI Max class, Radeon integrated graphics, large unified memory). This is where "all image classification runs privately on open models" has to be proven.

What the docs do and don't say:

- AMD is a Muse Glimmer launch partner, but the partner-verified hardware list we fetched covers Intel Arc Pro/Xeon and NVIDIA B300 — **no verified AMD/Strix Halo deployment is published in the docs checked**. Treat local Glimmer on this box as unproven.
- The published vLLM image is CUDA-pinned with **no ROCm image**; vLLM's verified Glimmer platforms are NVIDIA/Intel.
- **llama.cpp is the promising path**: it supports ROCm and Vulkan, serves the 17 GB GGUF Q4_K_M build, and — critically — its Glimmer support includes the vision projector, so multimodal local inference may work there even though SGLang's GGUF path is text-only.
- DINOv3 small variants (ViT-S/B, ConvNeXt Tiny/Small) are 21–89M parameters; embedding a photo library with them locally is cheap on almost anything, including this iGPU or CPU. This part of "local and private" is low-risk.

So the privacy architecture to test is: **everything local by default (DINOv3 embeddings + Glimmer via llama.cpp if it works), cloud only as an explicit escalation for unresolved clusters.** If Glimmer multimodal fails locally, the fallback is DINOv3 + local classification heads for triage, with Spark (Standard mode) doing extraction/reconstruction — still privacy-better than cloud-everything, but the "runs privately on open models" claim and the open-weight bonus story both weaken. That is exactly what E2/E3 decide.

## 4. Experiments — what to test, in order

Run in order; each gates the next. All experiments use the same corpus (E0) so results are comparable. Record results in worklog entries with exact commands, model IDs/checkpoints, quantization, hardware, and counts — a result without its conditions is not a result.

### E0 — Golden corpus and reference labels (do first, blocks everything)

- **Build:** one real, messy trip collection plus local outings, with an overlapping structured location export (Foursquare or Google, per BRAINSTORMING's dataset check). Privacy-safe subset cleared for the public demo; the rest stays in ignored local directories.
- **Label by hand:** reference visits (place, time window), photo→visit assignment, photo category (food / sightseeing / trip / personal) and evidence type (dish, menu, receipt, sign, storefront, interior, lodging, landmark, none), and dish identity where known. Deliberately include unknowns, conflicting sources, and repeated visits to the same place.
- **Write the golden queries:** vague-memory questions ("the little place in Kyoto with the grilled fish"), geospatial questions ("near X, what did I enjoy?"), and reorder questions ("what was good last time at…?"), each with the expected visit/dish answer or an explicit "unknown."
- **Pass:** corpus and labels exist and cover at least one multi-day trip; without this, no other experiment's numbers mean anything.

### E1 — DINOv3 embeddings: triage, similarity, classification head

- **Question:** can a frozen DINOv3 backbone (start ViT-B/16 and ConvNeXt-Small) do jobs 1–2 locally?
- **Tests:** (a) near-duplicate/burst grouping by embedding similarity; (b) same-dish and same-storefront matching across visits (patch-matching per the reference notebooks, plus global-embedding nearest neighbors); (c) a lightweight linear/k-NN head on the frozen features for the food/sightseeing/trip/personal taxonomy and evidence types, trained on a small labeled slice of E0.
- **Metrics:** duplicate-group precision/recall; same-dish/storefront match accuracy on labeled pairs; head accuracy vs. the hand labels, with a confusion matrix (food-vs-personal is the expected hard boundary).
- **Pass/kill:** if the head reaches usable accuracy (set the bar from the confusion cost: misrouting a receipt away from extraction is worse than a sightseeing/personal swap), DINOv3 owns triage and Spark/Glimmer calls drop to candidate photos only. If matching is weak, similarity falls back to metadata+time grouping and DINOv3 is demoted to dedup only.

### E2 — Muse Glimmer on Strix Halo (the local gate)

- **Question:** does Glimmer run multimodally, at usable throughput, on the Strix Halo box?
- **Tests:** llama.cpp (ROCm build, then Vulkan if ROCm fails) with the Q4_K_M GGUF + `mmproj` vision projector; measure cold start, tokens/sec, seconds per photo for a fixed extraction prompt, peak unified-memory use, and behavior over a 500-photo batch. Try the dynamic Q4 build if quality is marginal. Note the published sampling settings (temperature 1.0, top_p 0.95, top_k 64; do not run greedy).
- **Pass:** the full E0 corpus classifies/extracts locally at a rate that makes "import a trip overnight or in minutes" true, within memory. **Kill/pivot:** if multimodal llama.cpp fails or is impractically slow on this box, local scope shrinks to E1 (DINOv3 + heads) and Glimmer is either hosted or dropped — record which, because the bonus and privacy claims change with it.

### E3 — Evidence extraction: Glimmer vs. Muse Spark (quality ceiling)

- **Question:** on signs, menus, receipts, storefronts, and dishes (including Japanese text), how close is local Glimmer to cloud Spark?
- **Tests:** fixed structured-output schema (visible text transcription, dish names, place-name candidates, confidence, "cannot determine"); run both models on the same E0 evidence photos; Spark via API in Standard mode. Include the adversarial cases: dish-only photos where the correct place answer is "unknown."
- **Metrics:** transcription accuracy on readable text; dish-identification accuracy; place-candidate precision; **abstention correctness** (saying unknown when the evidence doesn't decide) — weighted as heavily as accuracy.
- **Decision:** defines the escalation rule (e.g., Glimmer first; Spark only when Glimmer's confidence is low or sources conflict) and the honest privacy claim we can make.

### E4 — SAM 3.1 ablation: do crops help?

- **Question:** does SAM 3.1 segmentation (prompt: "sign", "receipt", "menu", "dish") followed by extraction beat (a) whole-image extraction and (b) Glimmer/Spark choosing its own crop?
- **Metrics:** same extraction metrics as E3, per condition; also masks' failure modes on cluttered restaurant photos.
- **Pass/kill:** include SAM only if it measurably improves extraction; otherwise cut it (segmentation for its own sake is model-count padding). Remember SAM is cloud-only — a tie goes to the local option.

### E5 — Visit reconstruction: Spark vs. Glimmer vs. Spark Open

- **Question:** given a photo cluster + check-in/location records with known conflicts, which model reconstructs visits best — and states uncertainty best?
- **Tests:** same clusters to each candidate (Spark 1.3 API; Glimmer local if E2 passed; Spark Open hosted on Baseten, `meta-models/muse-spark-open-1026`). Wonder only as a tiebreaker probe on the hardest clusters. Structured output: proposed visits, evidence links per claim, confidence, explicit unknowns, targeted follow-up question when evidence is missing.
- **Metrics:** visit-grouping precision/recall against E0 labels; place-resolution accuracy; evidence-link correctness; conflict handling (nearby observation never upgraded to confirmed visit); targeted-question usefulness (would the answer actually decide the case?).
- **Decision:** picks the reconstruction engine and whether the agentic "ask one good question" loop is real or cut.

### E6 — Agentic geospatial retrieval and taste profile

- **Question:** can an agent (winner of E5, tool-calling over the local index) answer the E0 golden queries — vague-memory, near-a-place, what-was-good-last-time — by planning lookups (geospatial filter → visit → dishes/orders → evidence) instead of plain vector search?
- **Metrics:** golden-query success rate vs. a plain embedding-search baseline (this comparison is what keeps us out of "basic RAG" territory); answer evidence shown for every claim; correct "you haven't been / unknown" answers.
- **Taste profile test:** build the profile only from factual signals — recurrence counts by dish/cuisine/place, repeat visits, user-confirmed likes — then test it predicts held-out repeat visits/orders better than a most-frequent baseline. **Guardrails:** frequency in photos is biased (photogenic food, trips vs. daily life, photographing the special not the usual); the profile must show its evidence and accept corrections. It is a food/place preference summary, never a personality analysis (personality analyzers are an anti-project).

### E7 — Stretch probes (only after E1–E6)

- **Voice:** Muse Voice Transcribe on a short spoken recollection; first verify the evaluated-language list covers the languages we would demo (Japanese unconfirmed). Cut if it delays the core.
- **Muse Image:** none for the core; revisit only for clearly-labeled presentation material after the submission's main claims are true.

## 5. Decisions these experiments feed

| Decision | Decided by | Deadline pressure |
|---|---|---|
| Local stack: Glimmer via llama.cpp, or DINOv3+heads only, or hosted | E2, E3 | Gates the privacy claim, the open-weight bonus flag, and PLAN.md architecture |
| Cloud escalation rule (what leaves the device, when) | E3, E5 | Must be settled before any real collection is processed |
| SAM 3.1 in or out | E4 | Cut on a tie |
| Reconstruction engine + agent loop | E5, E6 | Core demo depends on it |
| Taste profile scope | E6 | Ship only if it beats the frequency baseline and stays evidence-linked |
| Track/bonus flags (Indie; open-weight and agentic bonuses) | E2, E5, E6 | Submission metadata — flagged in the first judging round, so the build must match the flag |

## 6. What would change our mind

- E2 fails *and* E3 shows a large Glimmer-vs-Spark quality gap → the local story becomes DINOv3-triage-only; reposition privacy as "embeddings and classification never leave the device; only unresolved clusters are escalated, in Standard mode, with the send-list shown to the user."
- E1's head beats Glimmer on triage accuracy → prefer the head for routing (cheaper, deterministic), Glimmer for extraction only.
- E5 shows models confidently resolving visits that the evidence cannot decide → reconstruction becomes suggestion-plus-confirmation by default; automated resolution only above a measured confidence bar.
- Golden queries (E6) don't beat plain search → the agent layer is unjustified; ship the evidence-linked index and direct filters instead, and drop the agentic-bonus claim.

## 7. Sources (fetched 2026-10-27)

- Meta Model API model catalog: https://dev.meta.ai/docs/models (Spark/Wonder/Image/Voice/SAM/Glimmer/Spark Open availability, inputs, context, modes)
- Muse Glimmer: https://dev.meta.ai/docs/muse-glimmer and https://dev.meta.ai/models/muse-glimmer (30B, Apache 2.0, distilled from Spark)
- Glimmer deployment: https://dev.meta.ai/docs/muse-glimmer/deploy (runtimes, GGUF + vision projector, bf16 ≈60 GB / ≈72 GB VRAM, quantized 17–20 GB, no ROCm vLLM image, sampling guidance) and https://dev.meta.ai/docs/muse-glimmer/hardware-platforms (verified Intel/NVIDIA platforms; no AMD platform verified)
- SAM 3.1: https://dev.meta.ai/models/sam-3-1 (API, text-prompted boxes/masks, video tracking)
- DINOv3: https://ai.meta.com/research/dinov3/ and https://github.com/facebookresearch/dinov3 (model family sizes, HF/timm support, matching notebooks, k-NN/linear evaluation); license: https://ai.meta.com/resources/models-and-libraries/dinov3-license/ (DINOv3 License, "Built with DINOv3" redistribution term)
- Hackathon requirements, judging, and bonus eligibility: [README.md](README.md) §§9–10
