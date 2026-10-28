# Crumbs — Implementation Punchlist

Agent-handoff checklist for [PLAN.md](PLAN.md). Conventions:

- IDs are stable (`EPIC-nn`); reference them in worklog entries, commits, and agent assignments.
- Every task lists **Acceptance** — a task is done when its acceptance is demonstrably true (command output, measured number, or a flow exercised end-to-end), not when code merely exists. Record validation in the unit's worklog entry (AGENTS.md).
- **Depends on** lists hard blockers only. Research dependencies (R1–R14 in PLAN §11) are named where they gate a task; on a negative research result, take the PLAN fallback and note it in the worklog — do not improvise a cloud substitute (local-only is non-negotiable).
- Priority tags: **[M]** Must · **[S]** Should · **[X]** Stretch. Within an epic, tasks are roughly in build order.
- Stack defaults marked *(verify)* in PLAN §5 are confirmed or replaced by INF-02's ADR before dependent tasks start.

---

## INF — Repo, platform, and developer infrastructure

- [ ] **INF-01 [M]** Repo layout for service, PWA, model tooling, eval harness, and fixtures; synthetic-fixture directory conventions; real data only under ignored `data/`, `photos/`, `exports/`, `location-history/`, `takeout/`. *Acceptance:* tree documented in a short repo README section; `git check-ignore` proves real-data paths are ignored.
- [x] **INF-02 [M]** Stack ADR: backend framework, frontend framework + build, DB/index choices, job-queue approach (in-process vs. worker), package managers. *Acceptance:* one worklog `decision` entry naming chosen stack and why; PLAN *(verify)* marks updated to match. *Decided 2026-10-28 (worklog 20261027T213519): Python `crumbs` package with staged CLI, SQLite store with append-only provenance-versioned derived rows, zbook as processing host (PRO 6000 deferred per lead), PWA grown from `spike/map-globe/`; FastAPI/queue/sqlite-vec named as revisit points at API-01 / 10x scale.*
- [ ] **INF-03 [M]** Local dev orchestration: one command brings up service + model servers (or documented stubs) + PWA dev server; health endpoints for each model server. *Acceptance:* fresh-clone walkthrough timed; stub mode runs with no GPU so UI work never blocks on models.
- [ ] **INF-04 [M]** Model-server contracts: versioned request/response schemas for classify, embed, extract, decide (DE readout), segment, transcribe; a fake/stub implementation of each for tests and UI development. *Acceptance:* contract tests pass against stubs and against at least one real server (Glimmer).
- [ ] **INF-05 [M]** Config and secrets hygiene: all paths/ports/model IDs via env or config file; nothing personal in defaults; `.env.example` with placeholders only. *Acceptance:* staged-safety check passes; repo grep finds no home paths or credentials.
- [ ] **INF-06 [S]** Structured logging + job/metrics store: per-stage timings, model latencies, error counts queryable for eval reports and the demo's on-screen numbers. *Acceptance:* one command prints throughput/latency summary for a pipeline run.
- [ ] **INF-07 [S]** Muse / coding-agent build channel: document how agents work this repo (worklog lanes, punchlist IDs), and verify the chosen coding agent can run the repo's checks. *Acceptance:* note in repo docs; one agent-completed task references its punchlist ID end-to-end.

## DAT — Corpus, labels, and eval harness (DISCOVERY E0)

