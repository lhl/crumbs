// Synthetic spike data — invented places/photos, real city-scale coordinates only.
// No personal data: names, dishes, and photos are generated placeholders.

const TRIPS = [
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
  // Inline SVG placeholder: stands in for a local thumbnail file in the real product.
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}'>` +
    `<rect width='100%' height='100%' fill='hsl(${p.hue} 65% 72%)'/>` +
    `<text x='50%' y='58%' font-size='${size * 0.42}' text-anchor='middle'>${p.emoji}</text></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

export { TRIPS };
