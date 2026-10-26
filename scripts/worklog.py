#!/usr/bin/env python3
"""Create, validate, and render contention-free worklog entries.

Tracked history lives in immutable Markdown files under ``worklog/entries``.
``WORKLOG.md`` is an ignored, generated view for convenient reading.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("WORKLOG_ROOT") or Path(__file__).resolve().parents[1])
ENTRY_DIR = ROOT / "worklog" / "entries"
DEFAULT_OUTPUT = ROOT / "WORKLOG.md"
REQUIRED_FIELDS = (
    "timestamp",
    "worker",
    "branch",
    "worktree",
    "base_commit",
    "status",
    "topic",
)
REQUIRED_SECTIONS = ("## Summary", "## Changes", "## Validation", "## Next")
ALLOWED_STATUSES = {"completed", "checkpoint", "decision", "blocked", "handoff"}
HOOK_NAMES = ("pre-commit", "commit-msg", "post-checkout", "post-merge", "post-commit")
PLACEHOLDERS = ("<required>", "<none-or-required-follow-up>")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
FILENAME_RE = re.compile(
    r"^\d{8}T\d{6}\.\d{6}Z-[a-z0-9][a-z0-9-]*-[a-z0-9][a-z0-9-]*-[0-9a-f]{6}\.md$"
)


class WorklogError(ValueError):
    """A worklog entry is malformed."""


def run_git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise WorklogError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def slugify(value: str, *, fallback: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    # Strip again after truncation: a cut that lands on a separator would
    # otherwise produce a slug that ``parse_entry`` rejects for its own topic.
    return value[:48].strip("-") or fallback


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def git_context() -> tuple[str, str, str]:
    branch = run_git("branch", "--show-current") or f"detached-{run_git('rev-parse', '--short', 'HEAD')}"
    base_commit = run_git("rev-parse", "HEAD")
    worktree = ROOT.name
    return branch, worktree, base_commit


def default_worker() -> str:
    return (
        os.environ.get("WORKLOG_WORKER", "").strip()
        or run_git("config", "--get", "user.name", check=False)
        or os.environ.get("USER", "").strip()
        or "worker"
    )


def entry_template(
    *,
    timestamp: datetime,
    worker: str,
    branch: str,
    worktree: str,
    base_commit: str,
    status: str,
    topic: str,
    title: str,
) -> str:
    iso_timestamp = timestamp.isoformat(timespec="microseconds").replace("+00:00", "Z")
    return f"""---
timestamp: {iso_timestamp}
worker: {worker}
branch: {branch}
worktree: {worktree}
base_commit: {base_commit}
status: {status}
topic: {topic}
---

# {title.strip()}

## Summary

<required>

## Changes

- <required>

## Validation

- <required>

## Next

