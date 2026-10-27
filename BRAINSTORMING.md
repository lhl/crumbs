# Brainstorming

Working notes for the hackathon project. See [README.md](README.md) for rules, judging rubric, and deadlines.

## Current direction: Crumbs (working name)

**Travel and food history reconstructed from photos and personal location history.** This is our preferred project direction as of 2026-10-27; the name and implementation are not finalized. Earlier ideas and hardware research are retained below for reference, not as the active build plan.

> **Crumbs** — Rediscover where you went, stayed, and ate.
>
> Not another journal to fill in: combine your photos, check-ins, and location history into a searchable travelogue, with trips, restaurant visits, meals, and stays linked to their supporting evidence.

### The problem

We already have photos of our travels and meals, but finding the experience behind them is hard. We remember a dish, a neighborhood, or what happened before or afterward—not the restaurant name or the date. This is a firsthand problem, including local restaurants and everyday discoveries, not just vacations.

Questions we want to answer:
- “What was that little restaurant in Kyoto where we had the grilled fish?”
- “Which hotel did we stay at before taking the ferry?”
- “Show me the coffee shops I visited in Taipei.”
- “When did we last go there, and what did we order?”
- “Put together that entire trip—I never made an album.”

### Why it matters beyond nostalgia: practical recall in the moment

The recurring pain is not reminiscing at home; it is being unable to look anything up *during a conversation or a decision*. Someone asks what was worth eating in Kyoto, or whether the famous popup was actually the best meal of that trip — and the answer exists in our photos but cannot be retrieved, named, or shared. Crumbs should make past experience usable:

- **Recommend and share from evidence:** answer “what did you love in Kyoto?” with named places, the dishes, and the photos to send a friend — including “the famous place was good, but these two were better,” which no current photo app can produce.
- **Order well next time:** at a repeat visit, pull up what we ordered before and what was good, instead of guessing from the menu. “What was good last time?” is a perennial, concrete pain point.
- **Geospatial recall:** “near this neighborhood / near where I am, what did I previously enjoy?” — search anchored in place, not in filenames or dates.
- **Revisit and rebook:** recover the hotel, the coffee shop near the station, the place worth returning to, with its evidence attached.

### Classification is a core feature, not a by-product

Sorting a library into **sightseeing, trips, personal, and food** (and, within those, evidence types such as dish, menu, receipt, sign, storefront, lodging, landmark) is itself a headline capability: it is what turns an undifferentiated camera roll into a browsable travel and food history. This classification should run **locally and privately on open models** (see [DISCOVERY.md](DISCOVERY.md)) — a large photo library should not have to leave the user's machine to be organized. Category boundaries are genuinely ambiguous (a family dinner is both personal and food); the taxonomy, its local classifier, and its measured accuracy are discovery experiment E1, not an assumption.

### The background agent: organized without being asked

Because the whole stack runs locally (see the local-only decision in [DISCOVERY.md](DISCOVERY.md)), Crumbs can work **in the background, always-on, without sending a life-log to a cloud service**: new photos are classified, grouped into visits, and reconciled with location records as they arrive; the taste profile stays current; and the only interruptions are occasional, targeted questions where evidence genuinely cannot decide (“was this the place near the station?”). This is the role Muse Glimmer is explicitly built for (always-on local agents), and it is what makes the history *ready at the moment of need* instead of being a reconstruction you run and wait for.

### Contextual options: the right memory at the right moment

The payoff of a current, local, evidence-linked history is surfacing **contextual options** at decision moments, under the user's control:

- **Arriving somewhere:** entering a neighborhood or city brings up what you previously enjoyed nearby — places, dishes, and the photos that prove it.
- **Sitting down at a repeat restaurant:** what you ordered last time and what was good, before you decide.
- **Talking or planning:** a friend asks for Kyoto recommendations, or a return trip is being planned — a shareable, evidence-backed shortlist in seconds, including “skip the famous place, these were better.”
- **About to reorder or rebook:** the hotel, café, or dish you already know you liked, with its visit attached.

