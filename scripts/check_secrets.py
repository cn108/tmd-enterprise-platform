#!/usr/bin/env python
"""Fail the build if a secret or a forbidden file would be committed.

Scans only files tracked by git, so local scratch files do not cause noise.
Run locally with `python scripts/check_secrets.py`; CI runs the same script.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_NAMES = {".env", "db.sqlite3"}
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".dump", ".sqlite3")
ALLOWED_ENV_SUFFIXES = (".example", ".sample", ".template")

PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"), "private key block"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(r"sk_live_[0-9A-Za-z]{10,}"), "live secret key"),
    (re.compile(r"ghp_[0-9A-Za-z]{36}"), "GitHub personal access token"),
    (re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"), "Slack token"),
    (re.compile(r"postgres(?:ql)?://[^\s:/]+:[^\s@/]{4,}@"), "database URL with password"),
]

SKIP_DIRS = {".git", "node_modules", "dist", ".venv", "__pycache__", ".angular"}
MAX_BYTES = 2_000_000


def tracked_files() -> list[Path]:
    try:
        output = subprocess.run(
            ["git", "ls-files", "-z"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"check_secrets: cannot list tracked files ({exc})", file=sys.stderr)
        return []
    return [Path(name) for name in output.split("\0") if name]


def check_name(path: Path) -> str | None:
    name = path.name
    if any(part in SKIP_DIRS for part in path.parts):
        return None
    if name in FORBIDDEN_NAMES:
        return "forbidden file name (local environment or database)"
    if name.endswith(FORBIDDEN_SUFFIXES):
        return "forbidden file type (key or dump)"
    if name.startswith(".env") and not name.endswith(ALLOWED_ENV_SUFFIXES):
        return "environment file must not be committed"
    return None


def check_content(path: Path) -> list[str]:
    try:
        if path.stat().st_size > MAX_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    return [label for pattern, label in PATTERNS if pattern.search(text)]


def main() -> int:
    problems: list[str] = []
    for path in tracked_files():
        reason = check_name(path)
        if reason:
            problems.append(f"{path}: {reason}")
            continue
        for label in check_content(path):
            problems.append(f"{path}: looks like a {label}")

    if problems:
        print("Secret scan failed:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("Secret scan passed: no tracked secrets or forbidden files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
