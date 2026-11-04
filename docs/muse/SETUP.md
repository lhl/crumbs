# Connecting a Muse agent to Crumbs (owner steps)

Crumbs stays on your hardware. The Muse agent reaches one port on one machine
through your private tunnel, with a read-only token. Your full archive never
leaves the box; only the answers to the questions the agent asks do.

## 1. Pick the tunnel

Use your tailnet (Tailscale or Headscale). Do not open a public port.

- Join the Crumbs machine and the Muse agent's VM to the same tailnet.
- Add an ACL that lets only the Muse VM reach the Crumbs machine on TCP 8770.
- Use the Crumbs machine's MagicDNS name, not its IP, everywhere: the IP can change when a
  device rejoins, and Muse approves each exact address form separately.

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

This can run alongside a token-free `crumbs serve` on 127.0.0.1 for the local PWA: the two
bind different addresses and read the same database.

If the agent platform injects credentials only on HTTPS requests (Muse does: on plain HTTP
the request arrives with its placeholder instead of the token, logged by Crumbs as
`placeholder '…:'`), put Tailscale Serve in front. It stays tailnet-only, with a valid certificate:

```bash
sudo tailscale serve --bg --https=8443 http://<tailnet IP of this machine>:8770
```

The base URL is then `https://<MagicDNS name>:8443`. Pick a free Serve port (443, 8443, or 10000);
`tailscale serve status` shows routes already in use.

A non-loopback bind refuses to start without `CRUMBS_API_TOKEN`. The Glimmer server
must also be reachable from this machine (`GLIMMER_URL`, default `http://127.0.0.1:18080`).

## 4. Configure the Muse agent

- The base URL (`https://<MagicDNS name>:8443` behind Serve, or `http://<MagicDNS name>:8770` directly) goes in the agent's plain configuration.
- Enter `CRUMBS_AGENT_TOKEN` through the agent platform's secure credential form, registered to
  that one host as a Bearer header. On Muse a helper sends a placeholder that is swapped for the
  real token only on requests to that host, so the token never appears in commands or chat.
- Give it [crumbs-skill.md](crumbs-skill.md) as a persisted skill (Muse repackages the
  "how to call" parts as helper commands).
- Set its HTTP timeout to at least 120 s: agent answers take 30 to 90 s.

## 5. Check it

From the Muse side, through its helper:

1. `GET /v1/health` with no auth: expect `{"status": "ok", ...}`.
2. One harmless authenticated call, e.g. `GET /v1/places?q=cafe`: this proves the credential
   swap works through the tunnel.
3. Chat tests: a known question ("where did I have soup dumplings in Taipei?"), an unknown one
   ("have I been to Paris?"), and an offline case (stop the server: the agent must say Crumbs is
   offline, not guess).

## What crosses the line

| Stays on your box | Goes to the Muse agent |
|---|---|
| Photos, EXIF/GPS, location history, the database, all model inference | The question, the answer text, the evidence cards (dates, read text, dish names, record ids), and photo previews only if the agent asks for one |
