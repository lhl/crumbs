# Crumbs

Crumbs turns the photos and location history you already have into a searchable database of where you went and what you ate. Every model runs on your own hardware.

Crumbs was built to solve a specific problem - with very large photo libraries (thousands, tens of thousands of food photos), the default photo search is basically useless for search and retrieval, eg trying to give a friend a reocmmendation, remembering where you went, or what you ate/ordered last time you were there. At the ame time, I wanted to have advanced AI-driven functionality *without* having to upload all of my photos and location to a third party, hence why Crumbs is backed by local AI for its functionality.

Crumbs was built for the [Meta Global AI Developer Hackathon](HACKATHON.md) (Oct 27 – Nov 4, 2026). It covers food first; hotel stays and trip stories are next.

## What you can ask

> "What was the name of the eel place I had lunch at, the day I went to that garden in Kyoto?"

The Ask agent (Muse Glimmer, running locally) answers in steps:
1. It finds the garden in the text of your photos.
2. It reads that day as a timeline of meals and stops.
3. It picks the lunch with the eel.
4. It takes a closer look at the sign and chopstick sleeve in those photos to read the restaurant's name.

The answer comes back with the photos it used as evidence.

It also answers single-lookup questions such as "where did I have soup dumplings in Taipei?" and "what did I eat in Kyoto?". For "have I been to Paris?", when there's no record, it says so instead of guessing.

## How it works

```
photos ─► import (EXIF, HEIC→JPEG) ─► visits & trips ─┐
location history (GeoJSON) ─► stays ──────────────────┤
                                                       ├─► evidence store (SQLite) ─► Ask agent ─► PWA / API / Muse
Muse Glimmer: classify every photo, read menus/signs ─┤        ▲
DINOv3: embeddings, near-duplicates ──────────────────┤        └─ your answers to review questions
OpenStreetMap places (cached) ─► place candidates ────┘
```

- **Provenance:** records are marked *observed* (EXIF, GPS), *inferred* (a model read it), *lookup* (map data), or *confirmed* (you said so). 
- **Review questions:** when the evidence is thin, Crumbs asks you ("Was this X?"). Your answer is stored next to the model's guess.
- **Citations:** the Ask agent plans lookups with tool calls and cites the visits and photos the tools returned. Any citation no tool returned is removed.

### Location data

Crumbs reads GPS from each photo's EXIF data. It uses OpenStreetMap for the place registry and for local vector basemaps (PMTiles), and it adds location history from GeoJSON exports (I have years of it from Wanderings). The labeling UI reverse-geocodes offline with GeoNames data. Each source is recorded as its own import, so check-ins, trip itineraries, or other sources can be added the same way.

## Models

| Model | Role | Parameters | Size (GB) | Precision | License |
|---|---|---|---|---|---|
| **Muse Glimmer 30B** | Classifies photos, reads menus & signs, plans Ask lookups | 30B | 19.8 | Q4_K_M GGUF (llama.cpp) | Apache 2.0 |
| **DINOv3 ViT-L/16** | Photo embeddings: near-duplicates, similarity | 303M | 1.21 | FP32 | DINOv3 License |
| SAM 3.1 *(tested)* | Masks for signs, menus, receipts, dishes | 848M | 1.68 | BF16 | SAM License |
| PE-Core L14 / G14 *(tested)* | Zero-shot photo labels | 0.32B / 1.88B vision | 2.6 / 9.1 | FP32 | Apache 2.0 |

Everything runs on an AMD Strix Halo box (128 GB unified memory); a 4× RTX PRO 6000 box handled burst runs. Results, measured on my photos:

- **Glimmer accuracy:** food F1 of 0.976 on 61 hand-verified food photos (Q4_K_M on Strix Halo).
- **Throughput:** classifying all 9,669 photos took about 12 minutes on the PRO 6000 box. On Strix Halo it runs at 19.4 s per photo.
- **DINOv3:** about 50 ms per photo.
- **Glimmer as a decision model (side quest):** using [AnyJev](https://github.com/nokia-applied-research/AnyJev) restricted reads with no training, Glimmer scored 76.6% on JevBench and 32.60 on the Decision Index 0.3 skill index. These are not leaderboard submissions.

Full numbers, engines and caveats are in [MODELS.md](MODELS.md).

## Privacy

- **Stays on your box:** photos, EXIF/GPS, location history, the database, and all model inference. The map uses local PMTiles, and the map view makes zero external requests.
- **What you choose to share:** the optional [Muse bridge](docs/muse/SETUP.md) lets a Muse agent ask Crumbs questions over your private tailnet, using a read-only token capped at a redacted privacy tier. The full archive stays on the box; only the answers to those questions go out.
- **Network lookup:** `places-fetch` asks OpenStreetMap's Overpass service for restaurants around your food visits and caches the results locally. That reveals the areas queried, but no photos or history. An offline map-data importer is planned.

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

Most of the implementation was done with Meta's **Muse Wonder Full (max)** until its credits ran out. Additional implementation models were **Claude Opus 5.5**, plus **GPT-6.1 Sol** and **DeepSeek V4.1 Flash 1017** running in our [Jouzu](https://jouzu.dev) coding harness.
