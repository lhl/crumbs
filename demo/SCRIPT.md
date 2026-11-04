# Crumbs — 3-Minute Video Script (draft v2, for the lead's voice pass)

Shooting script for the required 3-minute demo video. The lead records the voiceover; no synthetic narration. The narration is drafted in plain first person to be **rewritten into your own words**. Read it aloud once, then cross out anything you wouldn't say. [DEMO.md](DEMO.md) holds the measured numbers; [MODELS.md](MODELS.md) the model inventory.

**Shape.** Three acts: a personal hook, why it has to be local, and the Meta models that make local possible. Then a tight live demo and close. Most videos in this event demo features first. Ours argues a position first, then proves it on screen.

**Placeholders.** `<DISH>`, `<CITY>`, `<PLACE>`, `<NEVER_CITY>` and similar stand for real queries chosen at rehearsal. The repo is public, so the concrete values stay in local rehearsal notes.

**Pace.** Narration below is about 420 words: about 2:50 at a relaxed conversational pace, so cut about 10% after your read-through. Every shot names the built feature behind it ("Built" column). Never add a shot of something that isn't built.

## Hook options (pick one for 0:00–0:20)

| | Line | Footage |
|---|---|---|
| A (recommended) | "I have almost ten thousand photos from the last seven years. I can show you the best meal of my life. I can't tell you where it was. And I am not uploading my entire location history to someone's AI to find out." | Phone camera roll scroll, freeze on a dish photo. Hard cut to black on "not uploading". |
| B | "Your photo library and your location history together know where you sleep, who you eat with, and when you're not home. That's exactly the data every AI memory app wants you to upload. I built one that doesn't." | Slow pan over a location-history heatmap, then it blurs out. |
| C | "Every trip leaves crumbs: photos, receipts, a blue dot on a map. I wanted to follow them back, without handing them to anyone." | Breadcrumb trail drawing itself on the globe (▶ Play trail). |

## Script

| # | Time | Footage / cuts | Narration (draft; rewrite in your words) | Built |
|---|---|---|---|---|
| 1 | 0:00–0:20 | **Hook.** Per the option chosen above. | *(hook line)* | — |
| 2 | 0:20–0:35 | **What it is.** Title "Crumbs" over the offline globe; zoom into one trip; ▶ Play trail draws the route. | "So I built Crumbs. It turns the photos and location history you already have into a searchable memory of where you went and what you ate, without writing a journal. This is my real history: 590 visits, rebuilt automatically." | PWA globe + trail (spike/map-globe); import, group |
| 3 | 0:35–1:10 | **Why local.** (a) Location-history heatmap over a city, then blur/redact it. (b) Real footage of the Strix Halo box on the desk. (c) Screen: DevTools network panel with external requests blocked while the map renders: 0 external requests. (d) Terminal: `llama-server` serving Glimmer on the box. | "Here's the part I care about most. A photo library plus location history is the most complete record of your life there is: where you live, who you're with, when you're away. Most AI memory tools want all of it in their cloud, and to be useful they have to run all the time, in the background. An always-on cloud copy of my life is a liability I don't want. So every model in Crumbs runs on hardware I own. This box on my desk has 128 GB of unified memory and runs a 30-billion-parameter vision model. Even the map tiles are local files." | Local PMTiles (0 external requests, verified); Glimmer on llama.cpp (zbook) |
| 4 | 1:10–1:45 | **The Meta model stack.** One card per model, building up a wall. Each card shows the model, its job, and one measured number, over B-roll of its output: Glimmer's extraction JSON from a menu, DINOv3 near-duplicate pairs, SAM 3.1 masks on a menu/sign, PE-Core zero-shot labels. End on the full wall with a "measured on our hardware" tag. | "That's only possible now because of open models, and almost everything here is from Meta. Muse Glimmer is the workhorse: it sorted all 9,669 photos and read the menus, signs and receipts in over 3,000 of them. On the food photos I checked by hand, it scored 0.976 F1. DINOv3 embeds every photo in about 50 milliseconds, for duplicates and similarity. We also tested SAM 3.1 for finding signs and menus, and Perception Encoder as a fast zero-shot classifier. We measured all of them on the same photos, and that's how we picked what each one does." | classify, extract, embed; SAM/PE measured (MODELS.md, DEMO.md) |
| 5 | 1:45–2:15 | **Ask: Glimmer as an agent.** Ask panel with the "Muse Glimmer agent" toggle. Type *"where did I have `<DISH>` in `<CITY>`?"*, show "planning lookups…" for 1 s, then **jump cut** past the ~20 s wait. Answer appears; expand the trace (`search_dishes(…) → 1 found`); hover the photos, the dish chips (menu / seen) and the provenance badge. | "And then I can just ask. Glimmer works as an agent here: it decides which lookups to run over my index and writes a short answer. But the evidence never comes from the model. The cards come only from what the tools returned, and if Glimmer cites a visit that no tool returned, we strip it out." | AGT-02 v1 agent (`/v1/ask?agent=1`), Ask cards, photo previews |
| 6 | 2:15–2:30 | **Evidence beats guessing.** Ask *"what was that `<DISH_2>` place in `<CITY_2>`?"* (jump cut). Zoom on the card: "`<GPS_GUESS>`? · nearby (GPS)", while the answer says the photo text reads `<REAL_NAME>`. | "This one's my favourite. GPS says I was next to `<GPS_GUESS>`. But Glimmer read `<REAL_NAME>` in my own photos, and it shows me both, labelled for what they are. It never names a restaurant just from what the food looks like." | Place provenance, photo-text names |
| 7 | 2:30–2:42 | **Correct it / honest unknown.** Click **Yes** on "Was this `<PLACE>`?" and the card turns to "✓ you confirmed". Quick cut: *"have I been to `<NEVER_CITY>`?"* → "no record." | "When it's not sure, it asks me, and my answer is stored next to the model's guess, not over it. And when there's nothing there, it just says so." | Review answers (`POST /v1/review/<id>`); designed unknowns |
| 8 | 2:42–3:00 | **Close.** Back to the globe, slowly zooming out. End card: "Crumbs: food first. Hotels and whole trips next." Repo URL. | "Food is first; hotel stays and full trip stories are next. Your photos already remember where you've been. Crumbs helps you find it, and it never has to leave your house." | — |