Local processing is what makes proactive surfacing acceptable rather than creepy: the location triggers and the history never leave the device, triggers are user-configured, and every surfaced item links to its evidence. Contextual surfacing must be conservative — wrong or noisy prompts would destroy trust faster than no prompts — so precision and easy dismissal matter more than recall here.

### Agentic retrieval and a factual taste profile

On top of the reconstructed history, an agent should answer compound questions by planning lookups — geospatial filter → past visits → dishes/orders → evidence — e.g. “near X, what did I enjoy?” or “what should I order again at this place?” Every answer shows the photos and records behind it; “you have not been there / unknown” is a valid answer.

The same history supports a **taste profile**: which dishes, cuisines, and places recur, which places earned repeat visits, and what the user explicitly confirmed liking. This must stay factual and evidence-linked — photo frequency is biased (photogenic meals and trips are over-photographed; everyday favorites are under-photographed), so recurrence is a signal to show with its evidence, never an opaque verdict, and always correctable. It is a food-and-place preference summary, not a personality analysis.

### Product: visits and trips, not just photo tags

The primary objects are **trips, visits, meals, and stays**. Photos, check-ins, and location records are evidence for those objects, rather than isolated images with generated captions.

### Input sources: more than photos

We have Foursquare location data, Google data, and potentially other location-history sources to draw on. Exact available exports, fields, and access methods still need inspection; do not assume a provider offers a usable API or complete historical export.

- **Photos:** visual details, timestamps, and GPS where available. Photos are a decent start on their own — treat them as the primary source for the first build.
- **Foursquare:** available check-in/location records may supply named places and visit times.
- **Google:** available location-history or other relevant exports may supply additional movement and place evidence; confirm the actual dataset and format.
- **Stretch sources (only if spare time):** flight itineraries (Flighty, TripIt), GPS/fitness tracks (Wandering, Garmin), and lodging/travel bookings (Booking.com plus other booking emails searchable via msgvault). These could connect info across trips and stays, but each needs its export/schema inspected before any importer is promised.
- **Other personal location sources:** add import adapters as concrete datasets become available, rather than promising universal integrations.

This makes the project a **multi-source personal travel and food history**, not just a photo organizer. Location records can suggest visits with no photos; photos can supply the meal or experience behind a check-in. Neither source alone has to tell the whole story.

Normalize imported evidence while retaining source identifiers, original timestamps/timezones, coordinates, and source-provided place names or identifiers where present. Reconcile duplicate observations into visits without discarding provenance. A location sample near a restaurant does not prove we ate there; distinguish a nearby observation, a recorded check-in, and a user-confirmed visit. Conflicting sources should remain inspectable and correctable.

For the first build, pair the photo collection with one available structured location export covering the same period. Prefer explicit user-selected imports initially; direct account connections are a later option, subject to provider access and consent.

### Reconstruction pipeline

Proposed pipeline:
1. Import photos and available check-in/location exports; normalize metadata and retain source provenance.
2. Extract visual evidence: signs, receipts, menus, dishes, landmarks, and accommodation details.
3. Group related photos and location records into visits and trips, accounting for missing metadata, timezones, and ambiguous boundaries.
4. Resolve places by combining check-ins, location history, photo metadata, visible text, neighboring photos, and optional map/place lookups.
5. Preserve evidence and uncertainty for each inferred detail; allow users to correct names and groupings.
6. Browse the reconstructed history through a map, timeline, and visit cards; search using natural-language memories.
7. Answer compound, place-anchored questions agentically over the reconstructed history (prior visits, dishes, and orders near a place), and maintain the evidence-linked taste profile described above.

All steps run locally (local-only decision, [DISCOVERY.md](DISCOVERY.md)): DINOv3 and Muse Glimmer on the user's hardware. Unresolved cases produce a targeted question or an explicit unknown, never a cloud call. Which local model fills each step is decided by the experiments in DISCOVERY.md, not assumed here.

**The technical core is event reconstruction and place resolution, not captioning or basic retrieval-augmented chat.** A food photo may not identify a restaurant, but a nearby receipt and exterior photo can jointly establish the visit. Answers should show that evidence.

