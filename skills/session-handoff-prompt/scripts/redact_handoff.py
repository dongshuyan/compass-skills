#!/usr/bin/env python3
"""Redact sensitive strings from a handoff prompt draft."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from local_paths import redact_local_paths


COMMON_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "sk-<REDACTED>"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"), "gh<REDACTED>"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"), "xox-<REDACTED>"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA<REDACTED>"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "<PRIVATE_KEY_REDACTED>"),
    (re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^'\"\s]+"), r"\1=<REDACTED>"),
    (re.compile(r"(?i)(secret|client_secret)\s*[:=]\s*['\"]?[^'\"\s]+"), r"\1=<REDACTED>"),
    (re.compile(r"(?i)(access_token|auth_token|api_token)\s*[:=]\s*['\"]?[^'\"\s]+"), r"\1=<REDACTED>"),
    (re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1<REDACTED>"),
    (re.compile(r"(?i)(cookie:\s*)[^\n\r]+"), r"\1<REDACTED>"),
]

def redact(text: str, privacy: str) -> str:
    out = text
    for pattern, replacement in COMMON_PATTERNS:
        out = pattern.sub(replacement, out)
    if privacy == "shareable":
        out = redact_local_paths(out)
    return out


def read_input(path: str | None) -> str:
    if not path or path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Redact sensitive strings from a handoff prompt draft.")
    parser.add_argument("path", nargs="?", help="Draft path, or omit/use '-' for stdin.")
    parser.add_argument("--privacy", choices=("local", "shareable"), default="shareable")
    args = parser.parse_args()

    sys.stdout.write(redact(read_input(args.path), args.privacy))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
