# Discovery: Meta models for Crumbs — what to test, in what order

Status: pre-plan discovery, 2026-10-27. This document decides **what to test** before [BRAINSTORMING.md](BRAINSTORMING.md)'s direction becomes a PLAN.md. Product direction and use cases live in BRAINSTORMING.md; this file covers the Meta model catalog as it applies to Crumbs, the local-hardware question, and the experiments with pass/kill criteria.

Facts below are from Meta's own pages, fetched 2026-10-27 (sources in §7). Anything not verified there is marked **to test** — do not quote it as a capability until the experiment runs.

## Decision: local-only processing is the core (2026-10-27)

**The shipped system processes everything locally, with local models only.** All image classification, embedding, evidence extraction, visit reconstruction, and agentic retrieval run on the user's own hardware; no photo, location record, or derived image content is sent to a cloud model API. This is a product-defining claim — privacy is a headline feature, not a fallback mode — and it constrains every model choice below:

- **In the shipped pipeline:** Muse Glimmer (open weights, self-hosted) and DINOv3 (open weights, self-hosted), plus local non-model code (EXIF/metadata, geospatial index). That is the whole list.
- **Not in the shipped pipeline:** Muse Spark / Wonder (API-only), Muse Spark Open *as hosted by a partner* (self-hosting it is impractical at 816B; partner hosting is cloud processing), SAM 3.1 (API-only), Muse Image (API-only). These may be used **during development only** — e.g. as a quality oracle on the consented demo subset to measure how far local models are from the cloud ceiling — and that use must be disclosed wherever results are quoted. A benchmark number produced by a cloud model is never presented as the product's output.
- **One explicit, optional exception:** voice input. Muse Voice Transcribe is API-only, so if voice recollection/search ships at all, it is off by default, clearly labeled as sending *audio* (never images or location history) to Meta's API, and the system must be fully usable without it. A local speech-to-text alternative is an E7 probe; if neither is acceptable, voice is cut. Wording rule: we may say “all image and location processing is local; optional voice transcription is the only cloud feature, and it is off by default” — we may not say “fully private / nothing leaves the device” while that exception is enabled.
- **Hardware reality:** the lead has RTX PRO 6000 (96 GB) cards available, plus a Strix Halo (AMD, unified memory) box. That removes the main feasibility risk: SGLang's verified-platform matrix lists Muse Glimmer **bf16 on a single RTX PRO 6000**, and vLLM needs ≈72 GB VRAM to serve bf16 — both fit one PRO 6000. CUDA (vLLM/SGLang/PyTorch) is therefore the primary local target; llama.cpp/ONNX cover portability, and Strix Halo becomes a secondary “does it also run on a consumer AMD box?” test rather than the gate for the whole local story.

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
| **Muse Spark 1.3** (`muse-spark-1.3`) | Meta Model API | Text, image, video, audio, PDF in; text out; 1,048,576-token context; reasoning effort up to `"max"`; tool calling, structured output, search grounding. Recommended version for new work; 1.2/1.1 also available. Audio understanding in 1.3 is degraded — docs direct audio to 1.2 or Voice Transcribe. Standard mode: content not used for training; Contributor mode (`-contributor` ID) is discounted and may train on content. | **Development oracle only** (quality ceiling for E3/E5 comparisons) | Excluded from the shipped pipeline by the local-only decision. Any oracle use is limited to the consented demo subset, in Standard mode, and disclosed when its numbers are quoted. |
| **Muse Wonder** (`muse-wonder-1.0`) | Meta Model API (preview) | Most capable line; same inputs/context as Spark; long-horizon agentic work, sub-agent orchestration, computer use. API variant is Standard-mode only; the higher-capability Wonder Full is Muse Code-only, not API. Not available in South Korea on API or Muse Code. | **Development oracle only**, hardest cases | Excluded from the shipped pipeline (API-only, preview). At most a tiebreaker oracle in E5; the build must never depend on it. |
| **Muse Glimmer** | Open weights (Apache 2.0), self-hosted | 30B dense multimodal (text+image in, text out), distilled from Muse Spark; 128K-token default context; 100+ languages; built for local, always-on agentic tool use. bf16 weights ≈60 GB, ≈72 GB VRAM to serve under vLLM; published quantized builds 17–20 GB. Runtimes: vLLM, SGLang, llama.cpp, ExecuTorch, Ollama, LM Studio, Unsloth, HF Transformers. SGLang verifies bf16 (the multimodal checkpoint) on a single RTX PRO 6000 (96 GB); GGUF/NVFP4/MLX builds under SGLang are text-only, while llama.cpp's GGUF build ships a ~1.4 GB vision projector (`mmproj`) alongside the ~17 GB Q4_K_M text model. | 1, 3, 4, 5 — **the local core** | The privacy story and the open-weight bonus both ride on this model. Primary serving target is bf16 on a PRO 6000 via vLLM or SGLang (E2); quantized/llama.cpp builds are the portability path for smaller boxes. Glimmer docs warn against greedy decoding; use the published sampling settings (temperature 1.0, top_p 0.95, top_k 64). |
| **Muse Spark Open** | Open weights, self-host or partner-hosted | 816B MoE, 42B active; text/image/video/audio in; BF16 and NVFP4 checkpoints; serve via SGLang/vLLM/TensorRT-LLM/llama.cpp or hosted providers (Baseten model ID `meta-models/muse-spark-open-1026`). | None in the shipped pipeline | Partner hosting is cloud processing, and 816B self-hosting is impractical on our hardware. Recorded here so the exclusion is explicit; not a fallback. (It would count for the open-weight bonus per README §10, but using it would break the local-only claim — the claim outranks the bonus.) |
| **SAM 3.1** (`sam-3.1`) | Meta Model API only | Text prompt + image/video in; boxes and pixel-accurate masks out; also point/box-prompted segmentation; tracks objects across video frames. | None in the shipped pipeline; E4 measures the *value of cropping* locally | API-only, so excluded by the local-only decision regardless of quality. Segmentation is not identification anyway (a mask around a sign does not read it). E4 tests whether cropping helps at all, using local cropping (Glimmer-proposed regions, DINOv3 dense features, or fixed heuristics); if SAM-grade masks ever become necessary, that is a new decision, not a silent API call. |
| **DINOv3** | Open weights under the **DINOv3 License** (not Apache; weights via request/Hugging Face) | Meta FAIR self-supervised vision backbones; frozen backbones produce high-quality dense features without fine-tuning; lightweight adapters/heads can be trained on small labeled sets. Family: ViT-S/16 21M, ViT-S+/16 29M, ViT-B/16 86M, ViT-L/16 300M, ViT-H+/16 840M, ViT-7B, plus ConvNeXt Tiny 29M → Large 198M. HF Transformers ≥4.56 and `timm` ≥1.0.20 support; reference repo includes dense/sparse patch-matching and k-NN/linear-probe evaluation code. License requires "Built with DINOv3" display if redistributed and governs derivative works — read it before shipping anything built on it. | 1, 2 — **the local embedding workhorse candidate** | No language understanding: it cannot read a sign or name a dish. Its outputs are similarity and features; labels come from a small trained head or from a multimodal model. Small variants (21–86M) are trivially cheap locally, including on integrated graphics or CPU. **Eligibility caveat:** the hackathon's open-weight bonus names Muse Glimmer / Muse Spark Open only, and Stage One asks for Meta Model API and/or Meta open-weight model use (README §§9–10). DINOv3 is supporting infrastructure — it must not be our *only* Meta model story. |
| **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`) | Meta Model API | Streaming + file ASR; diarization, endpointing/VAD, keyword biasing; 25 evaluated languages with code-switching; turn-level timestamps (no word-level timestamps). | Stretch: spoken recollections / voice search | Language list not confirmed to include Japanese — check before any demo promise. Not needed for the core workflow. |
| **Muse Image** (`muse-image-1.0`) | Meta Model API | Text/image in, image out; generation and editing. | None in the core | Generated imagery must never be presented as historical evidence. At most a clearly-labeled presentation extra; defer. |
| **Muse Code** | Coding agent | The build tool; mentioned in the submission. | — | Already in use; no experiment needed. |

Non-Meta pieces Crumbs still needs (not discovery questions here): EXIF/metadata parsing, a map/place lookup provider (terms/attribution still open in BRAINSTORMING's next checks), and storage/indexing. Place identity should come from check-ins, GPS, and lookups — models supply evidence, not verdicts.

## 3. The local hardware question

Available hardware: **RTX PRO 6000 (96 GB) cards** (Blackwell, CUDA) and a **Strix Halo** box (AMD Ryzen AI Max class, Radeon integrated graphics, large unified memory). llama.cpp, vLLM, PyTorch, and ONNX are all in play. With that hardware the local stack is not a stretch goal; the questions are throughput, quality, and portability.

**Primary target — PRO 6000 / CUDA.** This is a vendor-verified Glimmer configuration, not a hope:

- SGLang's verified matrix lists Glimmer bf16 — the only multimodal checkpoint — on a single RTX PRO 6000 (96 GB); vLLM serving needs ≈72 GB VRAM (bf16 weights ≈60 GB plus KV cache/activations), which also fits one card. Multi-card tensor parallelism is essentially untested per the docs ("treat multi-GPU serving as untested"), so plan single-card serving per instance and parallelize across photos/instances instead.
- DINOv3 (PyTorch or ONNX) on the same card embeds a library at trivial cost relative to Glimmer generation; the embedding pass should never be the bottleneck.
- Serving choices to benchmark head-to-head in E2: vLLM vs. SGLang (both OpenAI-compatible endpoints, reasoning/tool-call parsers differ in flag names — `muse_glimmer` vs. `muse`; copy flags from the current recipe, they are version-sensitive).

**Secondary target — Strix Halo / AMD.** This answers “does it also run on a consumer box?” and widens the demo's credibility, but it no longer gates the product:

- No verified AMD/Strix Halo Glimmer deployment is published in the docs checked, and the published vLLM image is CUDA-pinned with no ROCm image. The promising path is llama.cpp (ROCm, then Vulkan) with the 17 GB GGUF Q4_K_M + `mmproj` vision projector; SGLang's GGUF path is text-only, so llama.cpp is the only documented multimodal route on AMD.
- DINOv3 small variants (21–89M parameters) run anywhere, including this iGPU or CPU, so classification/embedding on Strix Halo is low-risk even if Glimmer generation there is slow.
- Result framing: whatever E2 measures on Strix Halo is reported as the consumer-hardware story; the PRO 6000 numbers are the reference configuration. Do not quote PRO 6000 throughput as typical consumer performance.

**Architecture consequence.** The pipeline is local end-to-end (DINOv3 embeddings/heads → Glimmer extraction and reconstruction → local geospatial index and agent). If a local model cannot resolve a case, the product's answer is a targeted question to the user or an explicit unknown — never a silent cloud escalation. That behavior is itself a feature to demo: the system shows what it could not determine and asks exactly one useful question.

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

### E2 — Muse Glimmer serving: PRO 6000 first, Strix Halo second

- **Question:** what does local Glimmer serving cost and deliver, per hardware target?
- **Primary (PRO 6000 / CUDA):** serve the bf16 checkpoint under vLLM and under SGLang; measure cold start, tokens/sec, seconds per photo for the fixed E3 extraction prompt (images included), peak VRAM, and stability/throughput over a 500-photo batch, including concurrent requests. Confirm tool calling and structured output through each server's parser flags. Use the published sampling settings (temperature 1.0, top_p 0.95, top_k 64; do not run greedy).
- **Secondary (Strix Halo / AMD):** llama.cpp (ROCm build, then Vulkan) with the Q4_K_M GGUF + `mmproj` vision projector; same measurements, reporting peak unified-memory use. Try the dynamic Q4 build if quality (measured in E3) is marginal.
- **Pass:** on the PRO 6000, the full E0 corpus extracts locally at a rate that makes “import a trip in minutes” true on one card. On Strix Halo, any working multimodal result with honest numbers is a pass for the portability story; failure there does not block the product, but must be recorded (it bounds who can self-host the full stack). **Kill/pivot:** if bf16 serving fails on the PRO 6000 — contrary to the vendor-verified matrix — fall back to quantized builds and re-measure quality in E3 before concluding anything; do not pivot to cloud, which the local-only decision forbids.

### E3 — Evidence extraction quality: local Glimmer, measured absolutely (cloud oracle optional)

- **Question:** on signs, menus, receipts, storefronts, and dishes (including Japanese text), is local Glimmer good enough to ship — measured against the hand labels, not against another model?
- **Tests:** fixed structured-output schema (visible text transcription, dish names, place-name candidates, confidence, "cannot determine") on the E0 evidence photos, for each serving configuration that passed E2 (PRO 6000 bf16; Strix Halo GGUF if it ran). Include the adversarial cases: dish-only photos where the correct place answer is "unknown."
- **Metrics:** transcription accuracy on readable text; dish-identification accuracy; place-candidate precision; **abstention correctness** (saying unknown when the evidence doesn't decide) — weighted as heavily as accuracy. Report per hardware/quantization so the Strix Halo quality cost, if any, is a number rather than an impression.
- **Optional oracle:** the same set through Muse Spark (Standard mode, consented demo subset only) to size the local-vs-cloud gap. This informs whether to invest in better prompting/quantization; it never ships, and any quoted gap must name the oracle and the subset.
- **Decision:** Glimmer ships as the extractor if it clears the abstention-weighted bar set from E0's confusion costs. If it falls short, the levers are local — schema/prompt revision, higher-fidelity quantization, DINOv3-based routing of hard photos to longer Glimmer reasoning — not a cloud fallback.

### E4 — Cropping ablation: do localized crops help extraction? (local methods only)

- **Question:** does extracting from a crop (sign / receipt / menu / dish region) beat whole-image extraction? SAM 3.1 is API-only and therefore out of the shipped pipeline; this experiment tests the *value of cropping itself* using local region proposals: Glimmer-proposed boxes, DINOv3 dense-feature regions, or simple heuristics.
- **Metrics:** same extraction metrics as E3, per condition (whole image vs. each crop method); failure modes on cluttered restaurant photos.
- **Pass/kill:** adopt the best local crop method only if it measurably improves extraction; otherwise whole-image extraction ships and segmentation stays out (it is not identification, and adding it for its own sake is model-count padding). If crops help enormously and no local method captures the gain, record that as an open problem — it still does not authorize a SAM API call in the product.

### E5 — Visit reconstruction with local Glimmer (+ deterministic grouping)

- **Question:** given a photo cluster + check-in/location records with known conflicts, can local Glimmer (reasoning over DINOv3/metadata-proposed groupings) reconstruct visits — and state uncertainty — well enough to ship?
- **Tests:** clusters proposed by time/GPS/DINOv3 similarity, reconciled by Glimmer with a structured-output schema: proposed visits, evidence links per claim, confidence, explicit unknowns, and a targeted follow-up question when evidence is missing. Compare two conditions: Glimmer alone on raw clusters vs. Glimmer over deterministic pre-grouping. An optional Spark/Wonder oracle run (consented subset, disclosed) sizes the remaining gap on the hardest clusters.
- **Metrics:** visit-grouping precision/recall against E0 labels; place-resolution accuracy; evidence-link correctness; conflict handling (nearby observation never upgraded to confirmed visit); targeted-question usefulness (would the answer actually decide the case?).
- **Decision:** confirms the reconstruction design and whether the agentic "ask one good question" loop is real or cut. There is no cloud engine to fall back to; a shortfall is fixed with better grouping, schema, or confirmation UX.

### E6 — Agentic geospatial retrieval and taste profile

- **Question:** can an agent (winner of E5, tool-calling over the local index) answer the E0 golden queries — vague-memory, near-a-place, what-was-good-last-time — by planning lookups (geospatial filter → visit → dishes/orders → evidence) instead of plain vector search?
- **Metrics:** golden-query success rate vs. a plain embedding-search baseline (this comparison is what keeps us out of "basic RAG" territory); answer evidence shown for every claim; correct "you haven't been / unknown" answers.
- **Taste profile test:** build the profile only from factual signals — recurrence counts by dish/cuisine/place, repeat visits, user-confirmed likes — then test it predicts held-out repeat visits/orders better than a most-frequent baseline. **Guardrails:** frequency in photos is biased (photogenic food, trips vs. daily life, photographing the special not the usual); the profile must show its evidence and accept corrections. It is a food/place preference summary, never a personality analysis (personality analyzers are an anti-project).

### E7 — Stretch probes (only after E1–E6)

- **Voice (the one possible cloud exception):** first verify Muse Voice Transcribe's evaluated-language list covers the languages we would demo (Japanese unconfirmed). If voice ships, it is off by default, sends audio only, and is labeled as such. Also probe a local ASR option so the exception can be removed entirely; if neither is acceptable, cut voice. Never route image or location data through this path.
- **Muse Image:** none for the core; revisit only for clearly-labeled presentation material after the submission's main claims are true.

## 5. Decisions these experiments feed

| Decision | Decided by | Deadline pressure |
|---|---|---|
| Local serving stack: vLLM vs. SGLang on PRO 6000; llama.cpp viability on Strix Halo | E2 | Gates throughput claims, the hardware story in PLAN.md, and who can self-host |
| Voice exception: Muse Voice Transcribe (off by default), a local ASR, or no voice | E7 | Gates the exact privacy wording; settled before any public claim is written |
| Local cropping in or out (SAM stays out: API-only) | E4 | Adopt only on a measured win |
| Reconstruction engine + agent loop | E5, E6 | Core demo depends on it |
| Taste profile scope | E6 | Ship only if it beats the frequency baseline and stays evidence-linked |
| Track/bonus flags (Indie; open-weight and agentic bonuses) | E2, E5, E6 | Submission metadata — flagged in the first judging round, so the build must match the flag |

## 6. What would change our mind

- E3 shows local Glimmer extraction is not good enough even after prompt/schema and quantization levers → narrow the product's claims (e.g. extraction becomes draft-plus-user-confirmation everywhere, automated resolution only above a measured confidence bar). Reopening cloud processing would require a new lead decision superseding the local-only decision above; it is not a silent fallback.
- E2 shows Strix Halo multimodal Glimmer is impractical → the consumer-hardware story becomes DINOv3 classification/embedding locally with Glimmer requiring a discrete GPU; state the hardware floor honestly in PLAN.md and the demo.
- E1's head beats Glimmer on triage accuracy → prefer the head for routing (cheaper, deterministic), Glimmer for extraction only.
- E5 shows models confidently resolving visits that the evidence cannot decide → reconstruction becomes suggestion-plus-confirmation by default; automated resolution only above a measured confidence bar.
- Golden queries (E6) don't beat plain search → the agent layer is unjustified; ship the evidence-linked index and direct filters instead, and drop the agentic-bonus claim.

## 7. Sources (fetched 2026-10-27)

- Meta Model API model catalog: https://dev.meta.ai/docs/models (Spark/Wonder/Image/Voice/SAM/Glimmer/Spark Open availability, inputs, context, modes)
- Muse Glimmer: https://dev.meta.ai/docs/muse-glimmer and https://dev.meta.ai/models/muse-glimmer (30B, Apache 2.0, distilled from Spark)
- Glimmer deployment: https://dev.meta.ai/docs/muse-glimmer/deploy (runtimes, GGUF + vision projector, bf16 ≈60 GB / ≈72 GB VRAM, quantized 17–20 GB, no ROCm vLLM image, sampling guidance) and https://dev.meta.ai/docs/muse-glimmer/hardware-platforms (verified Intel/NVIDIA platforms; no AMD platform verified)
- SAM 3.1: https://dev.meta.ai/models/sam-3-1 (API-only — text-prompted boxes/masks, video tracking; excluded from the shipped pipeline by the local-only decision)
- DINOv3: https://ai.meta.com/research/dinov3/ and https://github.com/facebookresearch/dinov3 (model family sizes, HF/timm support, matching notebooks, k-NN/linear evaluation); license: https://ai.meta.com/resources/models-and-libraries/dinov3-license/ (DINOv3 License, "Built with DINOv3" redistribution term)
- Hackathon requirements, judging, and bonus eligibility: [README.md](README.md) §§9–10
