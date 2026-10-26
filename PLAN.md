# Crumbs — Plan

Status: full-spike plan, 2026-10-27 (building period Oct 27 – Nov 4; submissions due **Nov 4, 9:00 PM ET**). This plan turns [BRAINSTORMING.md](BRAINSTORMING.md) (direction and use cases) and [DISCOVERY.md](DISCOVERY.md) (model research and experiments E0–E7) into what we will build. [IMPLEMENTATION.md](IMPLEMENTATION.md) is the agent-handoff punchlist derived from it. Where a choice still depends on a research result, this plan names the dependency (§11) and the fallback; agents must not silently assume the optimistic branch.

This is a spike plan for a hackathon build, not a promise that every feature below ships. §3 defines the tiers; only **Must** is committed for the demo.

## 1. Product in one paragraph

Crumbs reconstructs a searchable travel and food history — trips, visits, meals, and stays — from a user's photos, check-ins, and location history, running **entirely on local open models** on the user's hardware. It organizes the library in the background, surfaces the right memory at decision moments (recommending to a friend, reordering at a repeat restaurant, arriving near a past place), and answers place-anchored questions agentically, with every inferred fact linked to its evidence and every unknown left unknown.

Working tagline: **Crumbs — A travelogue you never have to write.**

## 2. Principles (non-negotiable)

1. **Local-only processing.** All image/location processing uses local open models (Muse Glimmer, DINOv3, Perception Encoder, SAM 3.1 checkpoints, PLM — as validated by DISCOVERY). No photo, location record, or derived content goes to a cloud model API in the shipped system. The sole possible exception is optional, off-by-default voice transcription (audio only), labeled wherever it appears. Map tiles are a network surface too: see §7.4.
2. **Provenance and uncertainty are data, not UI garnish.** Every record distinguishes *observed* (source data), *inferred* (model, with confidence), *lookup* (external place data), and *confirmed* (user). Source data is never overwritten by derived data. Unknown places/dates stay unknown.
3. **Never infer an exact place from food appearance alone.** Dish identity supports a visit; it does not establish it.
4. **Corrections are a core flow.** Users can fix names, groupings, and place assignments, and the history (including the taste profile) updates visibly.
5. **Measured, not asserted.** Every model claim in the demo/submission traces to an eval result in a worklog entry (DISCOVERY §4 discipline).
6. **Public-repo safety.** No real photos, location exports, credentials, or personal identifiers in git — synthetic or consented, reviewed fixtures only (AGENTS.md). Real collections live in ignored local directories.

## 3. Scope tiers

### Must (demo core — the submission stands on these)
- Import: photos (EXIF timestamp/GPS where present) + **one** structured location source (Foursquare or Google, chosen by the E0 dataset inspection) over a user-selected scope.
- Local pipeline: classification (sightseeing / trip / personal / food + evidence types), embeddings, evidence extraction (signs/menus/receipts/dishes), visit/trip grouping, place resolution from check-ins + GPS + photo evidence, with confidence and abstention.
- Browse: **map, globe, and timeline** views over visits/trips; visit cards and place pages with evidence photos attached.
- Ask: natural-language (typed) questions in the golden-query families — vague memory, near-a-place, what-was-good-last-time — answered agentically over the local index, evidence shown, "unknown / haven't been" as a first-class answer.
- Corrections: rename a place, fix a grouping, confirm/reject an inferred visit; history updates.
- Contextual moment (at least one, demoable): repeat-restaurant ("what was good last time") and/or near-a-past-place surfacing.
- Demo dataset + eval: golden corpus with hand labels and golden queries (E0), headline metrics measured (E1/E3/E5/E6), 3-minute demo video (§10).

### Should (ship if Must is green by Nov 2)
- Glimmer-DE System-1 decision layer (E2b) replacing/augmenting generative routing, with calibrated probabilities.
- Taste profile v1 (recurrence + repeat visits + confirmed likes, evidence-linked, correctable).
- Voice input (push-to-talk query + spoken recollection) on local ASR if E7 passes; otherwise the labeled Muse Voice Transcribe option, off by default.
- Background organizing: watch-folder/incremental import that processes new photos without user action, plus a review queue of targeted questions.
- Shareable recommendation card/shortlist (privacy-safe export for sending to friends).
- Strix Halo portability numbers (E2 secondary arm) and a quantized Glimmer configuration.