### Why this is our leading hackathon choice

- **Build for Your World:** solves a recurring personal problem using an existing photo collection.
- **Impact:** recover places and experiences without manually maintaining a journal — and make them usable in the moment: recommending to friends, reordering what was good, and recalling what you enjoyed near a place (see “Why it matters beyond nostalgia” above). This does not save anyone's life; the claim is narrower and honest — a qualitative improvement that recurs at ordinary, frequent moments (eating out, traveling, recommending, planning), for anyone with years of photos they cannot search. Usefulness at frequent small moments, not severity of a single moment, is the impact argument; it only holds if the answers are fast, correct, and evidence-backed, which is why abstention and corrections are core features rather than polish.
- **Meta tooling:** multimodal reasoning has a necessary role in combining visual and textual clues across photos.
- **Technical depth:** visit grouping, place resolution, conflicting evidence, uncertainty, correction, and evidence-backed retrieval — on a **fully local, multi-model stack** (DINOv3/Perception Encoder embeddings, a Glimmer-derived decision layer, generative Glimmer reconstruction, local SAM 3.1 segmentation; DISCOVERY.md). Nothing about the core is an API wrapper: the models are open weights we serve, post-train, calibrate, and evaluate ourselves on our own hardware. That self-built stack, and the measurements behind it, are the technical-depth claim.
- **Demo:** a messy photo folder becomes a navigable map and timeline, followed by a successful search for a half-remembered restaurant — and a contextual moment: arriving near a past place, or sitting down at a repeat restaurant, surfaces what was good last time.

This is a stronger-defined evolution of the family photo archivist idea below. It has a more bounded demonstration than general memory glasses and a more visual result than desktop file search. It must demonstrate reconstruction beyond a simple image analyzer or basic RAG application; eligibility is not guaranteed by the framing alone.

### Candidate model roles — validate before committing

Use multiple models where they improve the result, not to maximize model count. These are proposed roles, not tested integrations; model capabilities and access still need verification.

| Model | Potential role | Scope decision |
|---|---|---|
| Muse Spark / Spark Open | Cloud quality ceiling only: a development oracle to measure local models against on the consented demo subset | Not in the shipped pipeline — the local-only decision (DISCOVERY.md) excludes API and partner-hosted models from processing; oracle use is disclosed wherever its numbers are quoted |
| Muse Glimmer | Local image triage, structured extraction, or orchestration of targeted follow-up analysis — the local core. Includes a possible **Glimmer-DE** variant: a LoRA-trained restricted-readout decision layer (single-forward, calibrated yes/no and multiple-choice answers, in the pattern of Shisa DE-2.1) for fast System-1 routing/abstention decisions, escalating to generative Glimmer reasoning when unsure | Include if quality, latency, and hardware requirements are practical; open-weight bonus candidate (DISCOVERY E2/E2b/E3) |
| DINOv3 (Meta FAIR, open weights, DINOv3 License) | Local embeddings: duplicate/burst grouping, same-dish/same-storefront matching, and a small trained head for the sightseeing/trip/personal/food classification | Supporting infrastructure, not the headline Meta model: the open-weight bonus names Glimmer/Spark Open only. Test in DISCOVERY E1 |
| SAM 3.1 (open checkpoints) | Isolate relevant regions such as signs, receipts, or dishes for downstream analysis, locally | The API is excluded by the local-only decision, but Meta also released open SAM 3/3.1 checkpoints (848M, SAM License, gated access) — DISCOVERY E4 tests local SAM 3.1 against whole-image extraction; segmentation does not itself identify a place or dish |
| Muse Voice Transcribe | Spoken recollections or voice search | Stretch; not required for the photo-to-history workflow |
| Muse Image / Muse Wonder | Potential illustrative presentation features | Defer; verify capabilities and never treat generated imagery as historical evidence |

