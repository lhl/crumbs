# Spike: web globe + flat tile map with photos and a time trail

Status: **working spike, exercised 2026-10-27** (headless Chromium, screenshots + interaction script). This answers PLAN.md's R6 (map/globe library + free tiles) at spike level. It is not product code; it proves the rendering approach and records what the real PWA (IMPLEMENTATION PWA-05/PWA-06) should adopt.

## Run it

```bash
cd spike/map-globe
npm install
sh tools/fetch-tiles.sh   # one-time: downloads the fully-local tile data (below) into git-ignored dirs
npm run dev      # http://127.0.0.1:5173
npm run build    # production bundle → dist/ (verified; public/ tile data is copied into dist/)
npm run preview  # serves the built version on :4173
```

## Fully-local mode (Protomaps / PMTiles) — the default basemap

`tools/fetch-tiles.sh` prepares everything the **Protomaps PMTiles (fully local)** style needs, all served same-origin at runtime:

| Piece | Source | Local size (measured) |
|---|---|---|
| `public/tiles/protomaps-demo.pmtiles` | `pmtiles extract` (pinned go-pmtiles v1.28.2, downloaded by the script if absent) against the Protomaps daily planet build (`build.protomaps.com/<YYYYMMDD>.pmtiles`, override with `PROTOMAPS_BUILD`), `--region=tools/demo-regions.geojson --maxzoom=15` | **40 MB** for the Kyoto + Taipei + Lisbon demo regions together; fetch took ~16 s via HTTP range requests (the planet file itself is ~120 GB and is never downloaded) |
| `public/tiles/protomaps-globe.pmtiles` | same build, `--maxzoom=5`, no region (whole planet, low zoom only) | **15 MB**; measured alternatives: z≤6 = 45 MB, z≤7 = 190 MB — each added zoom roughly triples it, so z5 is the lightweight-globe sweet spot |
| `public/fonts/` | glyph PBFs from `protomaps/basemaps-assets` (Noto Sans stacks the style references) | 15 MB |
| `public/sprites/v4/` | sprite sheets for the style's icons | 180 KB |

