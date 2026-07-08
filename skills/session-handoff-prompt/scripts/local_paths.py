#!/usr/bin/env python3
"""Shared local-path detection helpers for session handoff scripts."""

from __future__ import annotations

import re


_PATH_BODY = r"[^\s`'\"\)\]]+"
_UNC_SEGMENT = r"[^\\/\s`'\"\)\]]+"

LOCAL_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(rf"(?<!\w)/(Users|home|Volumes|private|tmp)/{_PATH_BODY}"),
    re.compile(rf"(?<!\w)/var/folders/{_PATH_BODY}"),
    re.compile(rf"(?<!\w)/mnt/[A-Za-z]/{_PATH_BODY}"),
    re.compile(rf"(?<!\w)~/(?:\.codex|\.claude)(?:/{_PATH_BODY})?"),
    re.compile(rf"\\\\\?\\[A-Za-z]:\\{_PATH_BODY}"),
    re.compile(rf"[A-Za-z]:\\{_PATH_BODY}"),
    re.compile(rf"\\\\{_UNC_SEGMENT}(?:\\{_UNC_SEGMENT}){{1,}}"),
]


def contains_local_path(text: str) -> bool:
    return any(pattern.search(text) for pattern in LOCAL_PATH_PATTERNS)


def redact_local_paths(text: str, replacement: str = "<LOCAL_PATH>") -> str:
    for pattern in LOCAL_PATH_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
