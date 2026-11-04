# Crumbs — 3-Minute Video Script (draft for review)

Shooting script for the required 3-minute demo video. [DEMO.md](DEMO.md) holds the beat rationale and the measured numbers. Every on-screen feature below is built and committed (see the "Built" column). Do not add a shot of anything that is not.

**Placeholders.** `<DISH>`, `<CITY>`, `<PLACE>`, `<NEVER_CITY>` and similar stand for real queries chosen at rehearsal. This repo is public, so the concrete values (which name the owner's real visits) live only in the local rehearsal notes, not here.

**Pace.** About 150 words per minute. The narration below is about 350 words (roughly 2:20 spoken), which leaves room for the jump cuts and pauses. Times are targets; trim narration before trimming the demo shots.

## Script

| # | Time | Footage / cuts | Narration | Built |
|---|---|---|---|---|
| 1 | 0:00–0:15 | **Cold open.** Phone screen recording: thumb-scrolling a camera roll of food photos. Slow down and freeze on one dish photo with no name or caption. | "Our phones are full of meals we loved and can't name. I know I had the best dumplings of my life somewhere in `<CITY>`. The photo is right here. The restaurant isn't." | — (phone footage) |
| 2 | 0:15–0:25 | **Title card.** "Crumbs: rediscover where you went, stayed, and ate." Subtitle: "Built on Muse Glimmer, self-hosted." | "Crumbs turns the photos and location history you already have into a searchable memory of where you ate, without writing a single journal entry." | — |
| 3 | 0:25–0:45 | **Globe.** PWA on the offline globe with clustered photo pins. Spin, then zoom into one trip; press **▶ Play trail** so the route draws itself. Hold briefly on the header stats. | "This is about ten thousand of my photos and my location history, rebuilt into 590 visits and 20 trips. The map tiles are local files, so even the map doesn't phone home." | PWA-06 globe + local PMTiles (spike/map-globe); IMP-01, group |
| 4 | 0:45–1:15 | **How it was built.** Split screen. Left: terminal running `crumbs classify` / `crumbs extract` progress. Right: one menu photo, then its extraction JSON (visible text, dish candidates, place-name candidates) typing in. End on a small model-role table overlay (Glimmer: classify, read, agent; DINOv3: embeddings). | "Meta's Muse Glimmer does the reading. It sorted all 9,669 photos into food, sightseeing, travel and personal, then read the menus, signs and receipts in over 3,000 of them: dish names, place names, prices. DINOv3 embeddings group near-duplicates. Every model in Crumbs runs on our own machines; the product sends no photos to a third-party API." | classify, extract, embed (MODELS.md) |
| 5 | 1:15–1:50 | **Ask, agent mode.** PWA Ask panel with the "Muse Glimmer agent" toggle visible. Type: *"where did I have `<DISH>` in `<CITY>`?"* Show "planning lookups…" for about 1 s, then **jump cut** past the ~20 s wait. The answer appears; expand the trace (`search_dishes(…) → 1 found`); hover the card's photos, dish chips and provenance badge. | "Now I just ask. Glimmer works as an agent: it decides which lookups to run over my local index, here a dish search scoped to the city, and writes a short answer. The cards don't come from the model. They come only from what the tools returned, and if Glimmer cites a visit no tool returned, we strip it. Each dish says whether it was read off a menu or just recognised on the plate." | AGT-02 v1 agent (`/v1/ask?agent=1`), Ask cards, photo previews |
| 6 | 1:50–2:10 | **Evidence beats guessing.** Ask *"what was that `<DISH_2>` place in `<CITY_2>`?"* (jump cut). Zoom on the card: the place shows "`<GPS_GUESS>`? · nearby (GPS)", while the answer says the photo text reads `<REAL_NAME>`. | "Here's why provenance matters. GPS says I was next to `<GPS_GUESS>`. But Glimmer read `<REAL_NAME>` in my own photos, and it tells me both, labelled for what they are. Crumbs never names a restaurant from what the food looks like." | Place provenance, photo-text names |
| 7 | 2:10–2:25 | **Correction.** On a card with "Was this `<PLACE>`?", click **Yes**. The card turns green: "✓ you confirmed". Ask *"what did I have at `<PLACE>`?"*; the confirmed visit comes back with its dishes. | "When it's unsure, it asks one question. I confirm, and that answer becomes part of my history, stored next to the model's guess rather than overwriting it." | Review answers (`POST /v1/review/<id>`) |
| 8 | 2:25–2:35 | **Honest unknown.** Ask *"have I been to `<NEVER_CITY>`?"* → "no record." | "And when there's nothing there, it says so. Unknown is an answer, not a failure." | Designed unknowns (parser + agent) |
| 9 | 2:35–3:00 | **Close on measurement.** Full-screen card with three numbers: food classification F1 **0.976** (hand-checked food photos); agent **8/8** questions answered with **0** unsupported citations; **9,669** photos processed on our own GPUs. Then end card: "Crumbs: food first. Hotels and whole trips next." Repo URL. | "We measured instead of guessing: Glimmer scored 0.976 F1 on the food photos we hand-checked, and in our live run the agent cited only visits its tools actually found. Food is first; hotel stays and whole-trip stories are next. Crumbs: rediscover where you went, stayed, and ate." | DEMO.md measured tables, agent worklog 20261104T104525 |

## Before recording

- **Footage consent.** Use only the owner-consented subset (or the synthetic set). Check every visible thumbnail, map zoom and card for faces or bystanders, licence plates, and anything near home or work. Blur in post if needed. Raw coordinates must never be on screen.
- **Glimmer tunnel.** Run `ssh -N -L 18080:127.0.0.1:18080 zbook`, then `crumbs serve` and `npm run dev` in `spike/map-globe`. Warm Glimmer with one throwaway question so the first take isn't cold.
- **Rehearse each query 2–3 times** and keep the takes where the answer is clean. The agent runs at temperature 0.2, so wording varies a little between runs; never cut together a claim the take didn't show.
- **Review state.** Leave one open question on the visit used in shot 7. Answer it only on camera.
- **Window size.** Record at 1440×900 or larger so the 380 px Ask panel and the map are both legible. Hide the bookmarks bar and other tabs.

## Claims guardrails (for the narration pass)

- "On our own machines" is accurate for the product path: our own APU boxes and our own dev GPU box. Do not say "on your phone" or "entirely on one laptop". During development, a hosted DE-2.1 comparison did send photos to an external API, and place lookups queried OpenStreetMap Overpass. So never say "no photo ever left our machines"; scope the claim to the product.
- The 0.976 F1 covers only the 61 hand-verified food photos from the 440-photo sample. Don't generalise it to all categories.
- "8/8, 0 unsupported citations" is one live run of 8 questions. It is not a golden-query accuracy number.
- SAM 3.1, PE-Core and DE-2.1 were evaluated but are not in the shipped pipeline. Leave them out of the narration, or say "evaluated".
- Voice, background organising, the taste profile and hotel/trip stories are **not built**. They may appear only as "next".
