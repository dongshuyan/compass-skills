#!/usr/bin/env python3
"""Derive a conservative display-only age range from an undergraduate timeline."""

from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
from datetime import date
from typing import Any, Iterable


PARTIAL_DATE_PATTERN = re.compile(r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$")
AGE_ASSUMPTIONS = {
    "undergraduate_start_age_min": 16,
    "undergraduate_start_age_typical": 18,
    "undergraduate_start_age_max": 20,
}
CONSISTENCY_EVENTS = {
    "undergraduate_graduation",
    "graduate_study_start",
    "employment_start",
    "other_later_event",
}


def parse_partial_date(value: str) -> tuple[date, date, str]:
    """Return earliest date, latest date, and precision for YYYY[-MM[-DD]]."""
    if not isinstance(value, str) or not PARTIAL_DATE_PATTERN.fullmatch(value):
        raise ValueError("date must be YYYY, YYYY-MM, or YYYY-MM-DD")
    parts = [int(part) for part in value.split("-")]
    year = parts[0]
    if len(parts) == 1:
        return date(year, 1, 1), date(year, 12, 31), "year"
    month = parts[1]
    if not 1 <= month <= 12:
        raise ValueError("month must be from 01 to 12")
    if len(parts) == 2:
        final_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, final_day), "month"
    day = parts[2]
    exact = date(year, month, day)
    return exact, exact, "day"


def elapsed_full_years(start: date, end: date) -> int:
    if start > end:
        raise ValueError("timeline anchor cannot be after the report date")
    return end.year - start.year - ((end.month, end.day) < (start.month, start.day))


def calculate_timeline_age_range(anchor_start: str, report_date: str) -> tuple[int, int, str]:
    """Return min age, max age, and anchor precision with date uncertainty included."""
    report = date.fromisoformat(report_date)
    earliest_start, latest_start, precision = parse_partial_date(anchor_start)
    min_elapsed = elapsed_full_years(latest_start, report)
    max_elapsed = elapsed_full_years(earliest_start, report)
    min_years = min_elapsed + AGE_ASSUMPTIONS["undergraduate_start_age_min"]
    max_years = max_elapsed + AGE_ASSUMPTIONS["undergraduate_start_age_max"]
    if min_years < 0 or max_years > 130 or min_years > max_years:
        raise ValueError("derived age range is outside the supported 0-130 year interval")
    return min_years, max_years, precision


def subtract_years(value: str, years: int) -> str:
    """Derive only a start year; graduation month/day do not prove enrollment precision."""
    if not isinstance(years, int) or isinstance(years, bool) or not 1 <= years <= 8:
        raise ValueError("degree duration must be an integer from 1 to 8 years")
    earliest, _, _ = parse_partial_date(value)
    target_year = earliest.year - years
    return f"{target_year:04d}"


def chronology_status(anchor_start: str, checks: Iterable[dict[str, Any]]) -> str:
    """Check only whether later resume events occur after undergraduate start."""
    anchor_earliest, anchor_latest, _ = parse_partial_date(anchor_start)
    saw_check = False
    saw_overlap = False
    for check in checks:
        saw_check = True
        check_earliest, check_latest, _ = parse_partial_date(check["date"])
        if check_latest < anchor_earliest:
            return "conflict"
        if check_earliest < anchor_latest:
            saw_overlap = True
    if not saw_check:
        return "not_checked"
    return "not_assessable" if saw_overlap else "consistent"


def normalize_consistency_check(check: Any) -> dict[str, str]:
    """Validate one later-event check and derive its date precision."""
    if not isinstance(check, dict):
        raise ValueError("each consistency check must be a JSON object")
    required = {"event", "date", "source_locator"}
    allowed = required | {"precision"}
    missing = sorted(required - set(check))
    extra = sorted(set(check) - allowed)
    if missing:
        raise ValueError("consistency check is missing: " + ", ".join(missing))
    if extra:
        raise ValueError("consistency check has unsupported fields: " + ", ".join(extra))
    event = check["event"]
    if event not in CONSISTENCY_EVENTS:
        raise ValueError("unsupported consistency-check event")
    _, _, precision = parse_partial_date(check["date"])
    supplied_precision = check.get("precision")
    if supplied_precision is not None and supplied_precision != precision:
        raise ValueError("consistency-check precision must match its date")
    locator = check["source_locator"]
    if not isinstance(locator, str) or not locator.strip():
        raise ValueError("consistency check needs a non-empty resume source locator")
    return {
        "event": event,
        "date": check["date"],
        "precision": precision,
        "source_locator": locator.strip(),
    }


