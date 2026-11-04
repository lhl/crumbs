# Crumbs — 3-Minute Video Script (draft v2, for the lead's voice pass)

Shooting script for the required 3-minute demo video:
- The lead records the voiceover; no synthetic narration. 
- The narration is drafted in plain first person in my own words.
- [DEMO.md](DEMO.md) holds the measured numbers; [MODELS.md](MODELS.md) the model inventory.

## Crumbs

0:00-0:30

[Scrolling through food photos]

I have tens of thousands of photos on my iPhone chronicling my life, including way too many food photos. But even for my most memorable meals, the default photo app makes it impossible for me to find the specifics, whether its giving a friend a recommendation, or remembering what I ordered the last time I was someplace. 

Like most people, I'm not exactly chuffed about uploading all of my photos and location history to AI services, so I built a app to solve this using local AI.

0:30-0:55

[Globe, Heat Map (wanderings style)] rotating. [Photos pop up]
[Crumbs]

It's called Crumbs.

And it turns the photos and location history you already have into a searchable database of where you went and what you ate.

*Now* you can ask it complex questions like "what was the name of the eel place I had lunch at in Kyoto, the day I went to Murin-an garden?" and off it goes.

[Type exactly: `what was the name of the eel place I had lunch at in Kyoto, the day I went to Murin-an garden?` — Glimmer: find_photos(Murinan) → day_timeline(that day) → answer, ~30 s]

0:55-1:23

[Strix Halo Box; Graphs]

This all runs locally on my AMD Strix Halo workstation.

Muse Glimmer is the agent that turns natural language into lookups.

The photos were all processed with open Meta models:
- DINOv3 for near-duplicates
- Glimmer's VLM for reading menus, signs, and categorization
- I also tested SAM 3.1 for masking and object id and PE-Core for zero-shot labels. 

Thanks Meta for all the open models.

1:23-1:48

[Accuracy Chart and Speed Table, split screen]

On my hand-checked food photos, Glimmer scored a 0.976 F1, which is fantastic.

And here are more result and speed details for the ML-inclined.  If you have 20 gigs of memory you can run Glimmer, and the rest of the models can be run on just about anything.

One fun sidequest, I also tested turning Glimmer into a Decision Model with AnyJev, which is actually pretty viable.

1:48-2:15
[Geo Architecture]

Location data is the other part. I extract the EXIF GPS data and use OpenStreetMapss for place registry and vector basemaps and also GeoNames for reverse-geocoding. 

I have years of GeoJSON as well that I use to augment my location history. 

Crumbs is designed so more metadata can be added from different sources, from checkins, trip itineraries, health activity or anything else you have.


2:15-3:00

[Show results]

And here we go: Crumbs found my Murin-an photos, went through the rest of that day, and read the sign in my lunch photos: 
Kyo Unawa Jingumichi. It was a solid hitsumabushi, overall good cospa.


You might have noticed that I asked my question through Buddy, my Muse agent. That's actually on purpose since I wanted to show that *you* can decide what lines you want to draw on your data - my full archive stays on my box, but I don't care if individual query results go out.

So that's Crumbs. your most personal memories, safely searchable. 

Food is first, hotels and trips are next.





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
