# Worklog entries

This directory is the durable cross-session journal. It uses immutable, one-file-per-logical-unit entries so agents can work in the same worktree or merge separate worktree branches without contending on one `WORKLOG.md`.

## Why shards instead of one shared file?

- A unique entry path does not overwrite another worker's write in a shared worktree.
- Independent branches normally merge by adding different files, with no content conflict.
- Entries retain their original worker, branch, base commit, decision, and validation context.
- The root `WORKLOG.md` remains convenient to read but is generated and ignored, so it never becomes a merge hotspot.

Long-lived per-worker files were deliberately avoided: worker names and sessions are reused, which eventually turns those files into shared append targets again.

## Create an entry

At the end of a substantial logical unit, decision, benchmark, blocker, or handoff:

```bash
python3 scripts/worklog.py new \
  --worker <stable-worker-or-lane-id> \
  --status completed \
  --title "Short outcome"
```

The command prints the new path. Replace every placeholder while keeping this fixed section order:

1. `## Summary`
2. `## Changes`
3. `## Validation`
4. `## Next`

Allowed statuses are `completed`, `checkpoint`, `decision`, `blocked`, and `handoff`.

Use one entry for one logical unit, and commit it with that unit. Do not create entries for every trivial edit or shell command. Prefer information a later worker needs: conclusions, exact benchmark/test commands and results, changed interfaces, known gaps, and concrete next steps.

## Append-only rule

Files under `worklog/entries/` are immutable after commit. Do not edit, rename, or delete an existing entry. Add a new `decision` or `checkpoint` entry that identifies and corrects the old conclusion. This preserves provenance and lets validation reject accidental rewrites.

## Validate and read

```bash
python3 scripts/worklog.py check
python3 scripts/worklog.py render
```

`render` atomically rebuilds the ignored root `WORKLOG.md` in timestamp order.

To validate append-only entries, enforce the repository commit-message format, and refresh the view automatically after commits, merges, and checkouts, activate the tracked hooks once per trusted clone/branch:

```bash
python3 scripts/worklog.py install-hooks
```

The installer refuses to replace an existing `core.hooksPath` unless `--force` is explicitly supplied. Git config is shared by linked worktrees, so one installation normally covers every worktree for the clone. Because this setting executes version-controlled hook code, do not install it from an untrusted fork or leave it active while checking out unreviewed branches.
