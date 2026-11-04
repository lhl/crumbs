# Crumbs — Agent Guide

Crumbs is the project built in this repository for the Meta Global AI Developer Hackathon (building period Oct 27 – Nov 4, 2026; submissions due Nov 4, 9:00 PM ET). It reconstructs a searchable travel and food history — trips, visits, meals, and stays — from photos, check-ins, and location history, with every inferred place linked to its supporting evidence. See [BRAINSTORMING.md](BRAINSTORMING.md) for the product direction [README.md](README.md) for what is built, and [HACKATHON.md](HACKATHON.md) for the hackathon rules, judging rubric, and deadlines.

**This repository is public.** That fact outranks convenience in every rule below. This `AGENTS.md` is read every session and covers the ground rules that apply to every task. Its workflow is adapted from systems proven on earlier projects; do not copy content, paths, or context from other projects into this repo.

Instruction precedence: if this file conflicts with platform / system / developer instructions, follow those first.

## Non-Negotiables

1. **Nothing private ever gets committed.** No secrets or API keys, no personal data (real photos, location history, check-in exports, EXIF/GPS dumps), no personal identifiers (emails, account/team IDs, home paths), and no proprietary or third-party material we don't have the rights to publish. See "Public-Repo Safety".
2. **Commit each complete, validated logical unit immediately.** Do not wait to be asked, and do not start the next unit until the previous one is committed.
3. **Never use `git add .`, `git add -A`, or `git commit -a`** — stage exact paths.
4. **Leave unrelated or unexpectedly staged work untouched.** Never restore, reset, overwrite, or delete work you did not create for the current task.
5. **Durable handoffs use immutable files under `worklog/entries/`**; the root `WORKLOG.md` is a generated, ignored view. See `worklog/README.md`.
6. **Every claim about what the product does must match what is built.** Demo material, README copy, and the submission may only highlight features, code, and functionality built during the hackathon — judges must be able to identify what was created during the event.

## Start Here

| Path | Purpose |
| --- | --- |
| `README.md` | Product README: what Crumbs is, what's built, models, privacy line, how to run, docs index. |
| `HACKATHON.md` | Hackathon participant guide: rules, schedule, judging, prizes. |
| `BRAINSTORMING.md` | Product direction for Crumbs: problem, pipeline, model roles, demo scope, open checks. Living document, not a spec of built features. |
| `worklog/README.md` | Worklog entry format, validation, rendering, and hooks. |
| `worklog/entries/` | Immutable per-unit decisions, results, blockers, and handoffs. |
| `scripts/worklog.py` | Create/check/render worklog entries; install tracked git hooks. |
| `scripts/check_staged_safety.py` | Pre-commit backstop that rejects secrets, personal-data paths, and oversized files in the staged index. |
| `.githooks/` | Tracked hooks: worklog + public-safety checks, commit-message format, generated-view refresh. |

## Decision Authority

The human lead owns product direction. Their decisions are directives, not hypotheses.

- **Execute, then report.** When the lead makes a call, make the change and report what it means. Do not open a pre-execution review of a decision already made; post-change validation verifies the implementation, not the decision.
- **State disagreement once, and late** — briefly, after the work, or before it only when the action is irreversible, destructive, or materially wider than requested. Then let the call stand.
- **Reversible changes default to action.** A default, flag, or doc fix is reversible; make it and let the report carry the caveats.

## Public-Repo Safety

This is the section that prevents the one unrecoverable failure mode: leaking something into a public git history, where deleting it later requires a history rewrite and the data must still be treated as disclosed.

