import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Protocol } from 'pmtiles';
import { layers as protomapsLayers, namedFlavor } from '@protomaps/basemaps';
import { generatePhotos, photoThumb, TRIPS } from './data.js';

// Fully-local basemap (PWA-05): one PMTiles archive + local glyphs/sprites, all same-origin.
// Data is fetched by tools/fetch-tiles.sh into public/ (git-ignored); see README.
maplibregl.addProtocol('pmtiles', new Protocol().tile);
const LOCAL_STYLE = {
  version: 8,
  glyphs: `${location.origin}/fonts/{fontstack}/{range}.pbf`,
  sprite: `${location.origin}/sprites/v4/light`,
  sources: {
    protomaps: {
      type: 'vector',
      url: `pmtiles://${location.origin}/tiles/protomaps-demo.pmtiles`,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: protomapsLayers('protomaps', namedFlavor('light'), { lang: 'en' }),
};

const STYLES = {
  'protomaps-local': LOCAL_STYLE,
  'openfreemap-liberty': 'https://tiles.openfreemap.org/styles/liberty',
  'openfreemap-positron': 'https://tiles.openfreemap.org/styles/positron',
  'carto-voyager': 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
  // Raster fallback (OSM tile usage policy: fine for a low-volume spike/demo, NOT a product default).
  'osm-raster': {
    version: 8,
    sources: {
      osm: {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '© OpenStreetMap contributors',
      },
    },
    layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
  },
};

let photos = generatePhotos();
let activeTrip = 'all';
let currentIdx = 0; // index into the *visible, time-ordered* photo list
let playing = false;
let playTimer = null;
let thumbMarkers = [];

const $ = (id) => document.getElementById(id);

const map = new maplibregl.Map({
  container: 'map',
  style: STYLES['protomaps-local'],
  center: [124, 30],
  zoom: 2.2,
  attributionControl: { compact: true },
});
map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }));

function visiblePhotos() {
  return activeTrip === 'all' ? photos : photos.filter((p) => p.tripId === activeTrip);
}

function toGeoJSON(list) {
  return {
    type: 'FeatureCollection',
    features: list.map((p) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      properties: { id: p.id, tripId: p.tripId, title: p.title, category: p.category, time: p.time },
    })),
  };
}

function trailFor(tripId, upToTime = Infinity) {
  const pts = photos.filter((p) => p.tripId === tripId && p.time <= upToTime);
  return pts.map((p) => [p.lon, p.lat]);
}

// Partial trail: whole segments before the cutoff, plus an interpolated head segment.
function partialTrail(tripId, cutoffTime) {
  const pts = photos.filter((p) => p.tripId === tripId);
  const coords = [];
  for (let i = 0; i < pts.length; i++) {
    if (pts[i].time <= cutoffTime) { coords.push([pts[i].lon, pts[i].lat]); continue; }
    if (i > 0) {
      const a = pts[i - 1], b = pts[i];
      const f = (cutoffTime - a.time) / (b.time - a.time);
      if (f > 0) coords.push([a.lon + (b.lon - a.lon) * f, a.lat + (b.lat - a.lat) * f]);
    }
    break;
  }
  return coords;
}

function refreshSources() {
  const list = visiblePhotos();
  map.getSource('photos')?.setData(toGeoJSON(list));
  for (const trip of TRIPS) {
    map.getSource(`trail-${trip.id}`)?.setData({
      type: 'Feature', geometry: { type: 'LineString', coordinates: trailFor(trip.id) },
    });
  }
  buildList(list);
  updateScrub();
  renderThumbMarkers(list);
  updateStats(list);
}

// Photo thumbnails as DOM markers only for the *selected trip* (bounded count);
// the clustered GeoJSON layer carries the all-trips and stress-test scale.
function renderThumbMarkers(list) {
  for (const m of thumbMarkers) m.remove();
  thumbMarkers = [];
  if (activeTrip === 'all' || list.length > 300) return;
  for (const p of list) {
    const el = document.createElement('button');
    el.className = 'thumb-marker';
    el.dataset.id = p.id;
    el.innerHTML = `<img alt="" src="${photoThumb(p, 68)}" loading="lazy">`;
    el.addEventListener('click', () => selectPhoto(p.id, { fly: false }));
    thumbMarkers.push(new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat([p.lon, p.lat]).addTo(map));
  }
}