- <none-or-required-follow-up>
"""


def create_entry(args: argparse.Namespace) -> int:
    if args.status not in ALLOWED_STATUSES:
        raise WorklogError(f"unsupported status: {args.status}")

    title = args.title.strip()
    worker = args.worker.strip() if args.worker else default_worker()
    if not title:
        raise WorklogError("title must not be empty")
    if not worker:
        raise WorklogError("worker must not be empty")

    now = utc_now()
    worker_slug = slugify(worker, fallback="worker")
    topic = slugify(args.topic or title, fallback="work")
    branch, worktree, base_commit = git_context()
    stamp = now.strftime("%Y%m%dT%H%M%S.%fZ")
    ENTRY_DIR.mkdir(parents=True, exist_ok=True)

    for _ in range(10):
        suffix = secrets.token_hex(3)
        path = ENTRY_DIR / f"{stamp}-{worker_slug}-{topic}-{suffix}.md"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue
        content = entry_template(
            timestamp=now,
            worker=worker,
            branch=branch,
            worktree=worktree,
            base_commit=base_commit,
            status=args.status,
            topic=topic,
            title=title,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        print(path.relative_to(ROOT))
        return 0

    raise WorklogError("could not allocate a unique worklog entry filename")


def parse_entry(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise WorklogError("missing opening frontmatter delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise WorklogError("missing closing frontmatter delimiter") from exc

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            raise WorklogError(f"malformed frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise WorklogError(f"empty frontmatter key/value: {line!r}")
        if key in fields:
            raise WorklogError(f"duplicate frontmatter field: {key}")
        fields[key] = value

    missing = [field for field in REQUIRED_FIELDS if field not in fields]
    extra = [field for field in fields if field not in REQUIRED_FIELDS]
    if missing:
        raise WorklogError(f"missing frontmatter fields: {', '.join(missing)}")
    if extra:
        raise WorklogError(f"unknown frontmatter fields: {', '.join(extra)}")
    if tuple(fields) != REQUIRED_FIELDS:
        raise WorklogError("frontmatter fields are out of order")

    timestamp_text = fields["timestamp"]
    if not TIMESTAMP_RE.fullmatch(timestamp_text):
        raise WorklogError("timestamp must use YYYY-MM-DDTHH:MM:SS.ffffffZ format")
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorklogError(f"invalid timestamp: {timestamp_text}") from exc
    if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() != timezone.utc.utcoffset(None):
        raise WorklogError("timestamp must include UTC timezone")
    if fields["status"] not in ALLOWED_STATUSES:
        raise WorklogError(f"unsupported status: {fields['status']}")
    if not re.fullmatch(r"[0-9a-f]{40}", fields["base_commit"]):
        raise WorklogError("base_commit must be a full 40-character lowercase commit hash")
    if slugify(fields["topic"], fallback="") != fields["topic"]:
        raise WorklogError("topic must be a lowercase kebab-case slug")

    body = "\n".join(lines[end + 1 :]).strip() + "\n"
    if not body.startswith("# "):
        raise WorklogError("body must begin with a level-one title")
    positions: list[int] = []
    for section in REQUIRED_SECTIONS:
        count = body.count(section)
        if count != 1:
            raise WorklogError(f"expected exactly one {section!r} heading, found {count}")
        positions.append(body.index(section))
    if positions != sorted(positions):
        raise WorklogError("required sections are out of order")
    for index, section in enumerate(REQUIRED_SECTIONS):
        content_start = positions[index] + len(section)
        content_end = positions[index + 1] if index + 1 < len(positions) else len(body)
        if not body[content_start:content_end].strip():
            raise WorklogError(f"{section!r} section is empty")
    for line in body.splitlines():
        candidate = line.strip().removeprefix("- ").strip()
        if candidate in PLACEHOLDERS:
            raise WorklogError(f"unfinished placeholder remains: {candidate}")
    if any(marker in text for marker in ("<<<<<<<", "=======", ">>>>>>>")):
        raise WorklogError("git conflict marker present")

    return fields, text.rstrip() + "\n"


def git_entry_paths(source: str) -> set[Path]:
    """Return entry paths from a git source: the index or committed HEAD.

    ``index`` (``git ls-files``) covers tracked entries plus any entry staged
    for the current commit. ``head`` (``git ls-tree HEAD``) covers only entries
    already committed. Untracked, uncommitted files are intentionally excluded
    so one agent's in-progress template cannot block another agent in a shared
    worktree.
    """
    rel = str(ENTRY_DIR.relative_to(ROOT))
    if source == "index":
        output = run_git("ls-files", "--", rel, check=False)
    elif source == "head":
        output = run_git("ls-tree", "-r", "--name-only", "HEAD", "--", rel, check=False)
    else:
        raise WorklogError(f"unknown entry source: {source}")
    return {ROOT / path for path in output.splitlines() if path}


def append_only_errors() -> list[str]:
    entry_dir = str(ENTRY_DIR.relative_to(ROOT))
    if run_git("rev-parse", "--verify", "HEAD", check=False) == "":
        return []
    output = run_git("diff", "--name-status", "HEAD", "--", entry_dir)
    errors: list[str] = []
    for line in output.splitlines():
        if not line:
            continue
        status, *paths = line.split("\t")
        if status != "A":
            rendered_paths = " -> ".join(paths)
            errors.append(f"tracked worklog entries are immutable: {status} {rendered_paths}")

    # The pre-commit hook validates working-tree contents. Reject a staged
    # entry that was edited again so an older, unvalidated index copy cannot
    # be committed while the newer working copy passes format validation.
    for path in run_git("diff", "--name-only", "--", entry_dir).splitlines():
        if path:
            errors.append(f"worklog entry differs from its staged content: {path}")
    return errors


def validate_entries(
    *,
    enforce_append_only: bool = True,
    scope: str = "commit",
) -> list[tuple[Path, dict[str, str], str]]:
    """Validate worklog entries and return them sorted.

    ``scope`` selects which entry files are format-validated so an in-progress,
    uncommitted template from another agent cannot block a commit in a shared
    worktree:

    - ``commit`` (default, used by ``check``): entries in the index, i.e.
      already-tracked entries plus entries staged for the current commit.
    - ``render``: committed ``HEAD`` entries only, so the aggregate reflects
      durable history and ignores in-progress untracked and staged files.
    """
    if scope == "commit":
        relevant = git_entry_paths("index")
    elif scope == "render":
        relevant = {path for path in git_entry_paths("head") if path.is_file()}
    else:
        raise WorklogError(f"unknown validation scope: {scope}")

    errors: list[str] = []
    parsed: list[tuple[Path, dict[str, str], str]] = []

    for path in sorted(relevant):
        if not FILENAME_RE.fullmatch(path.name):
            errors.append(f"{path.relative_to(ROOT)}: invalid filename")
            continue
        try:
            fields, text = parse_entry(path)
        except (OSError, UnicodeError, WorklogError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
            continue
        expected_stamp = datetime.fromisoformat(fields["timestamp"].replace("Z", "+00:00")).strftime(
            "%Y%m%dT%H%M%S.%fZ"
        )
        expected_worker = slugify(fields["worker"], fallback="worker")
        expected_prefix = f"{expected_stamp}-{expected_worker}-{fields['topic']}-"
        if not path.name.startswith(expected_prefix):
            errors.append(f"{path.relative_to(ROOT)}: filename does not match entry metadata")
            continue
        parsed.append((path, fields, text))

    if enforce_append_only:
        errors.extend(append_only_errors())

    if errors:
        raise WorklogError("\n".join(errors))

    parsed.sort(key=lambda item: (item[1]["timestamp"], item[0].name))
    return parsed


def check_entries(args: argparse.Namespace) -> int:
    parsed = validate_entries(enforce_append_only=not args.allow_modified, scope="commit")
    print(f"worklog: {len(parsed)} valid entr{'y' if len(parsed) == 1 else 'ies'}")
    return 0


def rendered_worklog(parsed: list[tuple[Path, dict[str, str], str]]) -> str:
    lines = [
        "# WORKLOG",
        "",
        "> Generated from immutable tracked entries in `worklog/entries/`.",
        "> Do not edit this file; run `python3 scripts/worklog.py render`.",
        "",
    ]
    if not parsed:
        lines.extend(["No worklog entries yet.", ""])
        return "\n".join(lines)

    for index, (path, _fields, text) in enumerate(parsed):
        if index:
            lines.extend(["", "---", ""])
        lines.extend([f"<!-- source: {path.relative_to(ROOT)} -->", "", text.rstrip()])
    lines.append("")
    return "\n".join(lines)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def render(args: argparse.Namespace) -> int:
    parsed = validate_entries(enforce_append_only=False, scope="render")
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    atomic_write(output, rendered_worklog(parsed))
    try:
        display_path = output.relative_to(ROOT)
    except ValueError:
        display_path = output
    print(f"worklog: rendered {len(parsed)} entries to {display_path}")
    return 0


def install_hooks(args: argparse.Namespace) -> int:
    for hook_name in HOOK_NAMES:
        hook_path = ROOT / ".githooks" / hook_name
        if not hook_path.is_file() or not os.access(hook_path, os.X_OK):
            raise WorklogError(f"tracked hook is missing or not executable: {hook_path.relative_to(ROOT)}")

    configured = run_git("config", "--get", "core.hooksPath", check=False)
    desired = ".githooks"
    if configured and configured != desired and not args.force:
        raise WorklogError(
            f"core.hooksPath is already {configured!r}; refusing to replace it "
            "without --force"
        )
    run_git("config", "core.hooksPath", desired)
    print(f"worklog: configured core.hooksPath={desired}")
    return render(argparse.Namespace(output=str(DEFAULT_OUTPUT)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="create a unique worklog entry template")
    new_parser.add_argument("--title", required=True, help="human-readable entry title")
    new_parser.add_argument("--topic", help="lowercase topic slug; defaults to title")
    new_parser.add_argument("--worker", help="worker/session ID; defaults to WORKLOG_WORKER or git user.name")
    new_parser.add_argument("--status", choices=sorted(ALLOWED_STATUSES), default="completed")
    new_parser.set_defaults(func=create_entry)

    check_parser = subparsers.add_parser("check", help="validate entries and append-only discipline")
    check_parser.add_argument(
        "--allow-modified",
        action="store_true",
        help="validate entry format without rejecting edits/deletions of tracked entries",
    )
    check_parser.set_defaults(func=check_entries)

    render_parser = subparsers.add_parser("render", help="render the ignored aggregate WORKLOG.md")
    render_parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="output path (default: WORKLOG.md)")
    render_parser.set_defaults(func=render)

    hooks_parser = subparsers.add_parser("install-hooks", help="activate tracked worklog refresh hooks")
    hooks_parser.add_argument("--force", action="store_true", help="replace an existing core.hooksPath setting")
    hooks_parser.set_defaults(func=install_hooks)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except WorklogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