An agentic extension could identify a missing clue, select related photos or a place lookup, and reconcile the result. That is more useful than adding an agent solely for bonus eligibility. **Processing is local-only by decision (see DISCOVERY.md):** all image classification, extraction, reconstruction, and retrieval run on local open models (Muse Glimmer + DINOv3) on the user's hardware (RTX PRO 6000 reference; Strix Halo portability target). The only possible cloud exception is optional voice transcription (Muse Voice Transcribe, off by default, audio only) — while it exists, public wording must say exactly that, never an unqualified “nothing leaves the device.”

### Hackathon scope and demo

Start with one real, messy trip collection, ideally including food, accommodation, signs, and receipts, plus an overlapping Foursquare or Google location dataset. Include local outings if useful to show that the product is not vacation-only.

Core demo:
1. Import photos and location records and build a map/timeline of inferred visits; show a place or visit that the combined evidence resolves better than photos alone.
2. Open a restaurant card containing related food, menu, receipt, and exterior photos where available.
3. Ask a real vague-memory question and recover the place with visible evidence.
4. Correct an incorrect grouping or place name and show the history update.

Core scope: photo and one structured location-source import, evidence extraction, cross-source reconciliation, visit/trip grouping, place resolution, map/timeline/cards, search, and user corrections. Defer glasses, continuous capture, general life logging, desktop indexing, phone-only inference, kernel tuning, and generated travel imagery.

Trust boundaries:
- Preserve original photos and location exports; derived records must not overwrite source data.
- Photos and location records are incomplete and sometimes inaccurate, not proof of a person's full movements. Combining them can expose sensitive routines; let users select the imported scope and avoid sending raw location history to cloud models unnecessarily.
- All image and location processing runs locally on open models; no photo or location record is sent to a cloud model API. Optional voice transcription is the sole exception, off by default and labeled as such.
- Do not infer an exact restaurant from food appearance alone.
- Keep unknown places and uncertain dates rather than forcing confident answers.
- Distinguish observed facts, model inferences, external lookup results, and user confirmations.
- Make cloud processing explicit and use only photos we have permission to process and show. Avoid exposing private locations or bystanders in the public demo.

### Naming notes

**Crumbs** is the current working-name candidate: short, food-related, and suggestive of following clues back through your history. Name/domain/trademark availability has not been checked.

Other directions considered: Breadcrumbs, Been There, Places & Plates, Wayback Table, My Travelogue, and Personal Atlas. “Automatic travelogue” works as a category description; “personal almanac” is broader but less immediately connected to photos, places, and food. The subtitle should make clear that local visits count too.

### One-liners and pitch options

Draft copy for the proposed product, not claims of implemented functionality.

#### Clear and descriptive
- Turn your photos and location history into a searchable story of where you went, stayed, and ate.
- Your travel and food history, pieced together from photos, check-ins, and places you’ve been.
- A personal travelogue built from the memories you already captured.

#### Problem-first
- Remember the meal. Find the restaurant.
- Find that place you never forgot—but can’t remember the name of.
- You took the photos. Crumbs connects the trip.

#### Short taglines
- Every trip leaves Crumbs.
- Rediscover where you went, stayed, and ate.
- Your photos remember more than you think.
- A travelogue you never have to write.

#### Hackathon pitch
- Crumbs uses multimodal AI to connect scattered photos and location records into an evidence-backed, searchable history of your travels and meals.
- Crumbs reconstructs your trips from photos, check-ins, and location history—so you can find places by what you remember, not what you named them.

#### Recommended project-page pairing

> **Crumbs — A travelogue you never have to write.**
>
> Turn your photos, check-ins, and location history into a searchable memory of where you went, stayed, and ate.

### Next checks for Crumbs

Model and hardware questions are tracked as experiments E0–E7 in [DISCOVERY.md](DISCOVERY.md), which gates PLAN.md. Remaining product-side checks:

- [ ] Select a representative photo collection and overlapping location records we can process; choose a privacy-safe subset for the public demo.
- [ ] Inspect available Foursquare, Google, and other location datasets (Flighty/TripIt, Wandering/Garmin, Booking.com + msgvault booking emails as stretch): export/access method, schema, timestamps/timezones, place identifiers, precision, and coverage. Choose the first structured-source importer; photos alone are a sufficient start.
- [ ] Write real retrieval questions and manually establish reference visits/place identities, including unknowns and conflicting source records.
- [ ] Inspect metadata coverage, supported photo formats, timezone issues, and missing GPS.
- [ ] Test Meta models on signs, receipts, food, and cross-photo place identification; measure errors, latency, and cost.
- [ ] Choose a map/place data source and verify access, attribution, usage terms, and location privacy implications.
- [ ] Prototype visit grouping and evidence-linked records before expanding the model stack.
- [ ] Evaluate grouping, place identification, and retrieval against the reference examples; test corrections and unsupported-answer behavior.

### Separate future idea: desktop file discovery

Another firsthand problem: large collections of files are difficult to search when we remember the content or context rather than the filename. A possible project would retrieve documents, screenshots, charts, and code; group duplicates/versions; and connect artifacts to their source data or scripts using supporting evidence. Existing indexing tools exist—the opportunity is better contextual retrieval, not claiming the category is empty.

This could be a valuable local-model project, but broad format support and incremental indexing would consume substantial scope. Keep it separate from Crumbs. The shared motivation is recovering personal history from existing artifacts; the travel-and-food project is the chosen direction for its bounded collection and visual demonstration.

## Model notes (from dev.meta.ai model pages, 2026-10-27)

| Model | What matters for us |
|---|---|
| **Muse Glimmer** (open, Apache 2.0) | 30B, text + image in. Built for **always-on local agents**: reliable tool calling, persistent state across restarts, self-managed memory, "hours-long sessions". Targets single consumer GPU / Mac. Runtimes: llama.cpp, vLLM, ExecuTorch, Ollama, LM Studio, Unsloth. Speculative decoding mentioned. |
| **Muse Spark Open** (open) | ~816B-A42B MoE (per vLLM/Azure naming). Image + video + document input, reasoning, computer use, multi-agent / subagent fan-out. Datacenter-class — run via Baseten/Modal/Fireworks (`meta-models/muse-spark-open-1026` on Baseten), not locally. |
| **Muse Voice Transcribe** (API) | **Streaming** ASR with built-in diarization (20+ speakers), live turn tracking, end-of-speech detection, keyword/context biasing. OpenAI-SDK compatible, `muse-voice-transcribe-1.0`, $0.18/hr. Docs (2026-10-27) say 25 evaluated languages with code-switching; Japanese support still **unconfirmed** — check the language list. |
| **DINOv3** (open, DINOv3 License) | Meta FAIR self-supervised vision backbones (ViT-S 21M → ViT-7B, ConvNeXt 29–198M). Frozen backbones give dense features for similarity/matching and small trained classification heads, no fine-tuning of the backbone needed. Runs locally on modest hardware. Cannot read text or name dishes — pair with Glimmer/Spark. License requires a “Built with DINOv3” display on redistribution. |
| **Muse Spark 1.3** (API) | Current Spark version, recommended for new work: 1M-token context, image/video/audio/PDF input, tool calling, structured output. Standard mode does not train on content; Contributor mode is discounted and may. Audio understanding is degraded in 1.3 (docs point to 1.2 or Voice Transcribe). |
| **Muse Glimmer on Strix Halo** | **Measured (2026-10-28).** The verified-platform docs list Intel/NVIDIA only and vLLM's image is CUDA-only, but the HIP build of mainline llama.cpp runs the official Q4_K_M GGUF + mmproj vision tower (+ dflash draft) end-to-end on the Radeon 8060S: real photo descriptions and exact text transcription work; full-res photo prefill ≈ 47 s/photo makes it a background-organizing pace, not bulk-import pace. Numbers and limits: DISCOVERY §3 / E2. |
| **Muse Spark** (API) | Frontier multimodal + agentic. Not used in the shipped pipeline (local-only decision); at most a disclosed development oracle for measuring local-model quality on the consented demo subset. |
| **SAM 3.1** (API) | Segmentation / tracking (text-promptable). |
| **Muse Image / Muse Wonder** (API) | Image gen / (TBD — check what Wonder actually is). |
| **Muse Code** | Coding agent — use it to build, and mention it in the submission. |