### Stretch (explicitly droppable)
- SAM 3.1 segmentation in the pipeline (only on an E4 win).
- Muse channel integration (§8).
- Second location-source importer; direct account connections.
- Community/viral surfaces (shareable trip replay), Muse Image presentation material (clearly labeled, never as evidence).

### Out of scope
Glasses/continuous capture, general life-logging, desktop file indexing, phone-native apps (the PWA is the mobile surface), kernel tuning, generated imagery as historical content, multi-user/social features.

## 4. Users and core use cases

Primary user: someone with years of photos and location history who eats out and travels, and cannot retrieve their own experiences. Use cases (from BRAINSTORMING, prioritized):

1. **Recall to recommend** — "What did you love in Kyoto?" → named places, dishes, photos, including "the famous place was good, these were better."
2. **Reorder well** — at a repeat restaurant: what was ordered before and what was good.
3. **Geospatial recall** — "Near this neighborhood, what did I enjoy?" (place-anchored, not date-anchored).
4. **Half-remembered place** — "That little place with the grilled fish" → recovered visit with its evidence chain.
5. **Revisit/rebook** — the hotel before the ferry, the café near the station.
6. **Browse the story** — map/globe/timeline of trips and visits without ever having journaled.
7. **Stay organized effortlessly** — background classification/grouping; occasional one-tap answers to targeted questions.

## 5. System architecture

Single-user, local-first system with three planes. Provisional stack choices are marked *(verify)* — the first implementation tasks confirm or replace them with a short ADR in the worklog; do not treat them as settled.

```
┌──────────────────────────── PWA (browser, installable) ───────────────────────────┐
│  Map · Globe · Timeline · Trip/Visit/Place views · Ask (text/voice) · Review queue │
│  Taste profile · Share cards · Settings/privacy · Import & progress                │
└───────────────────────────────────┬───────────────────────────────────────────────┘
                                     │ local HTTP API (localhost / LAN, token-gated)
┌───────────────────────────────────▼───────────────────────────────────────────────┐
│  Crumbs service (Python/FastAPI *(verify)*)                                        │
│  Importers → normalized evidence store (SQLite *(verify)*) → pipeline orchestrator │
│  (job queue): classify → embed → extract → group → resolve → index                 │
│  Agent runtime (tool calling over local index) · Taste profile · Background worker │
│  Vector + geospatial index (sqlite-vec / FAISS + R-tree *(verify)*)                 │
└──┬──────────────┬───────────────┬───────────────┬───────────────┬─────────────────┘
   │              │               │               │               │
 Glimmer srv   Embedding srv   SAM 3.1 (local)  ASR (local /    Place lookup
 (vLLM/SGLang, (DINOv3/PE,     (if E4 passes)   opt. exception) (local cache;
  PRO 6000;     PyTorch/ONNX)                                   provider TBD §11)
  Glimmer-DE
  readout)
```

- **Model plane:** independently served local models behind OpenAI-compatible or thin local APIs, so each can be benchmarked, swapped, or dropped per DISCOVERY results. Glimmer generative and Glimmer-DE share one served checkpoint where possible (E2b decides the readout mechanism).
- **Data plane:** content-addressed media store (originals read-only, referenced in place where possible), normalized evidence store, append-only derived records with provenance, local vector/geospatial indexes. Everything under a user-chosen local data directory, ignored by git in development.
- **Experience plane:** installable PWA talking only to the local service. No account, no telemetry, no third-party calls from the client except map tiles (§7.4).

Deployment shape for the hackathon: one machine (PRO 6000 box) runs models + service; the PWA is served from the same box and opened on a phone/laptop browser on the local network for the demo. A single-machine localhost demo is the fallback and must always work.

## 6. Data model (conceptual)

