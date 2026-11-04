# Skill: Crumbs, the owner's private food and travel memory

Give this document to the Muse agent as a persisted skill. It describes how to
ask Crumbs about the owner's own meals, places, and trips. Crumbs runs on the
owner's hardware; you reach it over the owner's private tunnel. The URL and
token are configured in the agent's vault or secret store, never in chat,
files, or this document.

## Connection

- Base URL: the `CRUMBS_URL` secret (a private tunnel address, port 8770 by default).
- Auth: send `Authorization: Bearer <CRUMBS_AGENT_TOKEN secret>` on every request except
  `/v1/health`. Never print, log, or repeat the token.
- This token is read-only and capped at privacy tier 1: coordinates are rounded to
  about 1 km and file names are stripped, whatever you request.

## Always check health first

`GET /v1/health` (no auth) returns `{"status": "ok", "counts": {...}}`.
If it fails or times out, tell the owner "Crumbs is offline right now" and stop.
Never answer a Crumbs question from memory or guesswork.

## Main endpoint: ask a question

`GET /v1/ask?q=<url-encoded question>&agent=1`

- Runs the owner's local Muse Glimmer agent over the history. It plans lookups,
  can look again at the owner's photos, and writes a short cited answer.
- Takes **30 to 90 seconds**. Use a request timeout of at least 120 s. Tell the owner
  you're checking their history while it runs.
- Without `agent=1` a fast deterministic parser answers (under a second). It handles
  simple forms like "where did I have soup dumplings in Taipei?" and "what did I eat in
  Kyoto?". Use it if the agent call times out.
- For "around here" questions, add `&near=current`. The owner's phone posts its location
  to Crumbs directly, so you never need or receive raw coordinates.

The response is JSON:

```json
{
  "status": "answered | unknown",
  "answer": "short text with citations like [p123] or [v45]",
  "results": [
    {"visit_id": 45, "date": "YYYY-MM-DD", "moment": "12:46–13:15",
     "place": {"name": null, "source": null, "status": null},
     "text_names": ["words read in the photos"],
     "dishes": [{"name": "eel rice bowl", "basis": "seen | read_on_menu | receipt"}],
     "media": [123, 124]}
  ],
  "agent": {"used": true, "latency_s": 70.2, "trace": [...], "grounding": {...}}
}
```

## How to relay answers

- Relay the answer in your own words, and remove the `[p…]`/`[v…]` citation markers.
- **Keep Crumbs' certainty words.** "probably", "photo text reads X", "a closer look reads X",
  "you confirmed", and "unnamed" mean different things. Do not upgrade a guess to a fact.
- `status: "unknown"` means the history has no record of it. Say so. It does not mean the
  owner never went there.
- Do not add facts about a place from general knowledge (opening hours, reviews,
  addresses) unless the owner asks. If you do look something up on the web, say it came
  from the web, not from their history.
- Do not reveal coordinates, file names, or other people in photos.

## Photos

`GET /v1/media/<media id>/preview` returns a stripped JPEG preview (no EXIF/GPS).
Fetch one only when the owner asks to see the photo, and show it only to the owner.

## Other read-only endpoints

| Endpoint | Use |
|---|---|
| `GET /v1/search?q=<text>&category=food` | Photos whose read text matches; categories: food, sightseeing, trip, personal, unknown |
| `GET /v1/visits?from=YYYY-MM-DD&to=YYYY-MM-DD` | Visits (photo groups) in a date range |
| `GET /v1/visit/<visit id>` | One visit with its photos and candidate places |
| `GET /v1/places?q=<name>` | Places in the local registry by name |
| `GET /v1/nearby?near=current&radius_m=1000` | Registry places near the owner's current location |

## What you cannot do

- Writes are refused (HTTP 403). The owner answers Crumbs' review questions ("Was this
  X?") in the Crumbs app, not through you.
- One request at a time: the local server is single-threaded, so a running `agent=1`
  question delays other calls. Do not fire calls in parallel.