function buildList(list) {
  const ol = $('photo-list');
  ol.innerHTML = '';
  for (const p of list) {
    const li = document.createElement('li');
    li.dataset.id = p.id;
    li.textContent = `${new Date(p.time).toLocaleString()} — ${p.title}`;
    li.addEventListener('click', () => selectPhoto(p.id, { fly: true }));
    ol.appendChild(li);
  }
}

function updateStats(list = visiblePhotos()) {
  const thumbs = activeTrip !== 'all' && list.length <= 300 ? list.length : 0;
  $('stats').textContent = `${list.length.toLocaleString()} photos · ${TRIPS.length} trips · clustered GeoJSON + ${thumbs} DOM thumbs`;
}

function updateScrub() {
  const list = visiblePhotos();
  if (!list.length) return;
  const p = list[Math.min(currentIdx, list.length - 1)];
  $('scrub').value = String(Math.round((list.indexOf(p) / Math.max(1, list.length - 1)) * 1000));
  $('clock').textContent = new Date(p.time).toLocaleString();
}

function selectPhoto(id, { fly }) {
  const list = visiblePhotos();
  const p = list.find((x) => x.id === id) || photos.find((x) => x.id === id);
  if (!p) return;
  currentIdx = Math.max(0, list.indexOf(p));
  $('photo-card').innerHTML =
    `<img alt="" src="${photoThumb(p, 240)}"><strong>${p.emoji} ${p.title}</strong><br>` +
    `<span class="muted">${TRIPS.find((t) => t.id === p.tripId)?.name ?? p.tripId} · ${p.category}<br>${new Date(p.time).toLocaleString()}<br>${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}</span>`;
  document.querySelectorAll('#photo-list li').forEach((li) => li.classList.toggle('on', li.dataset.id === id));
  document.querySelectorAll('.thumb-marker').forEach((el) => el.classList.toggle('on', el.dataset.id === id));
  // Trail progress: draw the active trip's trail up to this photo.
  const src = map.getSource(`trail-progress`);
  src?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: partialTrail(p.tripId, p.time) } });
  if (fly) map.flyTo({ center: [p.lon, p.lat], zoom: Math.max(map.getZoom(), 11), speed: 1.2 });
  updateScrub();
}

