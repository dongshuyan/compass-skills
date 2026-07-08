#!/usr/bin/env python3
"""Validate a handoff prompt draft for structure, length, and privacy mode."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from local_paths import contains_local_path


REQUIRED_GROUPS = {
    "workspace": ["Workspace:", "【工作目录】"],
    "goal": ["User goal:", "【用户目标】"],
    "requirements": ["Hard requirements:", "【必须遵守的要求】"],
    "completed": ["Completed:", "【已完成】"],
    "pending": ["Pending / needs verification:", "【未完成 / 待验证】"],
    "next": ["Next actions:", "【下一步】"],
}
LABELS = ["[verified]", "[inferred]", "[unverified]", "[已验证]", "[推断]", "[未验证]"]
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_style_key", re.compile(r"sk-[A-Za-z0-9_-]{16,}")),
    ("github_style_key", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer_header", re.compile(r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._~+/=-]+")),
    ("cookie_header", re.compile(r"(?i)cookie:\s*[^\n\r]+")),
]
MODE_LIMITS = {
    "minimal": (120, 1400),
    "balanced": (300, 3600),
    "full": (800, 7200),
}


def read_text(path: str | None) -> str:
    if not path or path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8", errors="replace")


def has_any(text: str, options: list[str]) -> bool:
    return any(option in text for option in options)


def validate(text: str, mode: str, privacy: str) -> dict[str, object]:
    hard: list[str] = []
    warnings: list[str] = []

    for group, options in REQUIRED_GROUPS.items():
        if not has_any(text, options):
            hard.append(f"missing_section:{group}")

    if not any(label in text for label in LABELS):
        warnings.append("missing_fact_labels")

    next_markers = ["Next actions:", "【下一步】"]
    for marker in next_markers:
        if marker in text:
            after_next = text.split(marker, 1)[1].strip()
            if len(after_next) < 12:
                hard.append("next_step_too_short")
            break

    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            hard.append(f"sensitive_pattern:{name}")

    if privacy == "shareable":
        if contains_local_path(text):
            hard.append("local_path_in_shareable_prompt")
    else:
        if contains_local_path(text):
            warnings.append("local_path_present")

    low, high = MODE_LIMITS.get(mode, MODE_LIMITS["balanced"])
    length = len(text)
    if length < low:
        warnings.append(f"short_for_mode:{length}<{low}")
    if length > high:
        warnings.append(f"long_for_mode:{length}>{high}")

    lower = text.lower()
    if "task-forest" in lower and "Task-forest state:" not in text and "【任务森林状态】" not in text:
        warnings.append("mentions_task_forest_without_section")

    return {"ok": not hard, "mode": mode, "privacy": privacy, "length": length, "hard": hard, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a session handoff prompt draft.")
    parser.add_argument("path", nargs="?", help="Draft path, or omit/use '-' for stdin.")
    parser.add_argument("--mode", choices=sorted(MODE_LIMITS), default="balanced")
    parser.add_argument("--privacy", choices=("local", "shareable"), default="local")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = validate(read_text(args.path), args.mode, args.privacy)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"ok={result['ok']} mode={result['mode']} privacy={result['privacy']} length={result['length']}")
        for item in result["hard"]:
            print(f"HARD {item}")
        for item in result["warnings"]:
            print(f"WARN {item}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