- [ ] **DAT-01 [M]** Demo corpus assembly: consented/synthetic trip + local-outing photos and overlapping location export under ignored dirs; public-demo subset reviewed for people/plates/addresses/GPS and recorded in the worklog. *Acceptance:* corpus manifest (counts, date range, sources) exists; review note committed (no data committed).
- [ ] **DAT-02 [M]** Export-format inspection (R1): Foursquare and/or Google export schema, timestamps/timezones, place IDs, precision, coverage gaps. *Acceptance:* written inspection note; importer choice for v1 decided and recorded.
- [ ] **DAT-03 [M]** Hand labels: reference visits, photo→visit, category (sightseeing/trip/personal/food), evidence types, dish identities; deliberate unknowns and conflicting-source cases included. *Acceptance:* label file versioned locally with counts per class; at least one multi-day trip fully labeled.
- [ ] **DAT-04 [M]** Golden queries set: vague-memory, near-a-place, what-was-good-last-time, plus unanswerable/unknown cases, each with expected answer or explicit unknown. *Acceptance:* ≥15 queries across families, stored in the eval harness format.
- [ ] **DAT-05 [M]** Synthetic public fixture set: generated/collected license-clean photos+records that mimic the real corpus shape for repo tests and the public demo fallback. *Acceptance:* fixture runs the full pipeline in CI-like fashion; license/consent note per asset.
- [ ] **DAT-06 [M]** Eval harness CLI: runs a pipeline stage or full pass over the corpus and emits metrics (classification accuracy/confusion, extraction field accuracy + abstention, grouping P/R, place accuracy, golden-query success) as machine-readable + human summary. *Acceptance:* one command reproduces a metrics table; harness reads model/checkpoint/hardware metadata into every report.
- [ ] **DAT-07 [S]** Labeling helper: minimal local tool/flow to speed hand-labeling and correction of reference data (not a product UI). *Acceptance:* labeling rate measured vs. raw spreadsheet flow; labels export to DAT-03 format.

## IMP — Importers and normalization

- [ ] **IMP-01 [M]** Photo importer: recursive scan of user-selected folders, content hashing, dedupe (exact + same-content), EXIF timestamp/timezone/GPS extraction, format coverage (JPEG/PNG/HEIC *(verify)*), corrupt-file handling. *Acceptance:* imports DAT-01 photos with per-file status; EXIF coverage report matches DAT-02-style inspection. *Working 2026-10-28 (worklog 20261027T213832): 440/440 sample photos imported with hash dedupe, EXIF facts, and 1024px analysis JPEGs (HEIC via ImageMagick); timezone extraction is stored raw — inference is IMP-03. Acceptance closes when the full (unsampled) corpus imports with the same reconciliation.*
- [ ] **IMP-02 [M]** Location importer v1 (source chosen in DAT-02): check-ins/location samples normalized with source IDs, original timestamps + tz, coordinates, source place names/IDs. *Acceptance:* imported counts reconcile with source export counts; raw records preserved and linkable.
- [ ] **IMP-03 [M]** Timezone engine: infer photo/record timezones from GPS, source tz, and trip context; store tz + tz_source + uncertainty; never silently assume device tz. *Acceptance:* unit tests over known tz-boundary cases from the corpus; ambiguous cases flagged, not guessed.
- [ ] **IMP-04 [M]** Import scope and consent flow (service side): user selects folders/date ranges; scope summary counts; resumable imports; delete-import with full derived-data cleanup. *Acceptance:* re-import is idempotent; delete removes derived records and proves it by query.
- [ ] **IMP-05 [S]** Incremental/watch import: new files in watched folders are queued automatically (background agent prerequisite). *Acceptance:* dropping a photo into the folder produces a classified, grouped item without manual action.
- [ ] **IMP-06 [X]** Second location-source importer (the one not chosen in IMP-02). *Acceptance:* same normalization contract and reconciliation tests as IMP-02.

## STO — Storage, schema, and indexing

- [ ] **STO-01 [M]** Schema implementation for PLAN §6 entities with provenance enum (`observed|inferred|lookup|confirmed`), confidence, model/checkpoint versioning, append-only corrections. *Acceptance:* migrations run from empty; a correction never mutates the original record (test).
- [ ] **STO-02 [M]** Media store: content-addressed references to originals in place (no copying by default), thumbnail/preview generation locally, missing-file detection. *Acceptance:* pipeline runs with originals read-only; thumbnails generated for the corpus.
- [ ] **STO-03 [M]** Vector index for embeddings (per model version) with nearest-neighbor + metadata filters. *Acceptance:* retrieval latency measured at corpus scale; index rebuild is one command.
- [ ] **STO-04 [M]** Geospatial index and queries: radius/near-place, city/area bucketing, visit clustering support. *Acceptance:* near-a-place query over corpus returns labeled-correct results in the harness.
- [ ] **STO-05 [M]** Job queue and stage runner: per-item stage state, retries, resume after crash/restart, model-version-aware re-runs. *Acceptance:* kill mid-run and resume with no duplicate derived records.
- [ ] **STO-06 [S]** Export/backup of the derived history (JSON/GeoJSON) and full data-deletion proof. *Acceptance:* export opens in the PWA demo mode; deletion test passes.