| Entity | Key fields | Notes |
|---|---|---|
| `SourceImport` | id, kind (photos/foursquare/google), scope, imported_at, source ref | One import never mutates another |
| `MediaItem` | content hash, path/ref, captured_at (+tz +tz_source), gps?, width/height, import_id | Originals immutable |
| `LocationRecord` | source, external_id, name?, category?, lat/lon, visited_at, raw ref | Check-ins and location-history samples kept distinct |
| `Classification` | media_id, taxonomy labels, evidence types, model, checkpoint, probabilities, created_at | Multi-label (personal ∧ food is legal); versioned per model run |
| `Embedding` | media_id, model, vector ref | Multiple models may coexist during E1 |
| `Extraction` | media_id, visible_text, dish candidates, place-name candidates, fields, confidence, model/checkpoint | Structured schema, "cannot determine" is a value |
| `Place` | id, name (observed/lookup/confirmed states), lat/lon, external place id?, status | Candidate places distinct from confirmed places |
| `Visit` | id, place_id?, time window, status (observed/inferred/confirmed/rejected), confidence | The central object |
| `Trip` | id, name (inferred/confirmed), time window, visit ids | Trips group visits; stays are visits with lodging evidence |
| `DishOrder` | visit_id, name, evidence media ids, user_rating? | "What was good" = dish + explicit/derived signals, shown honestly |
| `Correction` | target, field, old, new, actor, at | Append-only; derived views recompute |
| `Question` | text/voice transcript, plan, tool calls, answer, evidence refs, outcome | Agent runs are inspectable, not magic |
| `TasteSignal` | kind (recurrence/repeat/confirmed-like/corrected), subject, evidence refs, weight | Profile is computed from these, never free-text model invention |
| `Job` | stage, entity ref, status, model, metrics, error | Pipeline observability |

Provenance enum everywhere: `observed | inferred | lookup | confirmed`. Confidence stored with every inferred field; UI renders the distinction (§9).

## 7. Pipeline (background, incremental, resumable)

1. **Ingest.** Scan user-selected folders/exports; hash and dedupe media; parse EXIF (timestamp, tz inference, GPS); parse the location export into `LocationRecord`s. Nothing is uploaded anywhere. *(Dependencies: R1 export-format inspection.)*
2. **Classify + embed (System 0/1).** DINOv3/PE embeddings for every photo; taxonomy + evidence-type classification by the E1 winner (PE zero-shot, trained head, and/or Glimmer-DE from E2b). Bursts/near-duplicates grouped. This stage is cheap and total: every photo gets embeddings and labels.
3. **Extract (System 2, selective).** Only evidence-bearing candidates (receipts, menus, signs, storefronts, dishes in unresolved contexts) go to generative extraction (Glimmer; PLM comparator per E3; SAM 3.1 crops only on an E4 win). Output is schema-validated structured data with abstention.
4. **Group.** Deterministic pre-grouping by time gaps, GPS, check-in proximity, and visual similarity → candidate visits and trips; timezone-aware.
5. **Resolve.** Glimmer reconciles each candidate visit against check-ins, location records, extractions, and neighboring photos; emits place candidates with evidence links and confidence, or an explicit unknown plus at most one targeted question for the review queue. Place lookup (provider TBD, cached locally) may enrich *named* places; it never invents a visit.
6. **Index + profile.** Visits/places/dishes indexed for text, vector, and geospatial query; taste signals updated; taste profile recomputed from signals.
7. **Serve + surface.** API answers browse/ask/correction flows; contextual rules (geofence-like local triggers, repeat-place detection) produce the contextual options feed. All triggers computed locally.

Every stage is a restartable job with per-item status; re-running a stage with a new model creates new versioned records rather than overwriting (model comparison and rollback stay possible).

### 7.4 Map tiles and the local-only claim (explicit caveat)
Map tiles fetched from a public tile server reveal the viewed region to that server. To keep the privacy claim clean: prefer downloadable/offline vector tiles for the demo regions, or a locally served tile cache; at minimum disclose tile traffic in Settings ("map tiles are fetched from <provider>; your photos and history never leave this device"). Globe view may use the same tile source. Verify the chosen library/provider terms in R6 (§11).

## 8. Channels and interfaces

