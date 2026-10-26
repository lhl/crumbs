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

### Product: visits and trips, not just photo tags

The primary objects are **trips, visits, meals, and stays**. Photos, check-ins, and location records are evidence for those objects, rather than isolated images with generated captions.

### Input sources: more than photos

We have Foursquare location data, Google data, and potentially other location-history sources to draw on. Exact available exports, fields, and access methods still need inspection; do not assume a provider offers a usable API or complete historical export.

- **Photos:** visual details, timestamps, and GPS where available.
- **Foursquare:** available check-in/location records may supply named places and visit times.
- **Google:** available location-history or other relevant exports may supply additional movement and place evidence; confirm the actual dataset and format.
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

**The technical core is event reconstruction and place resolution, not captioning or basic retrieval-augmented chat.** A food photo may not identify a restaurant, but a nearby receipt and exterior photo can jointly establish the visit. Answers should show that evidence.

### Why this is our leading hackathon choice

- **Build for Your World:** solves a recurring personal problem using an existing photo collection.
- **Impact:** recover places and experiences without manually maintaining a journal.
- **Meta tooling:** multimodal reasoning has a necessary role in combining visual and textual clues across photos.
- **Technical depth:** visit grouping, place resolution, conflicting evidence, uncertainty, correction, and evidence-backed retrieval.
- **Demo:** a messy photo folder becomes a navigable map and timeline, followed by a successful search for a half-remembered restaurant.

This is a stronger-defined evolution of the family photo archivist idea below. It has a more bounded demonstration than general memory glasses and a more visual result than desktop file search. It must demonstrate reconstruction beyond a simple image analyzer or basic RAG application; eligibility is not guaranteed by the framing alone.

### Candidate model roles — validate before committing

Use multiple models where they improve the result, not to maximize model count. These are proposed roles, not tested integrations; model capabilities and access still need verification.

| Model | Potential role | Scope decision |
|---|---|---|
| Muse Spark / Spark Open | Interpret images and reconcile evidence across photos to reconstruct visits and identify places | Test first on a real trip, including ambiguous examples |
| Muse Glimmer | Local image triage, structured extraction, or orchestration of targeted follow-up analysis | Include if quality, latency, and hardware requirements are practical; open-weight bonus candidate |
| SAM 3.1 | Isolate relevant regions such as signs, receipts, or dishes for downstream analysis | Optional; segmentation does not itself identify a place or dish |
| Muse Voice Transcribe | Spoken recollections or voice search | Stretch; not required for the photo-to-history workflow |
| Muse Image / Muse Wonder | Potential illustrative presentation features | Defer; verify capabilities and never treat generated imagery as historical evidence |

An agentic extension could identify a missing clue, select related photos or a place lookup, and reconcile the result. That is more useful than adding an agent solely for bonus eligibility. Local processing is attractive for privacy, but do not claim local-only operation if images or location data go to cloud services.

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

- [ ] Select a representative photo collection and overlapping location records we can process; choose a privacy-safe subset for the public demo.
- [ ] Inspect available Foursquare, Google, and other location datasets: export/access method, schema, timestamps/timezones, place identifiers, precision, and coverage. Choose the first structured-source importer.
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
| **Muse Voice Transcribe** (API) | **Streaming** ASR with built-in diarization (20+ speakers), live turn tracking, end-of-speech detection, keyword/context biasing. OpenAI-SDK compatible, `muse-voice-transcribe-1.0`, $0.18/hr. Japanese support **unconfirmed** — check. |
| **Muse Spark** (API) | Frontier multimodal + agentic; the "big brain" escalation target. |
| **SAM 3.1** (API) | Segmentation / tracking (text-promptable). |
| **Muse Image / Muse Wonder** (API) | Image gen / (TBD — check what Wonder actually is). |
| **Muse Code** | Coding agent — use it to build, and mention it in the submission. |