## EMB — Embeddings and classification (E1)

- [ ] **EMB-01 [M]** Embedding service: DINOv3 local inference (PyTorch; ONNX export probe) with batch throughput measurement; model set per DISCOVERY E1 (ViT-B/16, ViT-S/16, ConvNeXt-Small; ViT-L/16 ceiling-only). *Acceptance:* embeddings/sec on PRO 6000 and Strix Halo recorded in worklog. *Smoke 2026-10-28: ViT-L/16 (camenduru mirror; official gate pending lead approval) embedded at ~200 img/s fp32 on the 8060S via transformers — service/batch measurement still owed (worklog 20261027T210818).*
- [ ] **EMB-02 [M]** Perception Encoder service: PE-Core embeddings + zero-shot classification with taxonomy prompts; prompt set versioned. *Acceptance:* same measurement protocol as EMB-01.
- [ ] **EMB-03 [M]** Classification bake-off runner (E1): DINOv3 head (linear/k-NN) vs. PE zero-shot vs. PE head on DAT-03 labels; confusion matrices; receipt-misroute cost weighted. *Acceptance:* DAT-06 report picks the routing winner (or split) with numbers; decision recorded.
- [ ] **EMB-04 [M]** Similarity tasks: near-duplicate/burst grouping; same-dish/same-storefront matching (DINOv3 patch matching + global NN from both stacks). *Acceptance:* precision/recall on labeled pairs; thresholds chosen from data, not vibes.
- [ ] **EMB-05 [M]** Classification stage in pipeline: every photo labeled (multi-label allowed) with probabilities + model version; text-query retrieval endpoint ("receipt", "grilled fish") for the agent. *Acceptance:* full corpus classified; retrieval precision spot-checked in harness.
- [ ] **EMB-06 [S]** Meta CLIP 2 tiebreaker probe (only if EMB-03 shows PE weakness, esp. non-English). *Acceptance:* one comparative report; adopt or drop in writing.
- [ ] **EMB-07 [S]** Taxonomy revision loop: merge/split categories based on confusion results (e.g. personal∧food handling), with label migration. *Acceptance:* taxonomy v2 (if any) documented; harness re-run shows effect.

## GLM — Muse Glimmer serving (E2)

- [ ] **GLM-01 [M]** Glimmer bf16 serving on one PRO 6000 under vLLM **and** SGLang (recipes copied fresh from current docs; parser flags verified); health + smoke prompts incl. one image. *Acceptance:* both servers answer an image prompt; commands and versions recorded.
- [ ] **GLM-02 [M]** Serving benchmark: cold start, tokens/sec, seconds/photo on the standard extraction prompt, peak VRAM, 500-photo batch incl. concurrency; pick the production server. *Acceptance:* E2 primary-arm numbers in worklog; winner + config committed as code/config, not shell history.
- [ ] **GLM-03 [M]** Structured-output and tool-calling verification through the chosen server (schema adherence over the E3 schema; tool-call parsing). *Acceptance:* ≥99% schema-valid responses over a 200-prompt probe, or the gap is a named blocker with workaround.
- [ ] **GLM-04 [S]** Quantized configuration (GGUF path) quality/latency comparison vs. bf16 on the E3 subset. *Acceptance:* quality delta is a number; quantized config adopted or rejected in writing.
- [ ] **GLM-05 [S]** Strix Halo arm (R10): llama.cpp ROCm→Vulkan with GGUF + mmproj; same measurements incl. unified memory. *Acceptance:* honest portability numbers (or failure modes) in worklog; hardware-floor statement drafted for PLAN/demo. *First arm measured (2026-10-28, zbook Radeon 8060S, HIP build of mainline llama.cpp — Vulkan not needed): official Q4_K_M + mmproj + dflash GGUFs run vision end-to-end (`--jinja` required); full-res photo prefill ≈4,150 tok @ ~88 tok/s, generation 17–27 tok/s with draft-dflash (46–76% acceptance); image encode 1.9 s on a small card. Still open: batch timing + downscale tuning; see worklog 20261027T203902.*
- [ ] **GLM-06 [S]** Always-on readiness: server supervision/restart, warm-keep policy, idle power behavior notes for the background agent. *Acceptance:* service recovers from a killed model server without pipeline data loss.