- **PWA (primary).** §9 flows. Installable, works on the demo LAN/localhost, responsive phone-first for contextual flows and desktop-first for review/correction.
- **Voice (interface, not a separate product).** Push-to-talk in Ask and in "add a recollection": audio → transcript (local ASR if E7 passes; else optional, labeled Muse Voice Transcribe, off by default; else typed only) → the same agent. Transcripts are stored as user-provided evidence with provenance `confirmed` only after user review.
- **Muse channel (stretch, two readings, both optional).** (a) *Development:* the system is built with Muse Code and other coding agents against this repo (mention in submission). (b) *Product:* expose the agent's query tools over a small local API/MCP-style interface so a Muse chat/coding-agent channel can ask Crumbs questions ("what did I order at X?") and receive evidence-linked answers. The PWA never depends on it; it ships only if Must/Should are green, and it runs against the same local service — no cloud copy of the history.
- **Share export.** Static, user-reviewed recommendation card/list (image/text) generated locally for sending to friends; only user-confirmed items, no location history beyond the named places the user selects.

## 9. PWA experience (flows)

Design language: a travelogue, not a dashboard. Photos are the primary visual material; confidence is shown as language ("confirmed", "inferred from receipt + check-in", "unknown"), not raw percentages except in detail views.

1. **First run / Import.** Pick photo folders + one location export → scope summary (counts, date range, "processing stays on this device") → live progress per pipeline stage with honest throughput ("1,240 photos classified locally") → lands in the Timeline with the first trips already grouped. A preloaded **demo mode** (consented/synthetic dataset) is available for judges.
2. **Home / Context.** Taste-profile summary strip, recent visits, contextual options feed ("You're near X — last time you had…", "Back in Kyoto? Your shortlist"), review-queue badge (targeted questions awaiting answers, each answerable in one tap).
3. **Map.** 2D map (MapLibre *(verify)*) with visit pins clustered by trip; filters: trip, category (food/sightseeing/lodging/personal), date; selecting a pin opens the visit card. Offline/cached tiles for demo regions (§7.4).
4. **Globe.** 3D globe (MapLibre globe projection or equivalent *(verify)*) showing trip arcs/clusters worldwide; spinning to a trip flies into its Map. This is the "your world" hero view and the demo's opening shot.
5. **Timeline.** Chronological river of trips → visits, with classification facets (sightseeing/trips/personal/food) and search-as-you-scroll; unknown/uncertain items visibly marked, not hidden.
6. **Trip view.** Ordered visits, stays, map mini-view, day grouping, share-card generation.
7. **Visit card / Place page.** Hero photos by evidence type (dish, menu, receipt, storefront), what was ordered, visit history (repeat visits!), provenance line per fact ("from check-in", "read from receipt photo", "you confirmed"), correction actions.
8. **Ask.** Text (+voice) box with example prompts; answers render as place/visit cards with the evidence chain and the agent's lookup steps summarized; "unknown / you haven't been there" states designed, not apologetic. Follow-ups keep context (place, trip).
9. **Review queue.** One-question-at-a-time cards ("Was this the place near the station?" with candidate photos), confirm/correct/skip; each answer visibly updates the visit and profile. This flow is the correction demo.
10. **Taste profile.** Recurring dishes/cuisines/places with counts, evidence thumbnails, confirmed likes, and per-item correct/remove. Framed as "what your photos show", with the frequency-bias caveat in plain language.
11. **Settings / Privacy.** Local-processing status (models, hardware, "no cloud model calls" — with the voice exception named if enabled), tile-provider disclosure, data directory, export/delete my data, demo-mode toggle.

## 10. Demo and submission (Nov 4, 9:00 PM ET)

**3-minute video script (Must-scope only, recorded by Nov 3):**
1. (0:00–0:25) The problem in one scene: scrolling a camera roll, failing to name the grilled-fish place. Globe opens — "your trips, rebuilt locally."
2. (0:25–1:10) Import a messy trip → background pipeline classifies/groups live on local hardware (show the local models working; no API calls) → map/timeline populate; one visit resolved *only* by combining receipt + storefront + check-in, evidence chain shown.
3. (1:10–1:50) Ask the vague-memory question (voice if ready) → recovered place with photos; then "what was good last time?" at the repeat restaurant.
4. (1:50–2:25) Contextual moment + correction: near-a-place card; fix one wrong grouping in the review queue and watch the visit/profile update; ask something unanswerable → honest unknown.
5. (2:25–3:00) Taste profile + recommendation shortlist to share; close on privacy: "every model ran on this box" with the measured numbers (photos/hour, accuracy, abstention) on screen.