def build_estimate(
    *,
    report_date: str,
    undergraduate_start: str | None,
    source_locators: list[str],
    undergraduate_graduation: str | None = None,
    degree_duration_years: int | None = None,
    consistency_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    checks = [normalize_consistency_check(check) for check in (consistency_checks or [])]
    if undergraduate_start is not None:
        if undergraduate_graduation is not None or degree_duration_years is not None:
            raise ValueError("provide either undergraduate start or graduation plus duration, not both")
        start = undergraduate_start
        kind = "undergraduate_start"
        graduation = None
        duration = None
    else:
        if undergraduate_graduation is None or degree_duration_years is None:
            raise ValueError("graduation-based derivation requires both graduation date and explicit degree duration")
        start = subtract_years(undergraduate_graduation, degree_duration_years)
        kind = "undergraduate_start_derived_from_graduation_and_duration"
        graduation = undergraduate_graduation
        duration = degree_duration_years
    if not source_locators or not all(isinstance(item, str) and item.strip() for item in source_locators):
        raise ValueError("at least one non-empty resume source locator is required")
    min_years, max_years, precision = calculate_timeline_age_range(start, report_date)
    consistency = chronology_status(start, checks)
    if consistency == "conflict":
        return {
            "status": "timeline_conflict",
            "display": "履历时间存在冲突，无法可靠推算年龄区间",
            "as_of": report_date,
            "min_years": None,
            "max_years": None,
            "anchor": {
                "kind": kind,
                "start": start,
                "precision": precision,
                "source_locators": source_locators,
                "graduation_date": graduation,
                "degree_duration_years": duration,
            },
            "assumptions": dict(AGE_ASSUMPTIONS),
            "consistency_status": "conflict",
            "consistency_checks": checks,
        }
    return {
        "status": "estimated",
        "display": (
            f"约{min_years}–{max_years}岁（按{start}本科入学、"
            "入学年龄18±2岁推算；非候选人自述）"
        ),
        "as_of": report_date,
        "min_years": min_years,
        "max_years": max_years,
        "anchor": {
            "kind": kind,
            "start": start,
            "precision": precision,
            "source_locators": source_locators,
            "graduation_date": graduation,
            "degree_duration_years": duration,
        },
        "assumptions": dict(AGE_ASSUMPTIONS),
        "consistency_status": consistency,
        "consistency_checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive a conservative, display-only age range from explicit undergraduate dates."
    )
    parser.add_argument("--report-date", required=True, help="Report date in YYYY-MM-DD format")
    anchor_group = parser.add_mutually_exclusive_group(required=True)
    anchor_group.add_argument("--undergraduate-start", help="Explicit undergraduate start as YYYY, YYYY-MM, or YYYY-MM-DD")
    anchor_group.add_argument("--undergraduate-graduation", help="Explicit undergraduate graduation date")
    parser.add_argument("--degree-duration-years", type=int, help="Explicit degree duration; required with graduation")
    parser.add_argument("--source-locator", action="append", required=True, help="Resume page or section; repeat if needed")
    parser.add_argument(
        "--consistency-check-json",
        action="append",
        default=[],
        help=(
            "Later-event JSON object with event, date, and source_locator; "
            "repeat as needed. Date precision is derived automatically."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        raw_checks = [json.loads(value) for value in args.consistency_check_json]
        payload = build_estimate(
            report_date=args.report_date,
            undergraduate_start=args.undergraduate_start,
            undergraduate_graduation=args.undergraduate_graduation,
            degree_duration_years=args.degree_duration_years,
            source_locators=[item.strip() for item in args.source_locator],
            consistency_checks=raw_checks,
        )
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 0
    except (TypeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