## GDE — Glimmer-DE System-1 decision layer (E2b)

- [ ] **GDE-01 [M]** Feasibility probes: option codes are single tokens in Glimmer's tokenizer; restricted next-token distribution readable from the chosen server (logprob coverage for ≤256 options); fallback readout design if top-k logprobs are insufficient. *Acceptance:* written probe result; go/no-go for the DE contract recorded (R4).
- [ ] **GDE-02 [S]** Question bank: Crumbs decision families (category, evidence-type presence, evidence sufficiency, same-visit, routing/abstention) rendered from DAT-03 labels with shuffled option order and explicit none/unknown options. *Acceptance:* dataset counts per family; leakage check (no photo in both train and eval).
- [ ] **GDE-03 [S]** Training run: LoRA (rank 16, attention projections, vision tower frozen) with answer-token-only loss via Axolotl/TRL per Glimmer post-training docs; 1 seed first. *Acceptance:* trained adapter evaluates end-to-end through the readout contract on held-out photos.
- [ ] **GDE-04 [S]** Calibration: per-read temperature fitting on held-out data; ECE before/after; routing thresholds derived from calibration, not defaults. *Acceptance:* calibration report in DAT-06 format; thresholds committed as config.
- [ ] **GDE-05 [S]** Multi-seed soup probe (3–5 LoRA runs averaged) if GDE-03 shows the pattern works. *Acceptance:* soup vs. single-run accuracy delta measured; keep the better, record cost.
- [ ] **GDE-06 [S]** Adaptive policy integration: read-twice and think-when-unsure (generative Glimmer) escalation inside the pipeline router. *Acceptance:* latency/accuracy tradeoff table on the corpus; policy thresholds in config.
- [ ] **GDE-07 [X]** Distillation fallback: Glimmer/Glimmer-DE labels → DE-style LoRA on PLM-3B as shipped System-1 (only on a GDE latency kill). *Acceptance:* comparative report; shipped System-1 named in writing.

## EXT — Evidence extraction (E3) and segmentation (E4)

- [ ] **EXT-01 [M]** Extraction schema + prompts: visible text, dish candidates, place-name candidates, per-field confidence, "cannot determine"; schema versioned; adversarial dish-only cases included by design. *Acceptance:* schema validates; prompts stored as code with versions.
- [ ] **EXT-02 [M]** Extraction runner over evidence candidates with the E3 model arms (Glimmer bf16/quantized; PLM-3B/8B comparators). *Acceptance:* DAT-06 extraction report (field accuracy + abstention correctness, per model/hardware).
- [ ] **EXT-03 [M]** Extractor selection + routing: winner (or PLM-volume/Glimmer-hard split) wired into the pipeline; hard-case routing rule from measured confidence. *Acceptance:* pipeline uses the chosen arm; decision + numbers in worklog (R5).
- [ ] **EXT-04 [S]** SAM 3.1 local ablation (R7): gated-checkpoint access (lead action), SAM 3.1 vs. SAM 2 vs. heuristic/embedding crops vs. whole-image on E3 metrics. *Acceptance:* adopt/drop segmentation in writing; if adopted, EXT-05 exists. *Prerequisites proven 2026-10-28: access granted; bf16 SAM 3.1 runs on the 8060S (~0.5 s/prompt, mask visually verified); unsloth FP8 quant shown non-loadable without torchao wiring and is not the path (worklog 20261027T210818). The ablation itself is still to run.*
- [ ] **EXT-05 [S]** Segmentation stage integrated (only on EXT-04 win): masks/crops for sign/receipt/menu/dish with runtime budget. *Acceptance:* end-to-end extraction improvement reproduced through the pipeline.
- [ ] **EXT-06 [S]** OCR-adjacent hardening: rotation/upscale/tiling preprocessing for receipts and menus; failure gallery from corpus errors driving one iteration. *Acceptance:* before/after metrics on the failing subset.

## REC — Grouping, reconstruction, and place resolution (E5)

