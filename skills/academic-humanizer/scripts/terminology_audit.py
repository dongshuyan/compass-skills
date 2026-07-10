#!/usr/bin/env python3
"""Report declared terminology variants without inferring or rewriting meaning."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PROTECTED_PATTERNS = (
    re.compile(r"```.*?```", re.DOTALL),
    re.compile(r"`[^`\n]+`"),
    re.compile(r'"(?:[^"\\]|\\.)*"'),
    re.compile(r"“[^”]*”"),
    re.compile(r"‘[^’]*’"),
    re.compile(r"\$\$.*?\$\$", re.DOTALL),
    re.compile(r"\$[^$\n]+\$"),
)


def _protected_intervals(text: str) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    for pattern in PROTECTED_PATTERNS:
        intervals.extend((match.start(), match.end()) for match in pattern.finditer(text))
    return sorted(intervals)


def _is_protected(start: int, end: int, intervals: list[tuple[int, int]]) -> bool:
    return any(start < protected_end and end > protected_start for protected_start, protected_end in intervals)


def _term_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term)
    has_cjk = bool(re.search(r"[\u3400-\u9fff]", term))
    prefix = r"(?<!\w)" if not has_cjk and term and (term[0].isalnum() or term[0] == "_") else ""
    suffix = r"(?!\w)" if not has_cjk and term and (term[-1].isalnum() or term[-1] == "_") else ""
    return re.compile(prefix + escaped + suffix, re.IGNORECASE)


def validate_ledger(ledger: list[dict[str, Any]]) -> None:
    required = {"concept_id", "canonical_term", "allowed_forms", "observed_variants", "distinguish_from"}
    concept_ids: set[str] = set()
    for index, item in enumerate(ledger):
        missing = required - set(item)
        if missing:
            raise ValueError(f"term {index} is missing fields: {', '.join(sorted(missing))}")
        if not isinstance(item["concept_id"], str) or not item["concept_id"].strip():
            raise ValueError(f"term {index} has an invalid concept_id")
        if item["concept_id"] in concept_ids:
            raise ValueError(f"duplicate concept_id: {item['concept_id']}")
        concept_ids.add(item["concept_id"])
        if not isinstance(item["canonical_term"], str) or not item["canonical_term"].strip():
            raise ValueError(f"{item['concept_id']} has an invalid canonical_term")
        for field in ("allowed_forms", "observed_variants", "distinguish_from"):
            if not isinstance(item[field], list) or not all(isinstance(value, str) for value in item[field]):
                raise ValueError(f"{item['concept_id']}.{field} must be a list of strings")


def audit_text(text: str, ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return observed-variant findings outside common protected spans.

    The caller supplies all identity judgments in ``ledger``. This function only
    locates declared variants; it never treats lexical similarity as coreference.
    """

    validate_ledger(ledger)
    protected = _protected_intervals(text)
    findings: list[dict[str, Any]] = []
    for item in ledger:
        authorized = {item["canonical_term"].casefold()}
        authorized.update(form.casefold() for form in item["allowed_forms"])
        for variant in item["observed_variants"]:
            if not variant.strip() or variant.casefold() in authorized:
                continue
            for match in _term_pattern(variant).finditer(text):
                if _is_protected(match.start(), match.end(), protected):
                    continue
                findings.append(
                    {
                        "concept_id": item["concept_id"],
                        "canonical_term": item["canonical_term"],
                        "variant": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                        "action": "review",
                    }
                )
    return sorted(findings, key=lambda finding: (finding["start"], finding["concept_id"]))


def _load_ledger(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    ledger = payload.get("terms") if isinstance(payload, dict) else payload
    if not isinstance(ledger, list):
        raise ValueError("ledger must be a JSON list or an object with a 'terms' list")
    return ledger


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report explicitly declared terminology variants without rewriting the manuscript."
    )
    parser.add_argument("text", type=Path, help="UTF-8 manuscript text file")
    parser.add_argument("--ledger", required=True, type=Path, help="JSON terminology ledger")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        text = args.text.read_text(encoding="utf-8")
        ledger = _load_ledger(args.ledger)
        findings = audit_text(text, ledger)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"terminology audit error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"finding_count": len(findings), "findings": findings}, ensure_ascii=False, indent=2))
    elif findings:
        for finding in findings:
            print(
                f"{finding['concept_id']}: {finding['variant']!r} -> "
                f"review against {finding['canonical_term']!r} at {finding['start']}:{finding['end']}"
            )
    else:
        print("No declared terminology variants found.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
