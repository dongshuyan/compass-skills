#!/usr/bin/env python3
"""Validate the canonical auditable source ledger, with legacy JSONL support."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


REQUIRED = {
    "source_id",
    "url",
    "title",
    "publisher",
    "source_tier",
    "source_type",
    "purpose",
    "accessed_at",
    "accepted",
    "decision_reason",
    "job_relevance",
    "identity_status",
    "source_origin",
    "identity_basis",
    "sensitive_data_present",
}
TIERS = {"A", "B", "C", "D"}
SOURCE_TYPES = {
    "government",
    "standard",
    "peer_reviewed",
    "official_employer",
    "official_professional",
    "paper",
    "patent",
    "open_source",
    "official_technical",
    "market",
    "social_media",
    "other",
}
PURPOSES = {"role_research", "candidate_professional", "candidate_social", "methods"}
RELEVANCE = {"direct", "supporting", "none"}
IDENTITY = {"not_required", "confirmed", "unresolved", "rejected"}
ORIGINS = {"provided", "discovered", "not_applicable"}
CANONICAL_PURPOSES = {"role_current", "candidate_professional", "candidate_social", "methods", "legal_compliance"}
CANONICAL_TIERS = {"A", "B", "C", "D", "excluded"}
CANONICAL_TYPES = {
    "government",
    "standard",
    "peer_reviewed",
    "official_employer",
    "official_professional",
    "official_technical",
    "patent",
    "open_source",
    "public_social",
    "market_report",
    "local_document",
    "other",
}
CANONICAL_STATUS = {"accepted", "rejected", "identity_unresolved", "superseded"}
CANONICAL_IDENTITY = {"not_applicable", "confirmed", "unresolved", "conflict"}
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
NUMERIC_SCORE_KEYS = {"score", "numeric_score", "personality_score", "culture_fit_score", "social_score"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate canonical sources.json ({schema_version, case_id, records}) and its "
            "identity/privacy gates. Legacy one-object-per-line JSONL is also accepted."
        )
    )
    parser.add_argument("input", type=Path, help="Path to canonical sources.json or compatible JSONL")
    return parser.parse_args()


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def in_enum(value: Any, allowed: set[str]) -> bool:
    return isinstance(value, str) and value in allowed


def parse_iso8601(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


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
    if isinstance(document, dict) and "records" in document:
        if not nonempty_string(document.get("schema_version")):
            errors.append("document: schema_version must be a non-empty string")
        if not nonempty_string(document.get("case_id")):
            errors.append("document: case_id must be a non-empty string")
        raw_records = document.get("records")
        if not isinstance(raw_records, list):
            return [], errors + ["document: records must be an array"], "canonical"
        for index, value in enumerate(raw_records, 1):
            if not isinstance(value, dict):
                errors.append(f"record {index}: record must be a JSON object")
            else:
                records.append((index, value))
        if not records and not errors:
            errors.append("source ledger contains no records")
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
        errors.append("source ledger contains no records")
    return records, errors, "jsonl"


def validate_canonical_record(line: int, record: dict[str, Any]) -> list[str]:
    prefix = f"record {line}"
    errors: list[str] = []
    required = {
        "id", "research_purpose", "query", "title", "url", "publisher", "source_tier",
        "source_type", "accessed_at", "jurisdiction", "status", "direct_support",
        "adopted_claims", "rejected_claims", "identity", "volatility", "scoring_eligible",
        "origin", "query_redacted", "social_search_authorized", "sensitive_data_present",
        "accepted", "job_relevance", "capability_ids", "sensitive_content_retained", "exclusion_code",
    }
    missing = sorted(required - record.keys())
    if missing:
        return [f"{prefix}: missing required fields: {', '.join(missing)}"]
    for field in ("id", "title", "url", "publisher", "accessed_at", "jurisdiction", "direct_support"):
        if not nonempty_string(record.get(field)):
            errors.append(f"{prefix}: {field} must be a non-empty string")
    if nonempty_string(record.get("url")):
        parsed = urlparse(record["url"])
        allowed_schemes = {"file"} if record.get("source_type") == "local_document" else {"http", "https"}
        if parsed.scheme not in allowed_schemes or (parsed.scheme in {"http", "https"} and not parsed.netloc):
            errors.append(f"{prefix}: url scheme does not match source_type")
    if not in_enum(record.get("research_purpose"), CANONICAL_PURPOSES):
        errors.append(f"{prefix}: invalid research_purpose")
    if not in_enum(record.get("source_tier"), CANONICAL_TIERS):
        errors.append(f"{prefix}: invalid source_tier")
    if not in_enum(record.get("source_type"), CANONICAL_TYPES):
        errors.append(f"{prefix}: invalid source_type")
    if not in_enum(record.get("status"), CANONICAL_STATUS):
        errors.append(f"{prefix}: invalid status")
    if not in_enum(record.get("volatility"), {"low", "medium", "high"}):
        errors.append(f"{prefix}: volatility must be low, medium, or high")
    if not in_enum(record.get("job_relevance"), {"direct", "supporting", "none"}):
        errors.append(f"{prefix}: job_relevance must be direct, supporting, or none")
    capability_ids = record.get("capability_ids")
    if not valid_nonempty_string_list(capability_ids, allow_empty=True):
        errors.append(f"{prefix}: capability_ids must be an array of non-empty strings")
        capability_ids = []
    if not isinstance(record.get("scoring_eligible"), bool):
        errors.append(f"{prefix}: scoring_eligible must be boolean")
    if not isinstance(record.get("accepted"), bool):
        errors.append(f"{prefix}: accepted must be boolean")
    elif (record.get("status") == "accepted") != record.get("accepted"):
        errors.append(f"{prefix}: accepted must be true exactly when status=accepted")
    if record.get("sensitive_content_retained") is not False:
        errors.append(f"{prefix}: sensitive_content_retained must be false")
    if record.get("exclusion_code") not in {
        None, "excluded_by_policy", "identity_unresolved", "low_quality", "stale", "irrelevant", "duplicate", "other"
    }:
        errors.append(f"{prefix}: invalid exclusion_code")
    if record.get("accepted") is True and record.get("exclusion_code") is not None:
        errors.append(f"{prefix}: accepted source must use exclusion_code=null")
    if record.get("origin") not in {"provided", "discovered", "not_applicable"}:
        errors.append(f"{prefix}: origin must be provided, discovered, or not_applicable")
    if not isinstance(record.get("query_redacted"), bool):
        errors.append(f"{prefix}: query_redacted must be boolean")
    if not isinstance(record.get("social_search_authorized"), bool):
        errors.append(f"{prefix}: social_search_authorized must be boolean")
    for field in ("adopted_claims", "rejected_claims"):
        if not valid_nonempty_string_list(record.get(field), allow_empty=True):
            errors.append(f"{prefix}: {field} must be an array of non-empty strings")
    if not parse_iso8601(record.get("accessed_at", "")):
        errors.append(f"{prefix}: accessed_at must be ISO-8601")
    for field in ("published_at", "updated_at", "refresh_after"):
        value = record.get(field)
        if value is not None and (not nonempty_string(value) or not parse_iso8601(value)):
            errors.append(f"{prefix}: {field} must be null or ISO-8601")
    if in_enum(record.get("status"), {"rejected", "identity_unresolved"}):
        if not nonempty_string(record.get("rejection_reason")):
            errors.append(f"{prefix}: rejected/unresolved sources require rejection_reason")
        if record.get("scoring_eligible") is not False:
            errors.append(f"{prefix}: rejected/unresolved sources must set scoring_eligible=false")

    identity = record.get("identity")
    if not isinstance(identity, dict):
        errors.append(f"{prefix}: identity must be an object")
        identity = {}
    for field in ("required", "status", "matching_anchors"):
        if field not in identity:
            errors.append(f"{prefix}: identity.{field} is required")
    if not isinstance(identity.get("required"), bool):
        errors.append(f"{prefix}: identity.required must be boolean")
    if not in_enum(identity.get("status"), CANONICAL_IDENTITY):
        errors.append(f"{prefix}: invalid identity.status")
    anchors = identity.get("matching_anchors")
    if not valid_nonempty_string_list(anchors, allow_empty=True):
        errors.append(f"{prefix}: identity.matching_anchors must be an array of non-empty strings")
        anchors = []
    candidate_source = record.get("research_purpose") in {"candidate_professional", "candidate_social"}
    if record.get("accepted") is True and record.get("research_purpose") in {
        "role_current", "candidate_professional", "candidate_social"
    }:
        if record.get("job_relevance") not in {"direct", "supporting"}:
            errors.append(f"{prefix}: accepted role/candidate source must be job-relevant")
        if not capability_ids:
            errors.append(f"{prefix}: accepted role/candidate source requires at least one capability_id")
    if record.get("job_relevance") == "none" and capability_ids:
        errors.append(f"{prefix}: job-irrelevant source must not reference capabilities")
    if candidate_source:
        if identity.get("required") is not True:
            errors.append(f"{prefix}: candidate source requires identity.required=true")
        if record.get("query_redacted") is not True:
            errors.append(f"{prefix}: candidate source must set query_redacted=true")
        if record.get("status") == "accepted" and identity.get("status") != "confirmed":
            errors.append(f"{prefix}: accepted candidate source requires confirmed identity")
        required_anchors = 2 if record.get("origin") == "discovered" else 1
        if record.get("status") == "accepted" and len(anchors) < required_anchors:
            errors.append(f"{prefix}: accepted candidate source needs at least {required_anchors} identity anchor(s)")
        if record.get("origin") not in {"provided", "discovered"}:
            errors.append(f"{prefix}: candidate source origin must be provided or discovered")
        if record.get("origin") == "discovered":
            if not nonempty_string(record.get("query")):
                errors.append(f"{prefix}: discovered candidate source requires a logged query")
            if record.get("query_redacted") is not True:
                errors.append(f"{prefix}: discovered candidate query must set query_redacted=true")
        elif record.get("origin") == "provided" and record.get("query") is not None:
            errors.append(f"{prefix}: provided candidate URL must use query=null")
    else:
        if identity.get("required") is not False or identity.get("status") != "not_applicable":
            errors.append(f"{prefix}: non-candidate source identity must be not applicable")
        if record.get("origin") != "not_applicable":
            errors.append(f"{prefix}: non-candidate source origin must be not_applicable")
    social_source = record.get("source_type") == "public_social" or record.get("research_purpose") == "candidate_social"
    if social_source:
        if record.get("source_type") != "public_social" or record.get("research_purpose") != "candidate_social":
            errors.append(f"{prefix}: public social sources require research_purpose=candidate_social and source_type=public_social")
        if record.get("scoring_eligible") is not False:
            errors.append(f"{prefix}: social sources must set scoring_eligible=false")
        if record.get("social_search_authorized") is not True:
            errors.append(f"{prefix}: social sources require social_search_authorized=true")
        if identity.get("status") != "confirmed":
            errors.append(f"{prefix}: social sources require confirmed identity")
    elif record.get("social_search_authorized") is not False:
        errors.append(f"{prefix}: non-social sources must set social_search_authorized=false")
    if record.get("source_tier") == "excluded" and record.get("scoring_eligible") is not False:
        errors.append(f"{prefix}: excluded sources must set scoring_eligible=false")
    sensitive_encountered = record.get("sensitive_data_present")
    if not isinstance(sensitive_encountered, bool):
        errors.append(f"{prefix}: sensitive-data encounter flag must be boolean")
    elif sensitive_encountered:
        if record.get("status") == "accepted":
            errors.append(f"{prefix}: accepted records cannot contain sensitive data")
        if record.get("status") != "rejected" or record.get("source_tier") != "excluded":
            errors.append(f"{prefix}: sensitive encounters must be rejected with source_tier=excluded")
        if record.get("exclusion_code") != "excluded_by_policy":
            errors.append(f"{prefix}: sensitive encounters require exclusion_code=excluded_by_policy")
    forbidden = sorted(set(iter_keys(record)) & FORBIDDEN_KEYS)
    if forbidden:
        errors.append(f"{prefix}: sensitive/job-irrelevant fields are forbidden: {', '.join(forbidden)}")
    if social_source:
        numeric = sorted(set(iter_keys(record)) & NUMERIC_SCORE_KEYS)
        if numeric:
            errors.append(f"{prefix}: social sources cannot contain numeric score fields: {', '.join(numeric)}")
    return errors


def valid_nonempty_string_list(value: Any, allow_empty: bool = False) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(nonempty_string(item) for item in value)


def validate_record(line: int, record: dict[str, Any]) -> list[str]:
    prefix = f"line {line}"
    errors: list[str] = []
    missing = sorted(REQUIRED - record.keys())
    if missing:
        errors.append(f"{prefix}: missing required fields: {', '.join(missing)}")
        return errors
    for field in ("source_id", "url", "title", "publisher", "decision_reason", "accessed_at"):
        if not nonempty_string(record[field]):
            errors.append(f"{prefix}: {field} must be a non-empty string")
    if nonempty_string(record["url"]):
        parsed = urlparse(record["url"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{prefix}: url must be an absolute http(s) URL")
    if not in_enum(record["source_tier"], TIERS):
        errors.append(f"{prefix}: source_tier must be one of {sorted(TIERS)}")
    if not in_enum(record["source_type"], SOURCE_TYPES):
        errors.append(f"{prefix}: source_type must be one of {sorted(SOURCE_TYPES)}")
    if not in_enum(record["purpose"], PURPOSES):
        errors.append(f"{prefix}: purpose must be one of {sorted(PURPOSES)}")
    if not in_enum(record["job_relevance"], RELEVANCE):
        errors.append(f"{prefix}: job_relevance must be one of {sorted(RELEVANCE)}")
    if not in_enum(record["identity_status"], IDENTITY):
        errors.append(f"{prefix}: identity_status must be one of {sorted(IDENTITY)}")
    if not in_enum(record["source_origin"], ORIGINS):
        errors.append(f"{prefix}: source_origin must be one of {sorted(ORIGINS)}")
    if not isinstance(record["accepted"], bool):
        errors.append(f"{prefix}: accepted must be boolean")
    if not isinstance(record["sensitive_data_present"], bool):
        errors.append(f"{prefix}: sensitive_data_present must be boolean")
    elif record["sensitive_data_present"]:
        if record.get("accepted") is True:
            errors.append(f"{prefix}: accepted records cannot contain sensitive data")
        if record.get("exclusion_code") != "excluded_by_policy":
            errors.append(f"{prefix}: excluded sensitive encounters require exclusion_code=excluded_by_policy")
    if not isinstance(record["identity_basis"], list) or not all(nonempty_string(x) for x in record["identity_basis"]):
        errors.append(f"{prefix}: identity_basis must be a list of non-empty strings")
    if nonempty_string(record["accessed_at"]) and not parse_iso8601(record["accessed_at"]):
        errors.append(f"{prefix}: accessed_at must be ISO-8601")
    if "published_at" in record and record["published_at"] is not None:
        if not nonempty_string(record["published_at"]) or not parse_iso8601(record["published_at"]):
            errors.append(f"{prefix}: published_at must be null or ISO-8601")

    accepted = record.get("accepted") is True
    purpose = record.get("purpose")
    if accepted and record.get("job_relevance") == "none":
        errors.append(f"{prefix}: accepted sources must be directly or supportingly job-relevant")
    if accepted and record.get("source_tier") == "D" and record.get("supports_key_conclusion") is not False:
        errors.append(f"{prefix}: tier D sources must set supports_key_conclusion=false")

    if purpose in {"candidate_professional", "candidate_social"} and accepted:
        if record.get("identity_status") != "confirmed":
            errors.append(f"{prefix}: accepted candidate sources require identity_status=confirmed")
        basis = record.get("identity_basis") if isinstance(record.get("identity_basis"), list) else []
        required_basis = 2 if record.get("source_origin") == "discovered" else 1
        if len(basis) < required_basis:
            errors.append(f"{prefix}: candidate source needs at least {required_basis} identity basis item(s)")
    elif purpose in {"role_research", "methods"}:
        if record.get("identity_status") != "not_required" or record.get("source_origin") != "not_applicable":
            errors.append(f"{prefix}: non-candidate research must use identity_status=not_required and source_origin=not_applicable")

    keys = set(iter_keys(record))
    forbidden = sorted(keys & FORBIDDEN_KEYS)
    if forbidden:
        errors.append(f"{prefix}: sensitive/job-irrelevant fields are forbidden: {', '.join(forbidden)}")
    if purpose == "candidate_social":
        if record.get("social_search_authorized") is not True:
            errors.append(f"{prefix}: candidate_social requires social_search_authorized=true")
        if record.get("scoring_eligible") is not False:
            errors.append(f"{prefix}: candidate_social must set scoring_eligible=false")
        numeric = sorted(keys & NUMERIC_SCORE_KEYS)
        if numeric:
            errors.append(f"{prefix}: social sources cannot contain numeric score fields: {', '.join(numeric)}")
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
                source_id = record.get("id")
            else:
                errors.extend(validate_record(line, record))
                source_id = record.get("source_id")
            if isinstance(source_id, str):
                if source_id in seen:
                    errors.append(f"line {line}: duplicate source_id: {source_id}")
                seen.add(source_id)
        payload = {"ok": not errors, "format": mode, "records": len(records), "errors": errors}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    except (OSError, ValueError) as exc:
        return fail_io(str(exc))


def fail_io(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