## Before recording

- **Footage consent.** Use only the owner-consented subset (or the synthetic set). Check every visible thumbnail, the heatmap and every map zoom for faces or bystanders, licence plates, and anything near home or work. The heatmap in shot 3 must be blurred or shown at a scale that reveals no address. Raw coordinates must never be on screen.
- **Shot 3 network proof.** Record DevTools with non-localhost requests blocked, as in the spike's verification. This proves the *map* is local. Don't frame it as proof that the whole pipeline is offline (see guardrails).
- **Shot 4 B-roll** is produced from local outputs: an extraction JSON for a consented menu photo, a DINOv3 `crumbs similar` pair, a SAM 3.1 mask overlay, and a PE-Core label. Check each for personal details before it goes in the edit.
- **Glimmer tunnel and services.** Run `ssh -N -L 18080:127.0.0.1:18080 zbook`, then `crumbs serve` and `npm run dev` in `spike/map-globe`. Ask one throwaway warm-up question first.
- **Rehearse each query 2–3 times** and keep clean takes (the agent runs at temperature 0.2, so wording varies). Never cut together a claim the take didn't show.
- **Review state.** Leave one open question on the shot-7 visit and answer it only on camera.
- **Window.** 1440×900 or larger; hide bookmarks and other tabs.

## Claims guardrails (check the narration against these)

- **"Every model in Crumbs runs on hardware I own"** is true for the product: the Strix Halo boxes, plus our own 4× RTX PRO 6000 box, which processed the full backlog faster with the same models. If you mention speed, say that. Do not say "no photo ever left my machines": during development a hosted DE-2.1 comparison sent photos to an external API, and place lookups queried OpenStreetMap's Overpass service (cached locally afterwards).
- **The 0-external-requests test** covers the map and tiles only.
- **"128 GB unified memory"** is the hardware spec; Linux reports about 125 GB usable. Say "128 GB box", not "125 GB of VRAM".
- **The 0.976 F1** comes from the zbook Q4_K_M run on the 61 hand-verified food photos in the 440-photo sample. Don't generalise it to every category or to the full corpus.
- **SAM 3.1 and Perception Encoder** were measured but are *not* in the shipped pipeline. Say "tested", as the draft does. The no-training Glimmer decision readout (Decision Index 32.60) is a research result, not a product feature. Leave it out or call it an experiment.
- **"Almost ten thousand photos from the last seven years"**: the store has 9,669 photos with visits from 2019 to 2026. Check against your own sense of the library before saying it.
- **Not built:** voice, background organising, the taste profile, hotel/trip stories. They may appear only as "next".