- **Secrets:** API keys (Meta Model API, Baseten, Modal, Fireworks, map/place providers), tokens, passwords, and key files live only in `.env` or the environment — never in code, docs, fixtures, screenshots, terminal captures pasted into entries, or commit messages. Refer to a credential by provider and purpose only ("the Meta Model API key in `.env`"), never by value, prefix, or suffix.
- **Personal data:** Crumbs' whole input domain — photos, EXIF/GPS metadata, Google/Foursquare location exports, check-ins — is personal data. Real personal data never enters git, including as test fixtures or demo assets. Work on real collections locally under the ignored directories in `.gitignore` (`data/`, `photos/`, `exports/`, `location-history/`, `takeout/`); commit only synthetic fixtures, or fixtures built from media that is explicitly consented for public use and has been reviewed for people, plates, addresses, and embedded GPS. Record that review in the unit's worklog entry.
- **Identifiers:** no personal emails, account or team IDs, phone numbers, home-directory paths (`/home/<you>/…` — use `~/` or repo-relative paths in prose), or exact home/work addresses. Hackathon team/account details stay out of this repo.
- **Proprietary material:** no code, data, or text copied from private or employer/client repositories (including the sibling projects this guide's workflow was adapted from — workflow *patterns* only, re-derived here), and no third-party assets without a license that permits redistribution. When porting an idea from an external source, record the source and its license in the commit message or worklog entry.
- **Before every commit**, the staged-safety check runs via the pre-commit hook: `python3 scripts/check_staged_safety.py`. It rejects credential/env files, personal-data paths, location-export and model-weight file types, files over 5 MiB, and high-confidence secret patterns. A bypass requires an explicit human decision recorded in a worklog entry — `--no-verify` without one is a rule violation.
- **If something private is committed anyway:** stop, tell the lead immediately, and treat the value/data as disclosed (rotate the credential). Do not quietly rewrite shared history without the lead's explicit instruction.
- **Demo and submission hygiene:** the public demo, video, and repo screenshots show only the consented/privacy-safe subset chosen in `BRAINSTORMING.md`'s next checks — no private locations, bystanders, or raw location history.

## Ground Rules

- **Source of truth for direction:** [BRAINSTORMING.md](BRAINSTORMING.md) until a real plan/spec replaces it; update it in the same commit when direction moves. Update `HACKATHON.md` only for hackathon-logistics facts, not as a worklog.
- **The root `README.md` is the product page** (since 2026-11-05; the hackathon guide moved to `HACKATHON.md`). It describes only what is built and measured, follows non-negotiable 6, and is not an implementation diary — history goes in `worklog/entries/`, and neither `README.md` nor `BRAINSTORMING.md` becomes one.
- **Preserve provenance and uncertainty.** Crumbs reconciles conflicting evidence; derived records must not overwrite source data, and code/docs must keep observed facts, model inferences, external lookup results, and user confirmations distinguishable. Never infer an exact restaurant from food appearance alone, and keep unknown places/dates unknown rather than forcing confident output.
- **No hard-coded home directories in prose or code.** Use `~/` outside the repo and repo-relative paths inside it.
- **Don't maximize model count.** Use multiple Meta models only where each improves the result (roles and open questions are in `BRAINSTORMING.md`); validate a model's capability on a real example before committing the integration to it. Do not claim local-only processing if data goes to a cloud API.
- **Flags are a cost, not a feature.** Prefer no flag; a necessary flag defaults to the production behavior and gets its removal condition recorded in the unit's worklog entry.

## Workflow

### Before Starting

1. `git status -sb` — note unrelated changes and leave them alone.
2. Read the relevant part of [BRAINSTORMING.md](BRAINSTORMING.md) and the latest relevant files under `worklog/entries/` (or `python3 scripts/worklog.py render` and read `WORKLOG.md`).

### During Work

- Keep changes scoped to one logical unit (one importer, one pipeline stage, one UI surface, one doc).
- Keep real personal data in the ignored local directories from the start; do not "temporarily" copy it into tracked paths.
- For a substantial unit, create a worklog entry before completion (below) and update it with non-trivial decisions, measurements, and dependency additions.

### Worklog

```bash
python3 scripts/worklog.py new --worker <stable-worker-or-lane-id> --status completed --title "Short outcome"
python3 scripts/worklog.py check
python3 scripts/worklog.py render
```

- Statuses: `completed`, `checkpoint`, `decision`, `blocked`, `handoff`. Fixed sections: `## Summary`, `## Changes`, `## Validation`, `## Next`.
- One entry per substantial logical unit; commit it with that unit. Not for trivial edits.
- Entries are **immutable after commit**: never edit, rename, or delete one. Correct a conclusion with a new `decision`/`checkpoint` entry that names the superseded entry.
- Activate the tracked hooks once per trusted clone: `python3 scripts/worklog.py install-hooks` (sets `core.hooksPath=.githooks`; refuse to force over an existing value without lead approval).

### After Changes (before claiming done)

- Run the narrowest relevant check for the change (tests once they exist; `python3 -m py_compile` for scripts; re-read for docs), then record the exact commands and outcomes in the worklog entry.
- Exercise a user-facing change through the surface a user reaches, not only its test harness, and confirm the intended path actually ran.
- Run `python3 scripts/worklog.py check`, `python3 scripts/worklog.py render`, `python3 scripts/check_staged_safety.py` (after staging), and `git diff --check` as applicable.
- **Commit immediately** — see Git Discipline.

## Git Discipline

- Commit working states only, one logical unit at a time; docs and repo setup are first-class units. Include the unit's new `worklog/entries/<entry>.md` when one was created.
- Stage exact paths, then verify exactly what the commit will record:

  ```bash
  git status -sb
  git diff --staged --name-only
  git diff --staged
  ```

- Commit messages use this format (enforced by `.githooks/commit-msg`); single-line commits are not allowed:

  ```text
  type: short imperative summary (≤ 72 chars)

  - Explain the concrete change and why it belongs in this unit.
  - Record validation performed and any important result or limitation.
  ```

  Prefixes: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `perf:`, `ci:`, `build:`, `security:`. **No bylines** — no `Co-authored-by`, agent attribution, or generated-by footers; no session URLs.
- Never run `git restore`, `git checkout --`, `git reset --hard`, `git clean -fd`, bulk `rm -rf` over tracked paths, history rewrites, or force-pushes unless the lead explicitly asks.
- A local commit does not authorize a push, release, or submission. The GitHub remote, demo video, and Cerebral Valley submission each need the lead's go-ahead.

### Never Committed

Secrets and env files, real photos/location/check-in data and anything derived that still identifies places or people, model weights, compiled artifacts and caches, raw API-response dumps containing personal data, and agent-runner state (`.claude/`, `.codex/`, `.pi/`, `.multiloop/`). `.gitignore` encodes this list; if you have to force-add past it, stop and get a recorded human decision first.

## Coordination

- The working tree is shared state; other agents or the human may be editing concurrently. **High-conflict files:** `AGENTS.md`, `BRAINSTORMING.md`, `scripts/worklog.py`, `scripts/check_staged_safety.py`, `.gitignore`. Stop and coordinate on same-file contention; the designated agent stages and commits their scoped hunks first.
- Worklog entry filenames are unique and should not conflict.
- If a commit reports "nothing to commit", a concurrent commit may already have swept your paths — check `git log -3 --stat` before redoing work. Do not amend another worker's commit.

## Handling Blockers

| Situation | Action |
| --- | --- |
| A feature is implemented but never exercised | Run it and report what it does; absence of a benchmark is not a defect. |
| A dataset/export format is assumed but uninspected | Inspect the actual export (fields, timestamps/timezones, place IDs, precision) before building on it — see the open checks in `BRAINSTORMING.md`. |
| Tempted to commit real photos/location data "just as a fixture" | Don't. Build a synthetic or consented, reviewed fixture instead (Public-Repo Safety). |
| A safety check flags your staged file | Fix the content or move it to an ignored path. Bypass only with a recorded human decision. |
| Secret or personal data already committed | Stop, notify the lead, treat it as disclosed (rotate credentials); no silent history rewrite. |
| Merge conflict in a high-conflict file | Stop and coordinate; do not force-stage or revert. |
| Unrelated files changed in the worktree | Leave them; another agent or the human owns them. |

## Communication

- Lead with the substantive finding or result, not just what command was run.
- Distinguish measured from inferred, observed from model-generated, and built from planned — especially in anything a judge might read.
- If work is in progress, state the current concrete result or explicitly say there is no result yet.