- [ ] **REC-01 [M]** Deterministic pre-grouping: time-gap + GPS + check-in proximity + visual similarity → candidate visits/trips; timezone-aware via IMP-03. *Acceptance:* grouping P/R on DAT-03 in harness; boundary cases reviewed manually.
- [ ] **REC-02 [M]** Visit reconciliation: Glimmer structured reconciliation per candidate (place candidates, evidence links, confidence, unknown, ≤1 targeted question). *Acceptance:* E5 report (grouping P/R after reconciliation, place accuracy, evidence-link correctness).
- [ ] **REC-03 [M]** Conflict rules engine: nearby-observation ≠ check-in ≠ confirmed visit; conflicting sources preserved and surfaced; no silent upgrades. *Acceptance:* unit tests encode the three-way distinction; UI-visible states exist in the API.
- [ ] **REC-04 [M]** Place resolution + enrichment: canonical place records, candidate merging, optional local-cached place lookup (provider per R8) with attribution stored. *Acceptance:* repeated visits to one place unify; lookup data cacheable offline for demo regions.
- [ ] **REC-07 [M]** Restaurant/place registry + anchor search (PLAN §4 use case 8): locally cached place registry (OSM-derived; name, kind/cuisine, coordinates, source) covering visit areas; per-visit ranked `PlaceCandidate`s triangulated by evidence strength (check-in > signage/menu text match > GPS proximity with distance; dish appearance never identifies); searchable by name/anchor-place/radius/time window for the recommendation flow. *Acceptance:* the anchor query — anchor restaurant + neighborhood + trip window — returns the visit's other candidate restaurants with their evidence and distances, unknowns explicitly unnamed; no candidate is auto-confirmed on GPS alone. *v1 built 2026-10-28 (worklog 20261028T043838): 1,618-place registry, 2,121 distance-ranked candidates over 58 food visits, `nearby`/`place-search` CLI with the anchor demo executed; text-match promotion and PMTiles-POI offline source still owed.*
- [ ] **REC-05 [M]** Trip assembly: visits → trips with stays (lodging evidence), day boundaries, trip naming (inferred, confirmable). *Acceptance:* demo trip assembles correctly end-to-end; naming correction persists.
- [ ] **REC-06 [S]** Suggestion-first mode toggle: auto-resolve only above measured confidence; everything else lands in the review queue. *Acceptance:* threshold derived from REC-02 metrics; queue contents match expectations on corpus.

## AGT — Agent, search, taste profile, background and contextual (E6)

- [ ] **AGT-01 [M]** Local index query tools for the agent: geospatial filter, visit/place/dish lookup, evidence retrieval, text+vector search — as typed, testable functions (no LLM in the loop). *Acceptance:* each tool unit-tested against corpus ground truth.
- [ ] **AGT-02 [M]** Agent runtime: local Glimmer tool-calling loop over AGT-01 with inspectable run traces (question → plan → calls → answer + evidence refs); unknown/haven't-been as designed outcomes. *Acceptance:* DAT-04 golden queries execute with traces stored.
- [ ] **AGT-03 [M]** Golden-query evaluation (R13): agent vs. plain vector-search baseline, same queries, blind comparison. *Acceptance:* success-rate table; agentic claim kept or dropped in writing.
- [ ] **AGT-04 [M]** Answer rendering contract: every factual claim in an answer carries evidence refs; UI can render the chain; unsupported claims blocked by construction (answer assembled from tool results). *Acceptance:* trace audit on all golden queries finds no unevidenced place/dish claims.
- [ ] **AGT-05 [S]** Taste signals + profile v1: recurrence/repeat/confirmed-like signals (STO schema), profile computation, held-out prediction test vs. frequency baseline (R12). *Acceptance:* prediction report; profile claim scoped to the result.
- [ ] **AGT-06 [S]** Background organizer: incremental pipeline on new imports (IMP-05), idle-time scheduling, review-queue generation with a strict interruption budget. *Acceptance:* new-photo-to-visit happens unattended; queue asks only questions generated by REC-02 unknowns.
- [ ] **AGT-07 [S]** Contextual surfacing engine: local triggers (near a past place, repeat-place arrival, city re-entry), user-configured on/off per trigger, precision-first thresholds, dismissal learning (dismissed ≠ deleted). *Acceptance:* triggers fire correctly in a scripted walkthrough over corpus geography; false-positive rate estimated and recorded.
- [ ] **AGT-08 [S]** Recommendation/shortlist builder: "best of <city>" from profile + visits with the "famous place vs. your better finds" contrast, user-editable before sharing. *Acceptance:* shortlist for the demo city generates from real corpus data with evidence attached.
- [ ] **AGT-09 [X]** Voice recollection intake: transcript → draft memory (place/date/dish) → user confirms → `confirmed` evidence. *Acceptance:* spoken note becomes a confirmed record; unconfirmed transcripts never affect ranking.

