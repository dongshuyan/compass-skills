#!/usr/bin/env python3
"""Validate the minimal interviewer-facing report payload."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from validate_case_contract import (
    audit_schema_keywords,
    load_json_strict,
    loads_strict,
    nonempty,
    validate_schema,
)


SKILL_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = SKILL_DIR / "references" / "schema-interviewer-report.json"
PRIORITY_RANK = {"must_ask": 0, "recommended": 1, "optional": 2}
PERSONAL_ASSESSMENT_TERMS = (
    "年龄",
    "出生",
    "籍贯",
    "老家",
    "婚姻",
    "已婚",
    "未婚",
    "配偶",
    "子女",
    "生育",
)
INTERNAL_VISIBLE_TERMS = (
    "reason",
    "evidence",
    "claim_only",
    "partially_specified",
    "comparability",
    "coverage",
    "gate_status",
    "cap-",
)
CONTACT_OR_IDENTITY_PATTERNS = (
    (
        "email address",
        re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])"),
    ),
    ("mobile phone number", re.compile(r"(?<!\d)(?:\+?86[\s-]?)?1[3-9]\d{9}(?!\d)")),
    ("identity number", re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")),
)


def calculate_age(normalized_birth: str, report_date: str) -> tuple[int, bool, str]:
    """Return age, whether it is approximate, and normalized precision."""
    as_of = date.fromisoformat(report_date)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized_birth):
        born = date.fromisoformat(normalized_birth)
        years = as_of.year - born.year - ((as_of.month, as_of.day) < (born.month, born.day))
        return years, False, "day"
    if re.fullmatch(r"\d{4}-\d{2}", normalized_birth):
        year, month = (int(part) for part in normalized_birth.split("-"))
        if not 1 <= month <= 12:
            raise ValueError("birth month must be from 01 to 12")
        years = as_of.year - year - (as_of.month < month)
        return years, True, "month"
    if re.fullmatch(r"\d{4}", normalized_birth):
        return as_of.year - int(normalized_birth), True, "year"
    raise ValueError("normalized_birth must be YYYY, YYYY-MM, or YYYY-MM-DD")


def _check_order(items: list[dict[str, Any]], path: str, errors: list[str]) -> None:
    orders = [item.get("order") for item in items if isinstance(item, dict)]
    if orders != list(range(1, len(items) + 1)):
        errors.append(f"{path}: order values must be consecutive from 1")


def _check_unique_ids(items: list[dict[str, Any]], path: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for index, item in enumerate(items):
        item_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(item_id, str):
            continue
        if item_id in seen:
            errors.append(f"{path}[{index}].id: duplicate id {item_id!r}")
        seen.add(item_id)


def _check_provided_field(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        return
    status = value.get("source_status")
    locator = value.get("source_locator")
    display = value.get("value")
    if status == "candidate_provided":
        if not nonempty(locator):
            errors.append(f"{path}.source_locator: candidate-provided information needs a source locator")
        if display == "未提供":
            errors.append(f"{path}.value: candidate-provided information cannot be '未提供'")
    elif status == "not_provided":
        if display != "未提供":
            errors.append(f"{path}.value: not-provided information must display '未提供'")
        if locator is not None:
            errors.append(f"{path}.source_locator: not-provided information must use null")


def _check_explicit_city(item: dict[str, Any], path: str, errors: list[str]) -> None:
    city = item.get("city")
    status = item.get("city_source_status")
    if status == "candidate_provided" and city == "未提供":
        errors.append(f"{path}.city: candidate-provided city cannot be '未提供'")
    if status == "not_provided" and city != "未提供":
        errors.append(f"{path}.city: city absent from candidate materials must display '未提供'")


def _visible_strings(data: dict[str, Any]) -> Iterable[tuple[str, str]]:
    overview = data.get("candidate_overview", {})
    for index, value in enumerate(overview.get("profile_summary", [])):
        yield f"candidate_overview.profile_summary[{index}]", value
    for index, item in enumerate(overview.get("fit_items", [])):
        for field in ("capability", "summary", "interview_focus"):
            yield f"candidate_overview.fit_items[{index}].{field}", item.get(field, "")
    location = overview.get("location_and_availability", {})
    yield "candidate_overview.location_and_availability.distance_summary", location.get("distance_summary", "")
    for index, value in enumerate(location.get("questions", [])):
        yield f"candidate_overview.location_and_availability.questions[{index}]", value
    for index, item in enumerate(data.get("resume_risks", [])):
        for field in ("capability", "resume_excerpt", "unclear_point", "why_check", "how_to_verify"):
            yield f"resume_risks[{index}].{field}", item.get(field, "")
    for index, item in enumerate(data.get("interview_questions", [])):
        for field in (
            "question",
            "purpose",
            "good_answer",
            "average_answer",
            "poor_answer",
            "recording_guidance",
        ):
            if field in item:
                yield f"interview_questions[{index}].{field}", item.get(field, "")
        for field in ("bonus_signals", "penalty_signals"):
            for item_index, value in enumerate(item.get(field, [])):
                yield f"interview_questions[{index}].{field}[{item_index}]", value
    yield "footer_note", data.get("footer_note", "")


def _all_strings(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _all_strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _all_strings(item, f"{path}[{index}]")


def validate_interviewer_report_data(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    early_questions = data.get("interview_questions")
    if isinstance(early_questions, list) and not 12 <= len(early_questions) <= 18:
        errors.append("interview_questions: question pool must contain 12 to 18 questions")
    schema = load_json_strict(SCHEMA_PATH, "interviewer report schema")
    errors.extend(audit_schema_keywords(schema))
    errors.extend(validate_schema(data, schema))
    if errors:
        return errors, warnings

    for path, value in _all_strings(data):
        for label, pattern in CONTACT_OR_IDENTITY_PATTERNS:
            if pattern.search(value):
                errors.append(f"{path}: contact or identity detail ({label}) cannot appear in interviewer data")

    case = data["case"]
    overview = data["candidate_overview"]
    personal = overview["personal_info"]
    for field in ("birth_information", "birthplace", "hometown", "marital_status", "current_city"):
        _check_provided_field(personal[field], f"candidate_overview.personal_info.{field}", errors)

    for index, item in enumerate(overview["education"]):
        _check_explicit_city(item, f"candidate_overview.education[{index}]", errors)
    for index, item in enumerate(overview["employment"]):
        _check_explicit_city(item, f"candidate_overview.employment[{index}]", errors)

    age = personal["age"]
    birth_information = personal["birth_information"]
    if age["as_of"] != case["report_date"]:
        errors.append("candidate_overview.personal_info.age.as_of must equal case.report_date")
    if birth_information["source_status"] == "not_provided":
        expected = {
            "display": "未提供",
            "years": None,
            "approximate": False,
            "normalized_birth": None,
            "precision": "not_provided",
            "source_status": "not_provided",
            "source_locator": None,
        }
        for field, expected_value in expected.items():
            if age.get(field) != expected_value:
                errors.append(f"candidate_overview.personal_info.age.{field}: must be {expected_value!r} when birth information is absent")
    else:
        if age["source_status"] != "candidate_provided" or not nonempty(age["source_locator"]):
            errors.append("candidate_overview.personal_info.age: converted age must retain candidate-provided provenance")
        if age["source_locator"] != birth_information["source_locator"]:
            errors.append(
                "candidate_overview.personal_info.age.source_locator must match birth_information.source_locator"
            )
        try:
            expected_years, expected_approximate, expected_precision = calculate_age(
                age["normalized_birth"], case["report_date"]
            )
            if age["years"] != expected_years:
                errors.append(
                    f"candidate_overview.personal_info.age.years: expected {expected_years} from normalized birth and report date"
                )
            if age["approximate"] is not expected_approximate:
                errors.append(
                    f"candidate_overview.personal_info.age.approximate: expected {expected_approximate} for {expected_precision} precision"
                )
            if age["precision"] != expected_precision:
                errors.append(
                    f"candidate_overview.personal_info.age.precision: expected {expected_precision!r}"
                )
            if expected_approximate and "约" not in age["display"]:
                errors.append("candidate_overview.personal_info.age.display: approximate age must include '约'")
            if not expected_approximate and "约" in age["display"]:
                errors.append("candidate_overview.personal_info.age.display: exact age must not include '约'")
            if str(expected_years) not in age["display"]:
                errors.append("candidate_overview.personal_info.age.display: converted years are missing")
        except (TypeError, ValueError) as exc:
            errors.append(f"candidate_overview.personal_info.age.normalized_birth: {exc}")

    fit_items = overview["fit_items"]
    _check_order(fit_items, "candidate_overview.fit_items", errors)
    for index, item in enumerate(fit_items):
        fit_text = " ".join(str(item.get(field, "")) for field in ("capability", "summary", "interview_focus"))
        for term in PERSONAL_ASSESSMENT_TERMS:
            if term in fit_text:
                errors.append(
                    f"candidate_overview.fit_items[{index}]: personal attribute term {term!r} cannot enter person-job matching"
                )

    location = overview["location_and_availability"]
    if location["company_location"] == "未提供" and location["distance_summary"] != "距离无法计算，待补充公司地址":
        errors.append(
            "candidate_overview.location_and_availability.distance_summary: missing company location requires the fixed unknown-distance message"
        )

    risks = data["resume_risks"]
    _check_order(risks, "resume_risks", errors)
    _check_unique_ids(risks, "resume_risks", errors)
    importance = [item["importance"] for item in risks]
    if importance != sorted(importance, reverse=True):
        errors.append("resume_risks: items must be sorted by importance descending")
    for index, item in enumerate(risks):
        risk_text = " ".join(
            str(item.get(field, ""))
            for field in ("capability", "resume_excerpt", "unclear_point", "why_check", "how_to_verify")
        )
        for term in PERSONAL_ASSESSMENT_TERMS:
            if term in risk_text:
                errors.append(
                    f"resume_risks[{index}]: personal attribute term {term!r} cannot be treated as a resume risk"
                )

    questions = data["interview_questions"]
    if not 12 <= len(questions) <= 18:
        errors.append("interview_questions: question pool must contain 12 to 18 questions")
    _check_order(questions, "interview_questions", errors)
    _check_unique_ids(questions, "interview_questions", errors)
    priority_ranks = [PRIORITY_RANK[item["priority"]] for item in questions]
    if priority_ranks != sorted(priority_ranks):
        errors.append("interview_questions: questions must be sorted by priority")
    required_kinds = {
        "job_core",
        "work_sample",
        "resume_check",
        "soft_skill",
        "logistics",
        "candidate_choice",
    }
    present_kinds = {item["kind"] for item in questions}
    for missing_kind in sorted(required_kinds - present_kinds):
        errors.append(f"interview_questions: include at least one {missing_kind} question")

    marriage_question_found = False
    for index, question in enumerate(questions):
        path = f"interview_questions[{index}]"
        if question["kind"] in {"logistics", "candidate_choice"} and question["evaluation_mode"] != "record_only":
            errors.append(f"{path}: {question['kind']} questions must be record-only")
        if question["kind"] == "work_sample" and question["evaluation_mode"] != "rated":
            errors.append(f"{path}: work_sample questions must use rated evaluation")
        if question["evaluation_mode"] == "rated":
            required = ("good_answer", "average_answer", "poor_answer", "bonus_signals", "penalty_signals")
            missing = [field for field in required if field not in question]
            if missing:
                errors.append(f"{path}: rated question missing {', '.join(missing)}")
            if "recording_guidance" in question:
                errors.append(f"{path}: rated question must not use recording_guidance")
            rated_text = " ".join(
                str(question.get(field, ""))
                for field in ("question", "purpose", "good_answer", "average_answer", "poor_answer")
            )
            rated_text += " " + " ".join(question.get("bonus_signals", []))
            rated_text += " " + " ".join(question.get("penalty_signals", []))
            for term in PERSONAL_ASSESSMENT_TERMS:
                if term in rated_text:
                    errors.append(
                        f"{path}: personal attribute term {term!r} cannot enter a rated question or rating signal"
                    )
        else:
            if not nonempty(question.get("recording_guidance")):
                errors.append(f"{path}: record-only question needs recording_guidance")
            forbidden = ("good_answer", "average_answer", "poor_answer", "bonus_signals", "penalty_signals")
            present = [field for field in forbidden if field in question]
            if present:
                errors.append(f"{path}: record-only question must not contain rating fields: {', '.join(present)}")
        if (
            question["kind"] == "candidate_choice"
            and question["evaluation_mode"] == "record_only"
            and "婚姻" in question["question"]
        ):
            marriage_question_found = True
    if not marriage_question_found:
        errors.append("interview_questions: include a record-only, candidate-choice marital-status question")

    for path, value in _visible_strings(data):
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        for term in INTERNAL_VISIBLE_TERMS:
            if term in lowered:
                errors.append(f"{path}: internal term {term!r} must not appear in interviewer-facing text")

    return errors, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate simplified interviewer-report-data JSON.")
    parser.add_argument("data", type=Path, help="Path to interviewer-report-data.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        value = loads_strict(args.data.expanduser().read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("interviewer report data must contain a JSON object")
        errors, warnings = validate_interviewer_report_data(value)
        payload = {
            "ok": not errors,
            "data": str(args.data.expanduser().resolve()),
            "errors": errors,
            "warnings": warnings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
