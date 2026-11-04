# 🥖 Crumbs

**Your photos already remember where you ate. Crumbs helps you find it, without your life leaving your house.**

Most of us have tens of thousands of photos on our phones, a lot of them of food. But even for the most memorable meals, the photo app makes it nearly impossible to find the specifics: the name of the place, what you ordered, when you were there. You want them when a friend asks for a recommendation, or when you're about to go back.

An AI could answer that, but only if you upload every photo and your whole location history to someone else's service. Crumbs does it with local AI instead. It turns the photos and location history you already have into a searchable record of where you went and what you ate, and every model runs on hardware you own.

Built for the [Meta Global AI Developer Hackathon](HACKATHON.md) (Oct 27 – Nov 4, 2026). Food comes first; hotel stays and whole-trip stories are next.

## What you can ask

> "What was the name of the eel place I had lunch at, the day I went to that garden in Kyoto?"

Crumbs' agent (Muse Glimmer, running locally) works through it step by step:
1. It finds the garden in the text of your photos.
2. It reads that day as a timeline of meals and stops.
3. It picks the lunch with the eel.
4. It takes a closer look at the sign and chopstick sleeve in those photos to read the restaurant's name.

The answer comes back with the photos it used as evidence.

Simpler questions work too: "where did I have soup dumplings in Taipei?", "what did I eat in Kyoto?", "have I been to Paris?". The last one gets an honest "no record" rather than a guess.

## How it works

```
photos ─► import (EXIF, HEIC→JPEG) ─► visits & trips ─┐
location history (GeoJSON) ─► stays ──────────────────┤
                                                       ├─► evidence store (SQLite) ─► Ask agent ─► PWA / API / Muse
Muse Glimmer: classify every photo, read menus/signs ─┤        ▲
DINOv3: embeddings, near-duplicates ──────────────────┤        └─ your answers to review questions
OpenStreetMap places (cached) ─► place candidates ────┘
```

- **Evidence, not guesses.** Every record keeps its provenance: *observed* (EXIF, GPS), *inferred* (a model read it), *lookup* (map data) or *confirmed* (you said so). Crumbs never names a restaurant from what the food looks like. A name comes from text in your photos, from GPS plus the map, or from you, and the answer says which.
- **Unknown stays unknown.** When the evidence is thin, Crumbs asks you ("Was this X?"). Your answer is stored next to the model's guess, never over it.
- **Grounded agent.** The Ask agent plans lookups over your index with tool calls. Answers cite the visits and photos the tools returned, and any citation no tool returned is removed.

## Models: open Meta models on my own hardware

| Model | Role | Parameters | Size (GB) | Precision | License |
|---|---|---|---|---|---|
| **Muse Glimmer 30B** | Classifies photos, reads menus & signs, plans Ask lookups | 30B | 19.8 | Q4_K_M GGUF (llama.cpp) | Apache 2.0 |
| **DINOv3 ViT-L/16** | Photo embeddings: near-duplicates, similarity | 303M | 1.21 | FP32 | DINOv3 License |
| SAM 3.1 *(tested)* | Masks for signs, menus, receipts, dishes | 848M | 1.68 | BF16 | SAM License |
| PE-Core L14 / G14 *(tested)* | Zero-shot photo labels | 0.32B / 1.88B vision | 2.6 / 9.1 | FP32 | Apache 2.0 |

Measured on my own photos and hardware: an AMD Strix Halo box with 128 GB of unified memory, plus a 4× RTX PRO 6000 box for burst runs.

- **Glimmer accuracy:** food F1 of **0.976** on 61 hand-verified food photos (Q4_K_M on Strix Halo).
- **Throughput:** classifying all 9,669 photos took about 12 minutes on the PRO 6000 box. On Strix Halo it runs at 19.4 s per photo.
- **DINOv3:** about 50 ms per photo.
- **Glimmer as a decision model (side quest):** restricted reads with [AnyJev](https://github.com/nokia-applied-research/AnyJev), no training, scored 76.6% on JevBench and a Decision Index 0.3 skill score of 32.60. These are not leaderboard submissions.

Full numbers, engines and caveats are in [MODELS.md](MODELS.md).

## Privacy: where the line is

- **Stays on your box:** photos, EXIF/GPS, location history, the database, and all model inference. The map uses local PMTiles, and the map view makes zero external requests.
- **You choose what crosses:** the optional [Muse bridge](docs/muse/SETUP.md) lets a Muse agent ask Crumbs questions over your private tailnet, using a read-only token capped at a redacted privacy tier. Only the answers to those questions leave the box; the archive never does.
- **One network lookup today:** `places-fetch` asks OpenStreetMap's Overpass service for restaurants around your food visits and caches the results locally. That reveals the areas queried, but no photos or history. An offline map-data importer is planned.
- **During development:** one comparison run sent sample photos to a hosted model API, by explicit decision, and bulk passes ran on our own PRO 6000 box.

## Run it

Requires Python 3.11+, exiftool, ImageMagick, and Node.js for the PWA. Glimmer is served by `llama-server --jinja` at `GLIMMER_URL` (default `http://127.0.0.1:18080`).

```bash
pip install -e .                       # add .[models] on the box that runs DINOv3
crumbs init-db
crumbs import-photos ~/Pictures/export     # EXIF, timestamps, 1024 px analysis copies
crumbs import-locations ~/wanderings.json  # optional location history (GeoJSON)
crumbs group && crumbs stays && crumbs embed
crumbs classify && crumbs extract          # Muse Glimmer passes
crumbs places-fetch && crumbs reconcile    # place candidates (OSM lookup) + review questions
crumbs ask --agent "where did I have soup dumplings in Taipei?"

crumbs serve                               # local API on 127.0.0.1:8770
cd spike/map-globe && npm install && sh tools/fetch-tiles.sh && npm run dev   # PWA on :5173
```

Your data lives in the git-ignored `data/` directory. `crumbs --help` lists every stage.

## Docs

| Doc | What's in it |
|---|---|
| [MODELS.md](MODELS.md) | Every model: size, precision, engine, memory, measured speed and accuracy |
| [PLAN.md](PLAN.md) · [IMPLEMENTATION.md](IMPLEMENTATION.md) | Product plan and the build checklist with status notes |
| [DISCOVERY.md](DISCOVERY.md) | Model and data research behind each choice |
| [demo/DEMO.md](demo/DEMO.md) | The demo's measured numbers and pipeline |
| [docs/muse/](docs/muse/) | Connecting a Muse agent: skill doc and setup |
| [spike/map-globe/README.md](spike/map-globe/README.md) | The globe/map PWA and fully local tiles |
| [worklog/](worklog/) | Immutable per-unit records of what was built, measured, and decided |
| [HACKATHON.md](HACKATHON.md) | The hackathon participant guide: rules, judging, deadlines |

## How it was built

Everything here was built during the hackathon's building period (Oct 27 – Nov 4, 2026). The worklog records each unit with its validation.

Most of the implementation was done with Meta's **Muse Wonder Full (max)** until its credits ran out. Additional implementation models were **Claude Opus 5.5**, plus **GPT-6.1 Sol** and **DeepSeek V4.1 Flash 1017** running in our [Jouzu](https://jouzu.dev) harness.

## Not built yet

Voice questions, background organising as new photos arrive, a taste profile, and hotel and trip stories. These are next, and nothing in the demo shows them as working.
