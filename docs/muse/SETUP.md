# Connecting a Muse agent to Crumbs (owner steps)

Crumbs stays on your hardware. The Muse agent reaches one port on one machine
through your private tunnel, with a read-only token. Your full archive never
leaves the box; only the answers to the questions the agent asks do.

## 1. Pick the tunnel

Use your tailnet (Tailscale or Headscale). Do not open a public port.

- Join the Crumbs machine and the Muse agent's VM to the same tailnet.
- Add an ACL that lets only the Muse VM reach the Crumbs machine on TCP 8770.

## 2. Create two tokens

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # run twice
```

- `CRUMBS_API_TOKEN`: the owner token (PWA, phone location updates, review answers).
- `CRUMBS_AGENT_TOKEN`: the Muse token. It is read-only and capped at privacy tier 1
  (coordinates rounded to about 1 km, file names stripped).

Put both in the Crumbs machine's `.env` or environment, never in git.

## 3. Run Crumbs on the tailnet address

```bash
CRUMBS_API_TOKEN=... CRUMBS_AGENT_TOKEN=... crumbs serve --host <tailnet IP of this machine>
```

A non-loopback bind refuses to start without `CRUMBS_API_TOKEN`. The Glimmer server
must also be reachable from this machine (`GLIMMER_URL`, default `http://127.0.0.1:18080`).

## 4. Configure the Muse agent

- Store `CRUMBS_URL` (`http://<tailnet IP>:8770`) and `CRUMBS_AGENT_TOKEN` in the agent's
  vault or secret store.
- Give it [crumbs-skill.md](crumbs-skill.md) as a persisted skill.
- Set its HTTP timeout to at least 120 s: agent answers take 30 to 90 s.

## 5. Check it

From the Muse VM:

```bash
curl -s $CRUMBS_URL/v1/health
curl -s -H "Authorization: Bearer $CRUMBS_AGENT_TOKEN" "$CRUMBS_URL/v1/ask?q=what%20did%20I%20eat%20in%20Kyoto%3F"
```

Then ask the agent a question in chat, for example "where did I have soup dumplings in Taipei?".

## What crosses the line

| Stays on your box | Goes to the Muse agent |
|---|---|
| Photos, EXIF/GPS, location history, the database, all model inference | The question, the answer text, the evidence cards (dates, read text, dish names, record ids), and photo previews only if the agent asks for one |