**Judging alignment:** Stage-One fit (themes + Meta open-weight models, built in-period) stated explicitly; Impact = frequent practical moments with the honest qualitative claim; Meta tooling = Glimmer post-trained decision layer + DINOv3/PE/SAM, served and evaluated locally; Technical depth = measured pipeline + provenance model; Demo = live-working system over a public repo, demo-only features clearly identified as built in-period. Track: **Indie Developer**. Bonus flags to claim only if built and measured: **Best Build on Meta Open Weight Models** (Glimmer), **Best Agentic Use-Case** (background agent + agentic retrieval). Submission checklist (from README §7–§8): public repo, accessible video, all contributors listed, one Representative, models/bonus flags accurate.

**Build-in-period hygiene:** features shown must be built during the hackathon; pre-existing assets (the DE pattern, prior model work) are prior art to cite, not to present as built in-period.

## 11. Research dependencies and caveats (the spike register)

Nothing in §3 Must may quietly depend on an unproven item. Each dependency has a fallback and a decision date; status lives in DISCOVERY worklog entries.

| ID | Dependency / unknown | Blocks | Fallback if negative | Decide by |
|---|---|---|---|---|
| R1 | Foursquare/Google export formats, fields, tz/precision (E0 inspection) | Importer choice, grouping quality | Photos-only grouping (time+GPS+visual); second source later | Oct 28 |
| R2 | Golden corpus size/labels achievable in time (E0) | All eval claims | Smaller corpus; claims shrink to what is measured | Oct 28 |
| R3 | Glimmer bf16 serving throughput on PRO 6000 (E2) | Pipeline latency, demo scale | Quantized Glimmer; smaller corpus for demo; PLM takes extraction volume | Oct 29 |
| R4 | Glimmer-DE readout mechanics: single-token option codes, logprob coverage, LoRA training (E2b) | System-1 layer (Should) | Generative routing with schema validation; PE/DINO classification only | Oct 30 |
| R5 | Local extraction quality incl. Japanese text (E3: Glimmer vs PLM) | Place resolution, dish identity | Confirmation-first UX (drafts + review queue carries more load); never lower the abstention bar silently | Oct 30 |
| R6 | Map/globe library + tile provider terms, offline tiles for demo regions (§7.4) | Map/Globe flows | Static rendered map images for demo; globe via the same library's fallback projection | Oct 29 (spike done Oct 27: `spike/map-globe/` — MapLibre v5 globe+Mercator, OpenFreeMap/CARTO/OSM-raster styles; fully-local PMTiles mode implemented and offline-verified Oct 27 — regional Protomaps extracts + local glyphs/sprites via `spike/map-globe/tools/fetch-tiles.sh`; see its README) |
| R7 | SAM 3.1 gated checkpoint access + E4 value | Segmentation (Stretch) | SAM 2 (Apache) or no segmentation; whole-image extraction | Oct 31 |
| R8 | Place-lookup provider: access, terms, attribution, offline caching | Place enrichment, canonical names | Check-in/source names only; "unnamed place at <area>" labels | Oct 30 |
| R9 | Local ASR quality incl. Japanese (E7); Muse Voice Transcribe language list | Voice (Should) | Typed Ask only; voice cut without penalty to Must | Nov 1 |
| R10 | Strix Halo Glimmer multimodal via llama.cpp/ROCm-Vulkan (E2 secondary) | Portability claims | PRO 6000 stated as the reference hardware; consumer story = embeddings/classification only | Nov 1 |
| R11 | Licenses for redistribution/claims: DINOv3 ("Built with DINOv3"), SAM License, PLM FAIR Research, Seamless CC BY-NC, PE Apache, Glimmer Apache, map/place attribution | Submission, public demo, any distribution | Drop or replace the encumbered component in shipped claims; legal notes in submission | Nov 2 |
| R12 | Taste profile beats frequency baseline (E6) | Taste profile (Should) | Ship recurrence lists as plain "most photographed" facts with bias labeling, no "profile" claim | Nov 1 |
| R13 | Agentic retrieval beats plain vector search on golden queries (E6) | Agentic bonus claim, Ask design | Ask = filtered search over evidence index; agent claims removed from demo/submission | Nov 1 |
| R14 | PWA on demo phone over LAN + installability quirks (service worker, mixed content, large payloads) | Demo reliability | Localhost-on-laptop demo; PWA still shipped, phone view recorded in video | Nov 2 |