## VOI — Voice interface (E7)

- [ ] **VOI-01 [S]** Local ASR probe (R9): SeamlessM4T v2 (MMS fallback) on recollection/query speech in demo languages incl. Japanese; WER measured; CC BY-NC implication recorded for the license pass. *Acceptance:* go/no-go for local voice in writing.
- [ ] **VOI-02 [S]** Push-to-talk Ask (PWA): record → transcribe (winning VOI-01 path) → AGT-02; transcript shown and editable before sending. *Acceptance:* spoken golden query succeeds end-to-end on demo hardware.
- [ ] **VOI-03 [X]** Muse Voice Transcribe option (only if VOI-01 fails): off by default, audio-only upload, labeled in UI and Settings; language list (Japanese) verified first. *Acceptance:* with the option off, zero network calls contain audio (verified by request log).

## API — Local service API

- [ ] **API-01 [M]** Browse APIs: trips, visits, places, timeline river, map pins (with clustering params), filters (trip/category/date/text). *Acceptance:* PWA flows (§9.3–9.7) can be built against these alone; response times measured at corpus scale.
- [ ] **API-02 [M]** Ask API: question in → streamed/inspectable answer with evidence refs and run id; follow-up context (place/trip) support. *Acceptance:* golden queries pass through the API, not just the harness.
- [ ] **API-03 [M]** Correction APIs: rename place, move photo between visits, confirm/reject visit, merge/split visits and places; all append-only via STO-01. *Acceptance:* each correction round-trips and visibly changes browse + profile outputs.
- [ ] **API-04 [M]** Import/progress APIs: start import, stage progress with per-stage counts and throughput, cancel/resume. *Acceptance:* PWA import flow (§9.1) driven entirely by these.
- [ ] **API-05 [M]** Review-queue APIs: list targeted questions, answer (confirm/correct/skip), question provenance (which unknown generated it). *Acceptance:* answering a question updates the target visit and closes the loop end-to-end.
- [ ] **API-06 [S]** Contextual feed API: current contextual options with trigger reason + evidence + dismiss endpoint. *Acceptance:* AGT-07 triggers surface through the API with reasons.
- [ ] **API-07 [S]** Taste profile + shortlist APIs (§9.10, AGT-08) with per-item evidence and correct/remove actions. *Acceptance:* profile edits change shortlist output.
- [ ] **API-08 [M]** Local access control: bind to localhost by default; LAN mode requires a pairing token; no unauthenticated LAN exposure. *Acceptance:* unauthenticated LAN request is rejected in a test.
- [ ] **API-09 [X]** Muse channel interface (§8): read-only query endpoint/MCP-style tool surface over AGT-01/AGT-02 with the same evidence contract and API-08 auth. *Acceptance:* an external agent channel answers one golden query through it; PWA unaffected if removed. *Local half built 2026-10-28 (worklog 20261028T052535): `crumbs serve` read-only API with health/search/nearby/visits/places/anchor endpoints, token auth, server-side `near=current`, privacy tiers 0/1/2; demo anchor query verified by curl. Remaining: the tunnel + Muse-side skill (owner steps) and the acceptance query through the actual channel.*

## PWA — Progressive web app and UI flows (PLAN §9)

