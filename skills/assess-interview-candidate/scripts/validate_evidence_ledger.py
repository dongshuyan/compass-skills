#!/usr/bin/env python3
"""Validate candidate evidence records without converting inference into fact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REQUIRED = {
    "evidence_id",
    "competency_id",
    "claim",
    "source_kind",
    "source_ref",
    "evidence_class",
    "job_relevance",
    "extraction_confidence",
    "mapping_confidence",
    "truth_status",
    "ability_confidence",
    "alternative_explanations",
    "verification_questions",
    "scoring_eligible",
    "high_impact",
}
SOURCE_KINDS = {"resume", "public_professional", "public_social", "interview", "work_sample"}
EVIDENCE_CLASSES = {
    "externally_corroborated",
    "strong_self_report",
    "partially_specified",
    "claim_only",
    "contradicted",
    "indeterminate",
}
RELEVANCE = {"direct", "supporting", "none"}
TRUTH = {"self_report", "verified", "contradicted", "indeterminate"}
CONFIDENCE = {"low", "medium", "high"}
FORBIDDEN_KEYS = {
    "age",
    "birth_date",
    "date_of_birth",
    "gender",
    "sex",
    "marital_status",
    "pregnancy",
    "family_status",
    "religion",
    "ethnicity",
    "race",
    "health",
    "medical_status",
    "disability",
    "biometric",
    "biometrics",
    "political_affiliation",
    "sexual_orientation",
    "criminal_record",
    "credit_record",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate canonical evidence-ledger.json ({schema_version, case_id, items}), "
            "inference boundaries, and scoring eligibility. Legacy JSONL is also accepted."
        )
    )
    parser.add_argument("input", type=Path, help="Path to canonical evidence-ledger.json or compatible JSONL")
    return parser.parse_args()


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_confidence(value: Any) -> bool:
    return (isinstance(value, str) and value in CONFIDENCE) or (
        isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1
    )


def in_enum(value: Any, allowed: set[str]) -> bool:
    return isinstance(value, str) and value in allowed


def valid_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(nonempty_string(item) for item in value)


def iter_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower()
            yield from iter_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_keys(child)


def load_jsonl(path: Path) -> tuple[list[tuple[int, dict[str, Any]]], list[str], str]:
    records: list[tuple[int, dict[str, Any]]] = []
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        document = None
    if isinstance(document, dict) and "items" in document:
        if not nonempty_string(document.get("schema_version")):
            errors.append("document: schema_version must be a non-empty string")
        if not nonempty_string(document.get("case_id")):
            errors.append("document: case_id must be a non-empty string")
        raw_items = document.get("items")
        if not isinstance(raw_items, list):
            return [], errors + ["document: items must be an array"], "canonical"
        for index, value in enumerate(raw_items, 1):
            if not isinstance(value, dict):
                errors.append(f"item {index}: item must be a JSON object")
            else:
                records.append((index, value))
        if not records and not errors:
            errors.append("evidence ledger contains no items")
        return records, errors, "canonical"
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(value, dict):
                errors.append(f"line {line_number}: record must be a JSON object")
                continue
            records.append((line_number, value))
    if not records and not errors:
        errors.append("evidence ledger contains no records")
    return records, errors, "jsonl"


def validate_starov(prefix: str, starov: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(starov, dict):
        return [f"{prefix}: starov must be an object"]
    for field in ("situation", "task", "action", "result", "ownership", "verification"):
        value = starov.get(field)
        if not isinstance(value, dict):
            errors.append(f"{prefix}: starov.{field} must be an object")
            continue
        if value.get("status") not in {"explicit", "inferred", "missing"}:
            errors.append(f"{prefix}: starov.{field}.status is invalid")
        if value.get("value") is not None and not isinstance(value.get("value"), str):
            errors.append(f"{prefix}: starov.{field}.value must be string or null")
    return errors


def validate_canonical_record(line: int, record: dict[str, Any]) -> list[str]:
    prefix = f"item {line}"
    errors: list[str] = []
    required = {
        "id", "claim", "claim_type", "excerpt", "location", "capability_ids",
        "importance_tier", "evidence_status", "truth_status", "starov", "confidence",
        "alternative_explanations", "remaining_gaps", "verification_questions",
        "scoring_eligible", "evidence_origin", "high_impact", "human_confirmed",
    }
    missing = sorted(required - record.keys())
    if missing:
        return [f"{prefix}: missing required fields: {', '.join(missing)}"]
    for field in ("id", "claim", "excerpt"):
        if not nonempty_string(record.get(field)):
            errors.append(f"{prefix}: {field} must be a non-empty string")
    if not in_enum(record.get("claim_type"), {
        "achievement", "responsibility", "skill", "credential", "timeline",
        "publication", "patent", "open_source", "other",
    }):
        errors.append(f"{prefix}: invalid claim_type")
    if not in_enum(record.get("importance_tier"), {"gate", "critical", "supporting", "differentiator"}):
        errors.append(f"{prefix}: invalid importance_tier")
    if not in_enum(record.get("evidence_status"), EVIDENCE_CLASSES):
        errors.append(f"{prefix}: invalid evidence_status")
    if not in_enum(record.get("truth_status"), TRUTH):
        errors.append(f"{prefix}: invalid truth_status")
    origin = record.get("evidence_origin")
    if not in_enum(origin, SOURCE_KINDS):
        errors.append(f"{prefix}: evidence_origin must be one of {sorted(SOURCE_KINDS)}")
    for field in ("scoring_eligible", "high_impact", "human_confirmed"):
        if not isinstance(record.get(field), bool):
            errors.append(f"{prefix}: {field} must be boolean")
    location = record.get("location")
    if not isinstance(location, dict):
        errors.append(f"{prefix}: location must be an object")
    else:
        for field in ("document", "locator"):
            if not nonempty_string(location.get(field)):
                errors.append(f"{prefix}: location.{field} must be a non-empty string")
        if location.get("page") is not None and (
            not isinstance(location.get("page"), int) or isinstance(location.get("page"), bool) or location["page"] < 1
        ):
            errors.append(f"{prefix}: location.page must be null or a positive integer")
    capabilities = record.get("capability_ids")
    if not valid_string_list(capabilities) or not capabilities:
        errors.append(f"{prefix}: capability_ids must contain at least one job capability")
    for field in ("alternative_explanations", "remaining_gaps", "verification_questions"):
        if not valid_string_list(record.get(field)):
            errors.append(f"{prefix}: {field} must be an array of non-empty strings")
    source_ids = record.get("source_ids", [])
    if not valid_string_list(source_ids):
        errors.append(f"{prefix}: source_ids must be an array of non-empty strings")
        source_ids = []
    if origin in {"public_professional", "public_social"} and not source_ids:
        errors.append(f"{prefix}: public evidence requires source_ids validated through the source identity gate")
    if record.get("evidence_status") == "externally_corroborated":
        if record.get("truth_status") != "verified" or not source_ids:
            errors.append(f"{prefix}: externally_corroborated evidence requires truth_status=verified and source_ids")
    if record.get("evidence_status") == "contradicted" and record.get("truth_status") != "contradicted":
        errors.append(f"{prefix}: contradicted evidence requires truth_status=contradicted")
    confidence = record.get("confidence")
    if not isinstance(confidence, dict):
        errors.append(f"{prefix}: confidence must be an object")
    else:
        for field in ("extraction", "mapping", "ability"):
            if confidence.get(field) not in {"low", "medium", "high", "unknown"}:
                errors.append(f"{prefix}: confidence.{field} is invalid")
    errors.extend(validate_starov(prefix, record.get("starov")))
    scoring = record.get("scoring_eligible") is True
    if scoring and origin not in {"interview", "work_sample"}:
        errors.append(f"{prefix}: only interview/work_sample evidence may be scoring eligible")
    if scoring and record.get("human_confirmed") is not True:
        errors.append(f"{prefix}: scoring-eligible evidence requires human_confirmed=true")
    if origin == "public_social" and scoring:
        errors.append(f"{prefix}: public_social evidence cannot be scored")
    if record.get("truth_status") != "verified" and not record.get("verification_questions"):
        errors.append(f"{prefix}: unverified evidence requires a verification question")
    if record.get("high_impact") is True:
        alternatives = record.get("alternative_explanations")
        if not isinstance(alternatives, list) or len(alternatives) < 2:
            errors.append(f"{prefix}: high-impact evidence requires at least two alternative explanations")
        if not record.get("verification_questions"):
            errors.append(f"{prefix}: high-impact evidence requires a verification question")
    forbidden = sorted(set(iter_keys(record)) & FORBIDDEN_KEYS)
    if forbidden:
        errors.append(f"{prefix}: sensitive/job-irrelevant fields are forbidden: {', '.join(forbidden)}")
    return errors


def validate_record(line: int, record: dict[str, Any]) -> list[str]:
    prefix = f"line {line}"
    errors: list[str] = []
    missing = sorted(REQUIRED - record.keys())
    if missing:
        errors.append(f"{prefix}: missing required fields: {', '.join(missing)}")
        return errors
    for field in ("evidence_id", "competency_id", "claim", "source_ref"):
        if not nonempty_string(record[field]):
            errors.append(f"{prefix}: {field} must be a non-empty string")
    if not in_enum(record["source_kind"], SOURCE_KINDS):
        errors.append(f"{prefix}: source_kind must be one of {sorted(SOURCE_KINDS)}")
    if not in_enum(record["evidence_class"], EVIDENCE_CLASSES):
        errors.append(f"{prefix}: evidence_class must be one of {sorted(EVIDENCE_CLASSES)}")
    if not in_enum(record["job_relevance"], RELEVANCE):
        errors.append(f"{prefix}: job_relevance must be one of {sorted(RELEVANCE)}")
    if not in_enum(record["truth_status"], TRUTH):
        errors.append(f"{prefix}: truth_status must be one of {sorted(TRUTH)}")
    for field in ("extraction_confidence", "mapping_confidence", "ability_confidence"):
        if not valid_confidence(record[field]):
            errors.append(f"{prefix}: {field} must be low/medium/high or a number from 0 to 1")
    for field in ("alternative_explanations", "verification_questions"):
        if not valid_string_list(record[field]):
            errors.append(f"{prefix}: {field} must be a list of non-empty strings")
    for field in ("scoring_eligible", "high_impact"):
        if not isinstance(record[field], bool):
            errors.append(f"{prefix}: {field} must be boolean")

    source_kind = record.get("source_kind")
    scoring = record.get("scoring_eligible") is True
    if record.get("job_relevance") == "none" and scoring:
        errors.append(f"{prefix}: job-irrelevant evidence cannot be scoring eligible")
    if scoring and source_kind not in {"interview", "work_sample"}:
        errors.append(f"{prefix}: only interview or work_sample evidence may be scoring eligible")
    if scoring and record.get("human_confirmed") is not True:
        errors.append(f"{prefix}: scoring-eligible evidence requires human_confirmed=true")
    if source_kind == "public_social" and scoring:
        errors.append(f"{prefix}: public_social evidence cannot be scored")
    if source_kind in {"public_professional", "public_social"}:
        if record.get("identity_status") != "confirmed":
            errors.append(f"{prefix}: public candidate evidence requires identity_status=confirmed")
        basis = record.get("identity_basis")
        if not valid_string_list(basis) or not basis:
            errors.append(f"{prefix}: public candidate evidence requires non-empty identity_basis")
    if record.get("truth_status") != "verified" and not record.get("verification_questions"):
        errors.append(f"{prefix}: unverified evidence requires at least one verification question")
    if record.get("high_impact") is True:
        alternatives = record.get("alternative_explanations")
        if not isinstance(alternatives, list) or len(alternatives) < 2:
            errors.append(f"{prefix}: high-impact evidence requires at least two alternative explanations")
        if not record.get("verification_questions"):
            errors.append(f"{prefix}: high-impact evidence requires a verification question")
    forbidden = sorted(set(iter_keys(record)) & FORBIDDEN_KEYS)
    if forbidden:
        errors.append(f"{prefix}: sensitive/job-irrelevant fields are forbidden: {', '.join(forbidden)}")
    return errors


def main() -> int:
    args = parse_args()
    try:
        path = args.input.expanduser().resolve(strict=True)
        records, errors, mode = load_jsonl(path)
        seen: set[str] = set()
        for line, record in records:
            if mode == "canonical":
                errors.extend(validate_canonical_record(line, record))
                evidence_id = record.get("id")
            else:
                errors.extend(validate_record(line, record))
                evidence_id = record.get("evidence_id")
            if isinstance(evidence_id, str):
                if evidence_id in seen:
                    errors.append(f"line {line}: duplicate evidence_id: {evidence_id}")
                seen.add(evidence_id)
        payload = {"ok": not errors, "format": mode, "records": len(records), "errors": errors}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