function setProjection(kind) {
  // MapLibre GL JS v5 native projections: 'globe' | 'mercator'. Same sources/layers keep working.
  map.setProjection({ type: kind === 'globe' ? 'globe' : 'mercator' });
  if (kind === 'globe') map.setSky({ 'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 1, 7, 0] });
  $('btn-globe').classList.toggle('on', kind === 'globe');
  $('btn-flat').classList.toggle('on', kind !== 'globe');
}

function addLayers() {
  map.addSource('photos', { type: 'geojson', data: toGeoJSON(visiblePhotos()), cluster: true, clusterRadius: 48, clusterMaxZoom: 13 });
  map.addLayer({ id: 'clusters', type: 'circle', source: 'photos', filter: ['has', 'point_count'],
    paint: { 'circle-color': '#4361ee', 'circle-opacity': 0.85, 'circle-radius': ['step', ['get', 'point_count'], 16, 50, 22, 250, 30] } });
  map.addLayer({ id: 'cluster-count', type: 'symbol', source: 'photos', filter: ['has', 'point_count'],
    layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-font': ['Noto Sans Bold'], 'text-size': 12 }, paint: { 'text-color': '#fff' } });
  map.addLayer({ id: 'photo-points', type: 'circle', source: 'photos', filter: ['!', ['has', 'point_count']],
    paint: { 'circle-color': ['match', ['get', 'tripId'], 'kyoto', '#e4572e', 'taipei', '#2a9d8f', '#4361ee'], 'circle-radius': 6, 'circle-stroke-width': 2, 'circle-stroke-color': '#fff' } });

  for (const trip of TRIPS) {
    map.addSource(`trail-${trip.id}`, { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: trailFor(trip.id) } } });
    map.addLayer({ id: `trail-${trip.id}`, type: 'line', source: `trail-${trip.id}`,
      paint: { 'line-color': trip.color, 'line-width': 2.5, 'line-opacity': 0.35, 'line-dasharray': [2, 2] } });
  }
  map.addSource('trail-progress', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] } } });
  map.addLayer({ id: 'trail-progress', type: 'line', source: 'trail-progress',
    layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#111', 'line-width': 4, 'line-opacity': 0.85 } });

  map.on('click', 'clusters', (e) => {
    const f = map.queryRenderedFeatures(e.point, { layers: ['clusters'] })[0];
    map.getSource('photos').getClusterExpansionZoom(f.properties.cluster_id).then((zoom) =>
      map.easeTo({ center: f.geometry.coordinates, zoom }));
  });
  map.on('click', 'photo-points', (e) => selectPhoto(e.features[0].properties.id, { fly: false }));
  for (const id of ['clusters', 'photo-points']) {
    map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
  }
}

window.__spikeMap = map; // spike debugging handle
let layersReady = false;
map.on('load', () => {
  if (!layersReady) { addLayers(); layersReady = true; }
  setProjection('globe');
  refreshSources();
  const first = visiblePhotos()[0];
  if (first) selectPhoto(first.id, { fly: false });
});

map.on('style.load', () => {
  if (!map.getSource('photos')) { addLayers(); layersReady = true; refreshSources(); }
});

// Controls
$('btn-globe').addEventListener('click', () => setProjection('globe'));
$('btn-flat').addEventListener('click', () => setProjection('flat'));
$('style-select').addEventListener('change', (e) => map.setStyle(STYLES[e.target.value]));
const tripSelect = $('trip-select');
for (const t of TRIPS) { const o = document.createElement('option'); o.value = t.id; o.textContent = t.name; tripSelect.appendChild(o); }
tripSelect.addEventListener('change', (e) => {
  activeTrip = e.target.value; currentIdx = 0; refreshSources();
  const list = visiblePhotos();
  if (list.length) {
    const bounds = new maplibregl.LngLatBounds();
    for (const p of list) bounds.extend([p.lon, p.lat]);
    map.fitBounds(bounds, { padding: 60, maxZoom: 13 });
    selectPhoto(list[0].id, { fly: false });
  }
});
$('btn-stress').addEventListener('click', (e) => {
  photos = generatePhotos({ stress: 5000 });
  e.target.disabled = true; e.target.textContent = '+5,000 added';
  refreshSources();
});
$('scrub').addEventListener('input', (e) => {
  const list = visiblePhotos();
  currentIdx = Math.round((Number(e.target.value) / 1000) * (list.length - 1));
  if (list[currentIdx]) selectPhoto(list[currentIdx].id, { fly: false });
});
function setPlaying(on) {
  playing = on;
  $('btn-play').textContent = on ? '⏸ Pause' : '▶ Play trail';
  clearInterval(playTimer);
  if (on) {
    playTimer = setInterval(() => {
      const list = visiblePhotos();
      currentIdx += 1;
      if (currentIdx >= list.length) { setPlaying(false); return; }
      selectPhoto(list[currentIdx].id, { fly: false });
    }, 450);
  }
}
$('btn-play').addEventListener('click', () => setPlaying(!playing));

// Local-tile presence check: the local style renders nothing outside the fetched extracts if this fails.
fetch('/tiles/protomaps-demo.pmtiles', { headers: { Range: 'bytes=0-126' } })
  .then((r) => { $('tile-status').textContent = (r.status === 200 || r.status === 206) ? '· local tiles ✓ (same-origin only)' : '· local tiles MISSING — run tools/fetch-tiles.sh'; })
  .catch(() => { $('tile-status').textContent = '· local tiles MISSING — run tools/fetch-tiles.sh'; });

// FPS meter (1s window) — the spike's built-in perf check.
let frames = 0, last = performance.now();
(function loop(now) {
  frames++;
  if (now - last >= 1000) { $('fps').textContent = `${frames} fps`; frames = 0; last = now; }
  requestAnimationFrame(loop);
})(performance.now());