- [ ] **PWA-01 [M]** App shell: installable PWA (manifest, service worker with offline shell), routing, local-service discovery/config, connection + local-processing status indicator. *Acceptance:* installs on demo phone and laptop; works with model servers down (graceful states).
- [ ] **PWA-02 [M]** Design system: travelogue visual language, photo-first components (visit card, evidence strip, provenance line, confidence language), dark/light, phone + desktop layouts. *Acceptance:* components used by all flows below; no raw confidence percentages outside detail views.
- [ ] **PWA-03 [M]** Import flow (§9.1): source pickers, scope summary, live stage progress, first-results landing. *Acceptance:* full corpus import driven from the PWA on demo hardware.
- [ ] **PWA-04 [M]** Timeline (§9.5): trip→visit river, category facets (sightseeing/trip/personal/food), uncertainty visibly marked, fast scroll at corpus scale (virtualized). *Acceptance:* demo corpus scrolls without jank on demo phone.
- [ ] **PWA-05 [M]** Map (§9.3): clustered visit pins, trip/category/date filters, pin→visit card, tile source per R6 with offline demo regions. *Acceptance:* all demo visits reachable from the map; tiles work with external network disabled for cached regions. *Tile half proven (2026-10-27) in `spike/map-globe/`: fully-local Protomaps PMTiles mode (regional extracts for the 3 demo regions + local glyphs/sprites, fetched by `tools/fetch-tiles.sh`, git-ignored) renders with all non-localhost network blocked and zero external requests — reuse that pattern here; the product flow itself (visit pins/filters/card against real data) is still to build.*
- [ ] **PWA-06 [M]** Globe (§9.4): 3D trip clusters/arcs, select-to-fly into Map, graceful fallback if the library's globe mode fails (R6). *Acceptance:* demo opens on the globe; every trip selectable.
- [ ] **PWA-07 [M]** Trip view (§9.6): ordered visits/days/stays, mini-map, share-card entry point. *Acceptance:* demo trip reads as a coherent travelogue.
- [ ] **PWA-08 [M]** Visit card + Place page (§9.7): evidence-by-type photo sections, what-was-ordered, repeat-visit history, per-fact provenance, correction actions. *Acceptance:* every fact on the demo place page traces to evidence in ≤1 tap.
- [ ] **PWA-09 [M]** Ask (§9.8): text (+ VOI-02 voice) input, example prompts, answer cards with evidence chain and summarized lookup steps, designed unknown states, follow-ups. *Acceptance:* all DAT-04 families demoable through the UI.
- [ ] **PWA-10 [M]** Review queue (§9.9): one-question cards with candidate photos, confirm/correct/skip, visible downstream update. *Acceptance:* the demo correction is performed here, not in a debug tool.
- [ ] **PWA-11 [S]** Home/Context (§9.2): profile strip, recent visits, contextual feed with reasons and dismissal. *Acceptance:* AGT-07 items appear with trigger reasons.
- [ ] **PWA-12 [S]** Taste profile view (§9.10): recurrences with counts/evidence, confirmed likes, correct/remove, frequency-bias plain-language note. *Acceptance:* every profile item shows its evidence; edits persist via API-07.
- [ ] **PWA-13 [S]** Share card: user-reviewed recommendation card/shortlist export (image/text), confirmed items only, no raw location history. *Acceptance:* card generates for the demo city; content reviewed in the flow before export.
- [ ] **PWA-14 [M]** Settings/Privacy (§9.11): local-processing status (models/hardware/no-cloud statement incl. any voice exception), tile-provider disclosure, data location, export/delete, demo-mode toggle. *Acceptance:* every public privacy claim in the demo is verifiable from this screen.
- [ ] **PWA-15 [M]** Demo mode: preloaded consented/synthetic dataset, reset-to-demo-state, guided highlights matching the video script. *Acceptance:* a judge can reproduce the video's flows unaided.
- [ ] **PWA-16 [S]** Empty/error/loading states for every flow (no models, no GPS, no location export, mid-pipeline). *Acceptance:* state gallery reviewed; no flow dead-ends.

## QA — Testing, evaluation reporting, and hardening

