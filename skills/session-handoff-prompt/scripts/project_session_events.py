#!/usr/bin/env python3
"""Project a transcript or agent log into a bounded, redacted event stream."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from local_paths import redact_local_paths


SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "sk-<REDACTED>"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"), "gh<REDACTED>"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"), "xox-<REDACTED>"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA<REDACTED>"),
    (re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1<REDACTED>"),
    (re.compile(r"(?i)(cookie:\s*)[^\n\r]+"), r"\1<REDACTED>"),
]

def redact(text: str, redact_paths: bool) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    if redact_paths:
        text = redact_local_paths(text)
    return text


def compact(value: Any, limit: int, redact_paths: bool) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    value = redact(" ".join(value.split()), redact_paths)
    return value if len(value) <= limit else value[: max(0, limit - 1)] + "…"


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                for key in ("text", "input_text", "output_text"):
                    if isinstance(item.get(key), str):
                        parts.append(item[key])
            elif isinstance(item, str):
                parts.append(item)
    return "\n".join(parts)


def parse_codex_jsonl(path: Path, max_chars: int, redact_paths: bool) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = obj.get("type")
            if kind == "session_meta":
                payload = obj.get("payload") or {}
                events.append({
                    "line": line_no,
                    "kind": "session_meta",
                    "session_id": payload.get("id"),
                    "cwd": compact(payload.get("cwd"), max_chars, redact_paths),
                })
            elif kind == "compacted":
                payload = obj.get("payload") or {}
                message = payload.get("message")
                if isinstance(message, str) and message.strip():
                    events.append({
                        "line": line_no,
                        "kind": "compacted",
                        "text": compact(message, max_chars, redact_paths),
                    })
            elif kind == "response_item":
                item = obj.get("payload") or obj.get("item") or {}
                item_type = item.get("type")
                if item_type == "message":
                    role = item.get("role")
                    if role in {"user", "assistant"}:
                        events.append({
                            "line": line_no,
                            "kind": "message",
                            "role": role,
                            "text": compact(content_text(item.get("content")), max_chars, redact_paths),
                        })
                elif item_type == "function_call":
                    events.append({
                        "line": line_no,
                        "kind": "tool_call",
                        "name": item.get("name"),
                        "arguments": compact(item.get("arguments"), max_chars, redact_paths),
                    })
                elif item_type == "function_call_output":
                    events.append({
                        "line": line_no,
                        "kind": "tool_output",
                        "call_id": item.get("call_id"),
                        "output": compact(item.get("output"), max_chars, redact_paths),
                    })
    return events


def parse_text(path: Path, max_chars: int, redact_paths: bool) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks: list[dict[str, Any]] = []
    current_role = "note"
    current: list[str] = []
    role_pattern = re.compile(r"^\s*(user|assistant|system|tool|agent)\s*[:：]\s*(.*)$", re.IGNORECASE)

    def flush() -> None:
        nonlocal current
        if current:
            chunks.append({
                "kind": "text",
                "role": current_role,
                "text": compact("\n".join(current), max_chars, redact_paths),
            })
            current = []

    for line in text.splitlines():
        match = role_pattern.match(line)
        if match:
            flush()
            current_role = match.group(1).lower()
            rest = match.group(2)
            if rest:
                current.append(rest)
        else:
            current.append(line)
    flush()
    return chunks


def detect_format(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    return "text"
                if isinstance(obj, dict) and obj.get("type") in {"session_meta", "response_item", "compacted"}:
                    return "codex-jsonl"
                return "text"
    except OSError:
        return "text"
    return "text"


def main() -> int:
    parser = argparse.ArgumentParser(description="Project a transcript or local agent log into a bounded event stream.")
    parser.add_argument("path", help="Transcript, saved handoff, or agent log path.")
    parser.add_argument("--format", choices=("auto", "codex-jsonl", "text"), default="auto")
    parser.add_argument("--max-events", type=int, default=160)
    parser.add_argument("--max-chars", type=int, default=600)
    parser.add_argument("--privacy", choices=("local", "shareable"), default="local")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    path = Path(args.path).expanduser()
    fmt = detect_format(path) if args.format == "auto" else args.format
    redact_paths = args.privacy == "shareable"

    if fmt == "codex-jsonl":
        events = parse_codex_jsonl(path, args.max_chars, redact_paths)
    else:
        events = parse_text(path, args.max_chars, redact_paths)
    events = events[-max(1, args.max_events):]

    if args.json:
        print(json.dumps({"path": str(path), "format": fmt, "events": events}, ensure_ascii=False, indent=2))
    else:
        for event in events:
            kind = event.get("kind")
            if kind == "session_meta":
                print(f"{event.get('line', '-')}: session_meta id={event.get('session_id') or '-'} cwd={event.get('cwd') or '-'}")
            elif kind == "message":
                print(f"{event.get('line', '-')}: {event.get('role')}: {event.get('text')}")
            elif kind == "tool_call":
                print(f"{event.get('line', '-')}: tool_call {event.get('name')}: {event.get('arguments')}")
            elif kind == "tool_output":
                print(f"{event.get('line', '-')}: tool_output {event.get('call_id')}: {event.get('output')}")
            elif kind == "compacted":
                print(f"{event.get('line', '-')}: compacted: {event.get('text')}")
            else:
                print(f"- {event.get('role', 'note')}: {event.get('text')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