## 12. Schedule (building period)

| Date | Focus | Exit criteria |
|---|---|---|
| Tue Oct 27 | Docs spike: BRAINSTORMING/DISCOVERY/this PLAN + IMPLEMENTATION; rubric mapping | Docs committed; agents can start §13 workstreams |
| Wed Oct 28 | E0 corpus + export inspection (R1/R2); repo/platform skeleton; importer v1; Glimmer serving smoke (E2 start) | Corpus labeled slice exists; photos import end-to-end (no models) |
| Thu Oct 29 | E1 embeddings/classification; E2 serving benchmark; storage/index; map+globe tech spike (R6) | Classification numbers on labeled slice; throughput number on PRO 6000; map renders real pins |
| Fri Oct 30 | E3 extraction; grouping v1; Glimmer-DE feasibility (R4); place resolution v1 | Extraction metrics; first end-to-end visits on demo corpus |
| Sat Oct 31 | E5 reconstruction; timeline/map/visit UI; corrections v1; E4 probe (R7) | Golden-query dry run; correction round-trip works |
| Sun Nov 1 | E6 agent + golden-query eval; taste profile v1 (R12/R13); voice probe (R9); Strix Halo arm (R10) | Agent vs search comparison measured; Must feature-complete |
| Mon Nov 2 | Hardening: background/incremental, contextual feed, share card, license pass (R11), PWA demo reliability (R14) | **Feature freeze for Must/Should**; demo dataset locked |
| Tue Nov 3 | Demo recording, submission draft, eval report write-up, rehearsal on demo hardware | Video recorded; submission form drafted; repo public-ready |
| Wed Nov 4 | Buffer, final checks, submit by 9:00 PM ET (aim: noon) | Submitted; no new features after noon |

## 13. Workstreams (agent lanes)

- **WS-Research (models/eval):** DISCOVERY E0–E7 execution, Glimmer serving, Glimmer-DE training, eval harness and reports. Owns R2–R5, R7, R9, R10, R12, R13 measurements.
- **WS-Data (platform):** importers, schema/store, pipeline orchestration, indexing, agent runtime, background/contextual services, API. Owns R1, R8.
- **WS-Product (PWA):** all §9 flows, map/globe/timeline, Ask/voice UI, share/settings, demo mode. Owns R6, R14 jointly with WS-Data.
- **WS-QA/Demo:** end-to-end tests, demo dataset curation, video, submission, license/attribution pass (R11, with WS-Research).

Coordination rules are AGENTS.md's (worklog per logical unit, exact-path staging, public-safety). High-conflict files (this plan, IMPLEMENTATION.md, schema, taxonomy, API contracts) get one owner per workstream at a time; contract changes land before dependent tasks start.

## 14. Risks (top)

1. **Scope vs. Nov 4.** Mitigation: Must tier is a vertical slice; Should/Stretch are pre-cut in writing (§3), and §12 freezes features Nov 2.
2. **Local model quality insufficient on real photos** (signs/Japanese/abstention). Mitigation: E3 measures early (Oct 30); confirmation-first UX is a designed fallback, not an apology; claims track measurements.
3. **Glimmer throughput makes import feel broken.** Mitigation: embeddings-first progress (library browsable before extraction finishes), staged pipeline visibility, demo corpus sized to measured throughput.
4. **Demo data privacy.** Mitigation: only the consented/synthetic demo subset on camera; real collections never leave ignored local directories; no private locations or bystanders in any public artifact.
5. **Anti-project misreading** ("image analyzer + RAG"). Mitigation: demo leads with reconstruction across sources, abstention, and corrections; agent must beat the search baseline (R13) or the claim is dropped.
6. **License/access surprises** (SAM gating, PLM/Seamless terms, tile/place terms). Mitigation: R11 pass on Nov 2 with drop/replace fallbacks already named.