All of it is git-ignored (see `.gitignore`); nothing tile/font/sprite is committed. The style itself is generated in code with `@protomaps/basemaps` (`layers('protomaps', namedFlavor('light'), {lang:'en'})`) and tiles are read via the `pmtiles` JS protocol's HTTP range requests against the local archives — so zooming/panning reads byte ranges from local files, with no tile server at all. The style carries **two sources with a zoom handoff**: the globe backdrop's layer set (countries, oceans, capitals — visible z<7) under the regional detail set (z≥6; deliberate overlap, no gap). Outside the three regional extracts the street-level basemap is intentionally absent — that is what "offline for cached regions" looks like — while the globe always shows the full Earth. The header shows `local tiles ✓` when the archives are present (or tells you to run the fetch script when they aren't).

### Streaming the planet archive directly (online option, also in the switcher)

Because PMTiles is just byte ranges over HTTP, the browser can also skip downloads entirely: the **"Protomaps planet (streamed)"** style points the same `pmtiles://` protocol at the remote planet archive and only the tiles actually viewed are transferred (initial globe view measured: 8 range requests). Two practical findings: `build.protomaps.com` sends **no CORS headers**, so browsers cannot stream from it — the Source Cooperative mirror (`data.source.coop/protomaps/openstreetmap/v4.pmtiles`, an older build) sends `Access-Control-Allow-Origin: *` and works; and streaming is **not** the privacy-clean mode (the host sees which tiles you view), so it stays an opt-in comparison, never the default.

Verified 2026-10-27 with **all non-localhost requests blocked** in headless Chromium: 0 external requests attempted, 35 same-origin range requests against the archive, Kyoto rendered with streets/labels/POIs, trip playback and trails working, ~41 fps in the dense Kyoto view under software GL (61 fps on the globe). This is the pattern PWA-05 should reuse for the product; regional extracts for a user's own trips can be produced the same way at import time or pre-downloaded per region.

## What it demonstrates

- **One MapLibre GL JS map, two projections.** Globe (🌐) and flat Mercator (🗺️) toggle via MapLibre v5's native `map.setProjection({type:'globe'|'mercator'})` — same vector sources and layers work in both; the globe adds atmosphere via `setSky`. No separate 3D engine (Cesium/deck.gl) is needed for this use case.
- **Photos at two scales.** All photos live in one clustered GeoJSON source (`cluster: true`): cluster bubbles with counts zoom apart into per-trip colored points. When a single trip is selected (≤300 photos), each photo additionally gets a **DOM thumbnail marker** (circular photo pins) — DOM markers are deliberately capped, because thousands of DOM nodes destroy frame rate; clustering carries the scale.
- **Time-based trail.** Each trip has a full dashed route line; selecting/playing a photo draws a **progress trail** (solid line up to that photo, with an interpolated head segment). The bottom scrubber and ▶ Play step through photos in time order, updating the photo card, list selection, marker highlight, and trail together.
- **Stress test.** "+5,000 stress photos" regenerates the dataset with 5,000 extra points around the trip anchors to exercise clustering.
- **Synthetic data only.** Three invented trips (Kyoto food, Taipei coffee, Lisbon sightseeing) with generated placeholder "photos" (inline SVG). No real photos, names, or location history.

## Measured results (this machine, headless Chromium + SwiftShader software GL)

| Check | Result |
|---|---|
| Globe initial render (126 photos, OpenFreeMap Liberty) | renders, clustered counts visible, `getProjection()` = `globe` |
| FPS, globe / flat / trip view | ~60 fps (capped by the test's frame loop; software GL — expect ≥ this on real GPUs) |
| Stress: 5,126 total photos (1,709 in the selected trip view), clusters on | ~60 fps in the same headless setup; DOM thumbs correctly suppressed above the 300 cap |
| Interaction flow (scripted) | projection toggle, trip select → fitBounds, play/pause stepping, photo card, stress add — all pass, no page errors |
| Production build | `vite build` OK; JS ≈ 1.07 MB (289 KB gzip), CSS ≈ 72 KB (10.6 KB gzip) — almost all MapLibre; code-splitting the map chunk is a product-side TODO, not a spike blocker |

Known cosmetic warnings in console: a few MapLibre "Expected value to be of type number, but found null" style warnings during projection/style switches (non-fatal; track down before productizing), and glyph fallback notices if a style's font stack doesn't include the layer's `text-font` — the spike's cluster-count layer pins `Noto Sans Bold`, which the OpenFreeMap styles provide.

## Free map tiles — where to get them (researched 2026-10-27)

All OSM-derived options require visible **© OpenStreetMap contributors** attribution (plus provider credit where stated). MapLibre's attribution control handles this if the style carries it.

| Source | What | Cost / key | Terms that matter | Verdict for Crumbs |
|---|---|---|---|---|
| **OpenFreeMap** (`tiles.openfreemap.org/styles/{liberty,bright,positron}`) | Hosted **vector** tiles + ready styles, OpenMapTiles schema | Free, **no API key** | Attribution "OpenFreeMap © OpenMapTiles, Data from OpenStreetMap". Offline downloads allowed ≤3,000 tiles / 50 MB per download, ≤4 parallel requests, unique User-Agent; full self-hosting offered (planet Btrfs images). Donation-funded — availability is best-effort, no SLA. | **Spike default and product candidate.** No key, vector styling, generous offline allowance that fits our cached-demo-regions plan (PLAN §7.4). Risk: single small provider; mitigate with self-host fallback. |
| **CARTO Basemaps** (`basemaps.cartocdn.com/gl/<style>-gl-style/style.json`) | Hosted **vector** styles (Voyager, Positron, Dark Matter) on a global CDN; raster PNG tiles also exist | Free tier **with API key** (free, no account): non-commercial ≤5M tile requests/mo, commercial ≤1M/mo, then paid plans | Attribution (CARTO + OSM) must stay visible; key is per-project, not shareable. Since Sep 2026 the *raster* endpoints refuse keyless requests; vector styles still load without a key today, but CARTO recommends adding one and may require it later. | **Strong fallback / A/B style.** Better SLA posture than OpenFreeMap, but key management + commercial cap make it second choice for a local-first product. Works in the spike's style switcher. |
| **OSM standard tiles** (`tile.openstreetmap.org`) | Hosted **raster** tiles from the OpenStreetMap Foundation | Free, no key | The Tile Usage Policy is explicit that OSM's donated servers are not a general app backend: no heavy use, no bulk scraping, valid HTTP Referer/User-Agent required, attribution required. | **Demo/prototype fallback only** (included in the switcher as `osm-raster`). Never a product default; never bulk-download. |
| **Protomaps / PMTiles (self-host)** | Single-file tile archives you generate or download, served statically or from object storage; basemap schema compatible with CARTO's vector layers | Free software; you pay only your own hosting | You control availability and can ship **fully offline regional extracts**; planet-scale extracts are large but regional (city/country) ones are practical. | **The privacy-clean endgame** for the product: download regional PMTiles once, serve locally, zero per-view tile traffic — resolves PLAN §7.4 outright. Evaluate in PWA-05; the spike didn't need it to prove rendering. |
| **OpenMapTiles self-host / OpenFreeMap self-host** | Your own tile server from OSM data | Free software; your infra | Full control, update pipeline is your problem. | Heavier than PMTiles for a single-user local product; keep as the fallback if PMTiles licensing/tooling disappoints. |

Not free (for contrast): Mapbox and MapTiler's hosted tiers are paid/keyed beyond small free allowances — no reason to accept a key + meter for a local-first app when the options above exist.

**Privacy note (PLAN §7.4 in practice):** hosted tiles (OpenFreeMap/CARTO/OSM) see the viewer's IP and the region being viewed. For the demo, pre-cache the demo regions within OpenFreeMap's offline allowance or ship PMTiles extracts; for the product default, PMTiles-regional or disclosure in Settings remains the plan.

## Recommendation for the product (closes R6 at spike level)

1. **MapLibre GL JS (v5.x) for both globe and flat map**, one map component, `setProjection` toggle; globe at low zoom / hero moments, Mercator for detail work. No second 3D library.
2. **Clustered GeoJSON for all photos; DOM thumbnail markers only for the current trip/visit (≤~300).** This split is the performance story; do not render a library as DOM markers.
3. **Trails as GeoJSON lines + a progress line** (this spike's partial-trail interpolation); for very long trips, precompute per-visit segments instead of per-photo lines.
4. **Tiles: OpenFreeMap Liberty default, CARTO Voyager alternate style, PMTiles regional extracts for offline/demo and as the privacy-clean product default**; attribution always visible.
5. **Bundle:** lazy-load the map chunk (MapLibre is ~290 KB gzip) so the PWA shell stays light; the map is a route-level feature, not app-shell weight.

## Files

- `src/main.js` — map setup, projections, clustering, trails, playback, FPS meter; `window.__spikeMap` is exposed for debugging.
- `src/data.js` — deterministic synthetic dataset generator (+ stress mode).
- `src/style.css`, `index.html` — minimal UI: projection/style/trip controls, photo panel, timeline scrubber.
