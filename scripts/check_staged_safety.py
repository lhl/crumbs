#!/usr/bin/env python3
"""Reject staged (or, with --all, tracked) content that must never be public.

This repository is public. This check is the mechanical backstop for the
public-safety rules in AGENTS.md: no secrets, no personal data (photos,
location history, check-in exports), no credentials, and no large binaries.

It scans the Git index by default -- what is about to be committed -- not the
working tree, so another worker's unstaged files cannot block a commit.
Content patterns are deliberately high-confidence to avoid false positives;
the path and size rules carry most of the weight.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MiB
MAX_SCAN_BYTES = 1 * 1024 * 1024  # only content-scan the first 1 MiB

# Path rules: matched against the repo-relative POSIX path (lowercased for
# the suffix/name checks). Anything matching is refused outright.
FORBIDDEN_DIR_PREFIXES = (
    "data/",
    "private/",
    "photos/",
    "exports/",
    "location-history/",
    "takeout/",
)
FORBIDDEN_SUFFIXES = (
    # credentials / key material
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".keystore",
    # location-history exports (personal movement data)
    ".gpx",
    ".kml",
    ".kmz",
    # model weights and large model artifacts
    ".safetensors",
    ".gguf",
    ".onnx",
    ".pt",
    ".pth",
    ".ckpt",
)
FORBIDDEN_NAMES = {
    ".env",
    "credentials.json",
    "credentials.yaml",
    "credentials.yml",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "service-account.json",
    ".netrc",
    "id_rsa",
    "id_ed25519",
}
ALLOWED_ENV_NAMES = {".env.example", ".env.sample", ".env.template"}

# High-confidence secret patterns in text content.
SECRET_PATTERNS = (
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"), "private key block"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "GitHub fine-grained token"),
    (re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"), "API secret key (sk-...)"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "Google API key"),
    (
        re.compile(
            r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"
        ),
        "hard-coded credential assignment",
    ),
)


def git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise SystemExit(f"error: git {' '.join(args)} failed: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line]


def staged_paths() -> list[str]:
    return git_lines("diff", "--cached", "--name-only", "--diff-filter=ACMR")


def tracked_paths() -> list[str]:
    return git_lines("ls-files")


def index_blob(path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f":{path}"], cwd=ROOT, check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise SystemExit(f"error: git show :{path} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def path_violation(path: str) -> str | None:
    lower = path.lower()
    name = Path(lower).name
    if name in ALLOWED_ENV_NAMES:
        return None
    if lower.startswith(FORBIDDEN_DIR_PREFIXES):
        return "personal-data directory (keep photos/location exports out of git; see AGENTS.md)"
    if name in FORBIDDEN_NAMES or name.startswith(".env."):
        return "credential/env file"
    if lower.endswith(FORBIDDEN_SUFFIXES):
        return "forbidden file type for a public repo (key material, location export, or model weights)"
    return None


def check(paths: list[str], from_index: bool) -> list[str]:
    errors: list[str] = []
    for path in paths:
        violation = path_violation(path)
        if violation:
            errors.append(f"{path}: {violation}")
            continue
        blob = index_blob(path) if from_index else (ROOT / path).read_bytes()
        if len(blob) > MAX_FILE_BYTES:
            errors.append(f"{path}: {len(blob)} bytes exceeds the {MAX_FILE_BYTES}-byte public-repo limit")
            continue
        if b"\x00" in blob[:8192]:
            continue  # binary: path/size rules above already applied
        text = blob[:MAX_SCAN_BYTES].decode("utf-8", errors="ignore")
        for pattern, label in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                line_no = text[: match.start()].count("\n") + 1
                errors.append(f"{path}:{line_no}: possible {label} -- never commit secrets to this public repo")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="scan all tracked files instead of the staged index")
    args = parser.parse_args()

    if args.all:
        paths, from_index = tracked_paths(), False
    else:
        paths, from_index = staged_paths(), True

    errors = check(paths, from_index)
    if errors:
        print("public-safety check failed:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        print("If a flagged file is genuinely safe and public, get an explicit human "
              "decision recorded in a worklog entry before bypassing this check.", file=sys.stderr)
        return 1
    print(f"public-safety: {len(paths)} file(s) clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