- [ ] **QA-01 [M]** Unit/integration suites for importers, tz engine, grouping, conflict rules, API contracts (INF-04 fakes). *Acceptance:* suites run in one command in stub mode (no GPU).
- [ ] **QA-02 [M]** End-to-end golden run: fixture corpus → full pipeline → golden queries, in stub and real-model modes. *Acceptance:* both modes green; real-mode metrics match DAT-06 reports.
- [ ] **QA-03 [M]** Eval report generator: the submission's numbers (classification, extraction, grouping, place, agent vs. search, throughput, hardware) compiled from harness outputs. *Acceptance:* report regenerates from raw outputs; no hand-typed numbers.
- [ ] **QA-04 [M]** Privacy verification: network-traffic audit of the full system in demo configuration (model calls, tiles, ASR exception) proving the local-only claim. *Acceptance:* audit log reviewed; every external call enumerated and disclosed in PWA-14.
- [ ] **QA-05 [S]** Performance pass: import throughput, Ask latency, map/timeline rendering at 10× demo corpus (synthetic scale test). *Acceptance:* measured budgets documented; worst flow fixed or scoped in writing.
- [ ] **QA-06 [S]** Failure-mode review: no-GPS photos, wrong EXIF tz, duplicate places, conflicting check-ins, corrupt files — each with corpus-derived case. *Acceptance:* every case yields a designed state (unknown/queue), never a crash or confident wrong answer.

## DEM — Demo, submission, and documentation

- [ ] **DEM-01 [M]** Demo dataset lock (Nov 2): corpus, labels, model checkpoints, and configs frozen; reset script restores demo state. *Acceptance:* clean-machine demo rehearsal passes from the reset script.
- [ ] **DEM-02 [M]** Demo hardware rehearsal: PRO 6000 box + phone PWA over LAN and localhost fallback; timing of every live step. *Acceptance:* two consecutive full run-throughs within the video's timings.
- [ ] **DEM-03 [M]** 3-minute video per PLAN §10 script, recorded by Nov 3; only in-period built features shown; prior art (e.g. the DE pattern) credited accurately. *Acceptance:* video accessible at a public link; claims checklist vs. QA-03/QA-04 signed off.
- [ ] **DEM-04 [M]** Submission package: CV platform entry by the Representative — public repo, video link, all contributors, track = Indie Developer, bonus flags (Open Weight / Agentic) only as measured, deadline Nov 4 9:00 PM ET (internal target: noon). *Acceptance:* submission confirmation saved; checklist in worklog.
- [ ] **DEM-05 [M]** License and attribution pass (R11): Glimmer Apache, PE Apache, DINOv3 "Built with DINOv3" display, SAM License, PLM FAIR Research, Seamless CC BY-NC (if shipped), Meta CLIP 2 (if used), map/place attribution, fixture asset licenses. *Acceptance:* in-app credits screen + repo NOTICE list every shipped model/dataset with license; encumbered items dropped or replaced if terms fail.
- [ ] **DEM-06 [M]** Repo public-ready pass: product README (what it is, how to run locally, hardware floor, measured results, license notes), no personal data/credentials, demo instructions for judges. *Acceptance:* fresh-clone run-through by a non-author; staged-safety clean.
- [ ] **DEM-07 [S]** X/community post assets for the Most Viral bonus (demo clip + post link submitted via platform by Nov 8 EOD) and gallery listing check for Community Vote. *Acceptance:* post published; link recorded (only if the team opts in).

---

## Suggested agent sequencing

1. **Day 1 (Oct 28):** INF-01…05, DAT-01…04, IMP-01/02, GLM-01 in parallel; INF-02 ADR gates STO/API/PWA starts.
2. **Day 2 (Oct 29):** STO-01…05, EMB-01…03, GLM-02/03, PWA-01/02/05/06 spikes, API-01 skeleton.
3. **Day 3 (Oct 30):** EMB-04/05, EXT-01…03, REC-01…04, GDE-01 (probe only), PWA-03/04/08.
4. **Day 4 (Oct 31):** REC-05/06, AGT-01…04, PWA-09/10, EXT-04 probe, QA-01/02.
5. **Day 5 (Nov 1):** AGT-05…08, VOI-01/02, GDE-02…06 (if green), PWA-11…14, GLM-05.
6. **Day 6 (Nov 2):** freeze — QA-03…06, PWA-15/16, DEM-01/05/06. No new features after this line without a lead decision recorded in the worklog.
7. **Days 7–8 (Nov 3–4):** DEM-02/03/04/07 only.
