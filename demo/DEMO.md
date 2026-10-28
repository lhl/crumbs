# Crumbs — Demo Script (working draft)

Three minutes, Must-scope only, every beat backed by a working feature. Concrete record IDs live in the local demo manifest (`crumbs demo` → `data/demo/manifest.json`, ignored — it names the owner's real visits). This file stays generic so it can live in the public repo.

## Beats

1. **The problem (0:00–0:25).** Scrolling a camera roll, failing to name a restaurant from a food photo. Cut to the offline globe: clusters of real trips, rebuilt locally. *Feature: PWA-06 globe + real corpus export.*
2. **The pipeline, visibly local (0:25–1:10).** Import → classify → group on screen with the model inventory beside it (MODELS.md): photos become categories, evidence, visits — no API calls (the blocked-network globe test is the proof). One food visit resolves only by combining menu text + GPS candidates. *Features: IMP-01, EMB, REC-01/02/07, EXT.*
3. **Ask (1:10–1:50).** The anchor query: "what was the dashi restaurant near <anchor area> in <trip month>?" — answered from visits and ranked candidates with evidence. Then "what did I have at <candidate place>?" for dishes. *Feature: AGT v1 (CLI + `/v1/ask`).*
4. **Correction + honest unknown (1:50–2:25).** One review-queue question answered (candidate confirmed/rejected, resolution updates); one question about a place never visited → designed unknown. *Features: REC-02 queue, labels.*
5. **Close on measurement (2:25–3:00).** The zbook rate table (MODELS.md) and the privacy statement: every model on the box, tiles offline, location history never leaves. *Features: MODELS.md, bridge tiers.*

## Sufficiency verdict (from `crumbs demo`, current store)

- The **pipeline demo is fully buildable from the current sample** (extraction hero, signage-confirmed candidate, review question, anchor visit all exist as real records).
- **Not public-video ready**: no user labels (no accuracy numbers yet), trips over-merge at sample sparsity (feature visits, not trip narratives), and any public footage needs the owner's consented subset or the synthetic set.
- A fresher iPhone/iCloud sync is **not required** for the demo; it would mainly buy a cleaner multi-day trip storyline.
