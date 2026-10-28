// Synthetic spike data — invented places/photos, real city-scale coordinates only.
// No personal data: names, dishes, and photos are generated placeholders.

let TRIPS = [
  {
    id: 'kyoto',
    name: 'Kyoto — food trip (synthetic)',
    color: '#e4572e',
    anchors: [
      [135.7681, 35.0116], [135.7639, 35.0046], [135.7712, 35.0179],
      [135.7597, 35.0007], [135.7755, 35.0128], [135.7662, 35.0211],
    ],
    kinds: ['grilled fish counter', 'ramen bar', 'market stall', 'tea house', 'izakaya', 'bakery'],
    cat: 'food',
  },
  {
    id: 'taipei',
    name: 'Taipei — coffee & night markets (synthetic)',
    color: '#2a9d8f',
    anchors: [
      [121.5644, 25.033], [121.5598, 25.0412], [121.5712, 25.0289],
      [121.5535, 25.0367], [121.5651, 25.0455],
    ],
    kinds: ['coffee shop', 'night market stall', 'noodle shop', 'bookstore cafe', 'breakfast stand'],
    cat: 'food',
  },
  {
    id: 'lisbon',
    name: 'Lisbon — sightseeing (synthetic)',
    color: '#4361ee',
    anchors: [
      [-9.1427, 38.7223], [-9.1503, 38.7167], [-9.1365, 38.7281],
      [-9.1589, 38.7112], [-9.1312, 38.7195],
    ],
    kinds: ['viewpoint', 'tram street', 'tile facade', 'harbor', 'old town square'],
    cat: 'sightseeing',
  },
];

// Deterministic PRNG so the spike is reproducible.
function mulberry32(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const EMOJI = { food: '🍽️', sightseeing: '📷', trip: '🧭', personal: '🏠' };

export function generatePhotos({ stress = 0 } = {}) {
  const rand = mulberry32(42);
  const photos = [];
  let t = Date.UTC(2026, 3, 4, 9, 0); // Apr 4 2026
  for (const trip of TRIPS) {
    const perTrip = 42;
    for (let i = 0; i < perTrip; i++) {
      const a = trip.anchors[i % trip.anchors.length];
      const lon = a[0] + (rand() - 0.5) * 0.012;
      const lat = a[1] + (rand() - 0.5) * 0.009;
      t += (20 + rand() * 90) * 60_000; // 20–110 min between photos
      const kind = trip.kinds[i % trip.kinds.length];
      photos.push({
        id: `${trip.id}-${i}`,
        tripId: trip.id,
        lon, lat,
        time: t,
        title: `${kind} #${i + 1}`,
        category: trip.cat,
        emoji: EMOJI[trip.cat],
        hue: Math.floor(rand() * 360),
      });
    }
    t += 36 * 3600_000; // gap between trips
  }
  if (stress > 0) {
    // Cheap stress fixtures: jittered world points used only to exercise clustering.
    for (let i = 0; i < stress; i++) {
      const trip = TRIPS[i % TRIPS.length];
      const a = trip.anchors[i % trip.anchors.length];
      photos.push({
        id: `stress-${i}`, tripId: trip.id,
        lon: a[0] + (rand() - 0.5) * 0.4, lat: a[1] + (rand() - 0.5) * 0.3,
        time: t + i * 60_000, title: `stress photo ${i}`, category: 'trip',
        emoji: EMOJI.trip, hue: Math.floor(rand() * 360),
      });
    }
  }
  return photos.sort((a, b) => a.time - b.time);
}

export function photoThumb(p, size = 56) {
  if (p.img) return p.img; // real corpus: local analysis JPEG served from /photos/<id>.jpg
  // Inline SVG placeholder: stands in for a local thumbnail file in the real product.
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}'>` +
    `<rect width='100%' height='100%' fill='hsl(${p.hue} 65% 72%)'/>` +
    `<text x='50%' y='58%' font-size='${size * 0.42}' text-anchor='middle'>${p.emoji}</text></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

const TRIP_COLORS = ['#e4572e', '#2a9d8f', '#4361ee', '#f4a261', '#8338ec', '#06d6a0', '#ef476f', '#118ab2'];
const EMOJI_ALL = { food: '🍽️', sightseeing: '📷', trip: '🧭', personal: '🏠', unknown: '❔', unclassified: '📍' };

// Real corpus mode: /crumbs-data.json is produced by `crumbs export-spike`
// (photo points + visits + trips from the local evidence store) and the
// analysis thumbnails by copying data/crumbs/analysis files to /photos/.
// Both are git-ignored personal data; when the file is absent the spike
// falls back to the synthetic set above.
export async function loadRealData() {
  try {
    const resp = await fetch('/crumbs-data.json');
    if (!resp.ok) return null;
    const data = await resp.json();
    if (!data.features?.length) return null;
    TRIPS = data.trips.map((t, i) => ({
      id: `trip-${t.id}`,
      name: `Trip ${t.started_at.slice(0, 10)} → ${t.ended_at.slice(0, 10)}`,
      color: TRIP_COLORS[i % TRIP_COLORS.length],
    }));
    const photos = data.features.map((f) => {
      const p = f.properties;
      const cat = p.category || 'unclassified';
      return {
        id: `m${p.media_id}`,
        tripId: p.trip_id != null ? `trip-${p.trip_id}` : 'unassigned',
        lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1],
        time: Date.parse(p.captured_at.replace(' ', 'T')),
        title: p.rel_path.split('/').pop(),
        category: cat, emoji: EMOJI_ALL[cat] || '📍',
        hue: (p.media_id * 47) % 360,
        img: `/photos/${p.media_id}.jpg`,
        visitId: p.visit_id,
      };
    }).filter((p) => Number.isFinite(p.time));
    return photos.sort((a, b) => a.time - b.time);
  } catch {
    return null;
  }
}

export { TRIPS };
