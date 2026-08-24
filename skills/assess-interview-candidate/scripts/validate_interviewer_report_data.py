#!/usr/bin/env python3
"""Validate the minimal interviewer-facing report payload."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
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
from derive_timeline_age import (
    AGE_ASSUMPTIONS,
    calculate_timeline_age_range,
    chronology_status,
    parse_partial_date,
    subtract_years,
)
from prepare_candidate_photo import (
    PHOTO_MAX_BYTES,
    PHOTO_MAX_DATA_URI_CHARS,
    PHOTO_MAX_DIMENSION,
    PHOTO_MIN_DIMENSION,
    detect_mime,
    sanitize_image,
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
PERSONAL_ASSESSMENT_PATTERNS = tuple(
    (term, re.compile(re.escape(term), re.IGNORECASE)) for term in PERSONAL_ASSESSMENT_TERMS
) + (
    (
        "岁",
        re.compile(
            r"(?:\d{1,3}|[零〇一二两三四五六七八九十百]{1,4})\s*"
            r"(?:(?:[–—~～\-至到]|to)\s*(?:\d{1,3}|[零〇一二两三四五六七八九十百]{1,4})\s*)?周?岁",
            re.IGNORECASE,
        ),
    ),
    ("年轻", re.compile(r"年轻|年长|年少|高龄|低龄|大龄|岁数|年纪.{0,4}(?:轻|小|大|长)")),
    (
        "照片",
        re.compile(r"照片|头像"),
    ),
    (
        "photo",
        re.compile(r"\b(?:photo|portrait|headshot)\b", re.IGNORECASE),
    ),
    (
        "年龄",
        re.compile(
            r"未满\s*(?:\d{1,3}|[零〇一二两三四五六七八九十百]{1,4})\s*(?:周?岁)?\s*(?:者|人员|候选人|求职者|申请人)?"
            r"|(?:\d{1,3}|[零〇一二两三四五六七八九十百]{1,4})\s*(?:周?岁)?\s*(?:以下|以内|以上)\s*(?:者|人员|候选人|求职者|申请人)",
        ),
    ),
    ("年龄段", re.compile(r"(?<!\d)(?:[5-9]\d|0\d)后")),
    (
        "age",
        re.compile(
            r"\b(?:age|aged|ages)\b"
            r"|(?<!\d)\d{1,3}\s*(?:[-–—]|to)\s*\d{1,3}\s*(?:years?\s*old|y/?o)\b"
            r"|\b(?:younger|youngest|older|oldest|elderly)\s+(?:candidates?|applicants?|people|persons?|employees?|engineers?|developers?)\b"
            r"|\b(?:candidates?|applicants?|people|persons?|employees?|engineers?|developers?)\b.{0,24}\b(?:younger|older)\s+than\s+\d{1,3}\b"
            r"|\b(?:candidates?|applicants?|people|persons?|employees?|engineers?|developers?)\b.{0,24}\b(?:under|over|below|above)[-\s]+\d{1,3}\b"
            r"|\b(?:under|over|below|above)[-\s]+\d{1,3}\s+(?:candidates?|applicants?|people|persons?|employees?|engineers?|developers?)\b",
            re.IGNORECASE,
        ),
    ),
)
PERSON_APPEARANCE_PATTERNS = (
    (
        "照片",
        re.compile(
            r"外貌|颜值|长相|容貌|五官"
            r"|(?:候选人|求职者|申请人|应聘者)(?:本人)?的?"
            r"(?:外貌|颜值|长相|容貌|五官|外形|个人形象)"
            r"|(?:候选人|求职者|申请人|应聘者)(?:很|较|更)?(?:好看|漂亮|帅气)"
            r"|(?:他|她|其本人)(?:很|较|更|看起来|显得)?(?:好看|漂亮|帅气)"
            r"|(?:外形出众|外貌出众|长相好看|容貌出众|好看|漂亮|帅气)(?:的)?"
            r"(?:候选人|求职者|申请人|应聘者|人|者)",
        ),
    ),
    (
        "photo",
        re.compile(
            r"\bgood\s+looks\b|\bphysical\s+appearance\b"
            r"|\b(?:candidate|applicant|person|individual|employee|engineer|developer)(?:s|'s|s')?\s+"
            r"(?:physical\s+)?(?:appearance|look|looks)\b"
            r"|\b(?:candidates?|applicants?|people|persons?|individuals?|employees?|engineers?|developers?)\s+"
            r"(?:has|have|with)\s+(?:an?\s+)?(?:professional\s+|physical\s+|personal\s+)?"
            r"(?:appearance|look|looks)\b"
            r"|\b(?:attractive|good[- ]looking|youthful|young-looking)\s+"
            r"(?:candidates?|applicants?|people|persons?|individuals?|employees?|engineers?|developers?)\b"
            r"|\b(?:candidates?|applicants?|people|persons?|individuals?|employees?|engineers?|developers?)\s+"
            r"(?:look|looks|are|is|seem|seems)\s+(?:attractive|good[- ]looking|youthful|young-looking)\b"
            r"|\b(?:he|she|they)\s+(?:is|are|look|looks|seem|seems)\s+"
            r"(?:attractive|good[- ]looking|youthful|young-looking|beautiful|handsome)\b"
            r"|\b(?:their|his|her)\s+(?:appearance|look|looks)\b",
            re.IGNORECASE,
        ),
    ),
)
GENERIC_APPEARANCE_PATTERNS = (
    (
        "照片",
        re.compile(r"外形|(?:个人|职业)形象|形象(?:专业|好|出众|适配)|好看|漂亮|帅气"),
    ),
    (
        "photo",
        re.compile(
            r"\b(?:appearance|look|good[- ]looking|youthful|young-looking)\b",
            re.IGNORECASE,
        ),
    ),
)
ARTIFACT_ATTACHED_APPEARANCE_PATTERNS = (
    re.compile(
        r"(?:界面|页面|仪表盘|网站|应用|产品|设计|布局|视觉|组件|表单|图表|代码|架构|服务|系统|实现|交互|前端|品牌)"
        r"(?:的|很|较|更|看起来|显得|呈现|呈现出|具有|拥有)?\s*"
        r"(?:专业|清晰|简洁|美观|漂亮|好看|出众|一致)?\s*(?:外形|形象|好看|漂亮)"
    ),
    re.compile(
        r"\b(?:ui|ux|dashboard|interface|page|screen|website|web|app|application|product|design|layout|visual|component|form|chart|code|architecture|service|system|implementation|solution|api|css|html)\b"
        r"(?:'s|\s+(?:has|have|with|shows|uses|keeps|offers|presents|features|maintains|displays|provides))?\s+"
        r"(?:an?\s+)?(?:professional\s+|polished\s+|consistent\s+|clear\s+|clean\s+|attractive\s+)?"
        r"(?:appearance|look)\b",
        re.IGNORECASE,
    ),
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
PHOTO_DATA_URI_PATTERN = re.compile(r"^data:(image/png);base64,([A-Za-z0-9+/]+={0,2})$")


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


def _personal_assessment_signal(value: str) -> str | None:
    for label, pattern in PERSONAL_ASSESSMENT_PATTERNS:
        if pattern.search(value):
            return label
    for segment in re.split(r"[.!?。！？;；,，\n]+|\b(?:and|but|while)\b|(?:并且|但是|但|而)", value, flags=re.IGNORECASE):
        if not segment.strip():
            continue
        for label, pattern in PERSON_APPEARANCE_PATTERNS:
            if pattern.search(segment):
                return label
        for label, pattern in GENERIC_APPEARANCE_PATTERNS:
            if pattern.search(segment):
                if any(artifact_pattern.search(segment) for artifact_pattern in ARTIFACT_ATTACHED_APPEARANCE_PATTERNS):
                    continue
                return label
    return None


def _check_candidate_photo(photo: dict[str, Any], path: str, errors: list[str]) -> None:
    status = photo.get("status")
    payload_fields = (
        "data_uri",
        "mime_type",
        "byte_length",
        "pixel_width",
        "pixel_height",
        "sha256",
    )
    provenance = photo.get("provenance")
    if status == "not_present":
        if any(photo.get(field) is not None for field in payload_fields) or provenance is not None:
            errors.append(f"{path}: not-present photo must not contain image data or provenance")
        return
    if status in {"ambiguous", "extraction_unavailable"}:
        if any(photo.get(field) is not None for field in payload_fields):
            errors.append(f"{path}: non-included photo status must not contain image data")
        if not isinstance(provenance, dict):
            errors.append(f"{path}.provenance: {status} needs the resume PDF page that was reviewed")
        elif (
            provenance.get("extraction_method") != "not_completed"
            or provenance.get("image_index") is not None
            or provenance.get("crop_box") is not None
        ):
            errors.append(f"{path}.provenance: {status} must use not_completed without an image locator")
        return
    if status != "included":
        return
    if not isinstance(provenance, dict):
        errors.append(f"{path}.provenance: included photo needs structured resume PDF provenance")
        return
    method = provenance.get("extraction_method")
    if method == "embedded_image":
        if not isinstance(provenance.get("image_index"), int) or isinstance(provenance.get("image_index"), bool):
            errors.append(f"{path}.provenance.image_index: embedded_image needs a non-negative integer")
        if provenance.get("crop_box") is not None:
            errors.append(f"{path}.provenance.crop_box: embedded_image must not contain a crop box")
    elif method == "page_crop":
        crop_box = provenance.get("crop_box")
        if (
            not isinstance(crop_box, list)
            or len(crop_box) != 4
            or any(not isinstance(item, int) or isinstance(item, bool) for item in crop_box)
            or crop_box[0] < 0
            or crop_box[1] < 0
            or crop_box[2] <= 0
            or crop_box[3] <= 0
        ):
            errors.append(f"{path}.provenance.crop_box: page_crop needs x,y,width,height")
        if provenance.get("image_index") is not None:
            errors.append(f"{path}.provenance.image_index: page_crop must not contain an image index")
    else:
        errors.append(f"{path}.provenance.extraction_method: included photo needs embedded_image or page_crop")

    data_uri = photo.get("data_uri")
    mime_type = photo.get("mime_type")
    if not isinstance(data_uri, str):
        errors.append(f"{path}.data_uri: included photo must use a local image data URI")
        return
    if len(data_uri) > PHOTO_MAX_DATA_URI_CHARS:
        errors.append(f"{path}.data_uri: encoded photo exceeds the bounded data URI length")
        return
    match = PHOTO_DATA_URI_PATTERN.fullmatch(data_uri)
    if not match:
        errors.append(f"{path}.data_uri: included photo must use a local image data URI")
        return
    detected_mime, encoded = match.groups()
    if mime_type != detected_mime:
        errors.append(f"{path}.mime_type: must match the image data URI MIME type")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        errors.append(f"{path}.data_uri: invalid base64 image data ({exc})")
        return
    if len(raw) > PHOTO_MAX_BYTES:
        errors.append(f"{path}.data_uri: photo exceeds the {PHOTO_MAX_BYTES} byte limit")
    if photo.get("byte_length") != len(raw):
        errors.append(f"{path}.byte_length: must match decoded image bytes")
    if photo.get("sha256") != hashlib.sha256(raw).hexdigest():
        errors.append(f"{path}.sha256: must match decoded image bytes")
    try:
        if detect_mime(raw) != detected_mime:
            errors.append(f"{path}.data_uri: image bytes do not match the declared MIME type")
        sanitized, width, height = sanitize_image(raw, detected_mime)
        if sanitized != raw:
            errors.append(f"{path}.data_uri: image bytes must be sanitized before embedding")
        if photo.get("pixel_width") != width or photo.get("pixel_height") != height:
            errors.append(f"{path}: pixel dimensions must match decoded image bytes")
        if not (
            PHOTO_MIN_DIMENSION <= width <= PHOTO_MAX_DIMENSION
            and PHOTO_MIN_DIMENSION <= height <= PHOTO_MAX_DIMENSION
        ):
            errors.append(
                f"{path}: photo dimensions must each be from {PHOTO_MIN_DIMENSION} to {PHOTO_MAX_DIMENSION} pixels"
            )
    except ValueError as exc:
        errors.append(f"{path}.data_uri: {exc}")


def _check_timeline_age_estimate(
    estimate: dict[str, Any],
    birth_information: dict[str, Any],
    report_date: str,
    path: str,
    errors: list[str],
) -> None:
    if estimate.get("as_of") != report_date:
        errors.append(f"{path}.as_of must equal case.report_date")
    if estimate.get("assumptions") != AGE_ASSUMPTIONS:
        errors.append(f"{path}: enrollment-age assumptions must be 16, 18, and 20")
    status = estimate.get("status")
    anchor = estimate.get("anchor")
    checks = estimate.get("consistency_checks", [])
    birth_provided = birth_information.get("source_status") == "candidate_provided"
    if birth_provided:
        if status != "not_needed":
            errors.append(f"{path}.status: birth information is provided, so timeline estimate must be not_needed")
        if anchor is not None or estimate.get("min_years") is not None or estimate.get("max_years") is not None:
            errors.append(f"{path}: birth information takes precedence over timeline inference")
        if checks or estimate.get("consistency_status") != "not_checked":
            errors.append(f"{path}: not_needed estimate must not retain timeline checks")
        return
    if status == "not_needed":
        errors.append(f"{path}.status: not_needed is allowed only when candidate birth information is provided")
        return
    if status == "insufficient_evidence":
        if anchor is not None or estimate.get("min_years") is not None or estimate.get("max_years") is not None:
            errors.append(f"{path}: insufficient evidence must not contain an anchor or numeric range")
        if estimate.get("consistency_status") != "not_assessable":
            errors.append(f"{path}.consistency_status: insufficient evidence must be not_assessable")
        if "证据不足" not in str(estimate.get("display", "")) and "无法" not in str(estimate.get("display", "")):
            errors.append(f"{path}.display: insufficient evidence must be transparent")
        return
    if not isinstance(anchor, dict):
        errors.append(f"{path}.anchor: estimated or conflicting timeline needs a structured anchor")
        return
    start = anchor.get("start")
    try:
        _, _, expected_precision = parse_partial_date(start)
        if anchor.get("precision") != expected_precision:
            errors.append(f"{path}.anchor.precision: must match anchor start precision")
        if anchor.get("kind") == "undergraduate_start":
            if anchor.get("graduation_date") is not None or anchor.get("degree_duration_years") is not None:
                errors.append(f"{path}.anchor: direct undergraduate start must not include graduation derivation fields")
        elif anchor.get("kind") == "undergraduate_start_derived_from_graduation_and_duration":
            graduation = anchor.get("graduation_date")
            duration = anchor.get("degree_duration_years")
            if subtract_years(graduation, duration) != start:
                errors.append(f"{path}.anchor: start must be derived from explicit graduation date and duration")
        for index, check in enumerate(checks):
            _, _, check_precision = parse_partial_date(check.get("date"))
            if check.get("precision") != check_precision:
                errors.append(f"{path}.consistency_checks[{index}].precision: must match date precision")
        expected_consistency = chronology_status(start, checks)
    except (TypeError, ValueError) as exc:
        errors.append(f"{path}.anchor: {exc}")
        return
    if status == "timeline_conflict":
        if estimate.get("min_years") is not None or estimate.get("max_years") is not None:
            errors.append(f"{path}: timeline conflict must not contain a numeric range")
        if estimate.get("consistency_status") != "conflict" or expected_consistency != "conflict":
            errors.append(f"{path}.consistency_status: timeline conflict needs a contradictory structured check")
        if "冲突" not in str(estimate.get("display", "")):
            errors.append(f"{path}.display: timeline conflict must be visible")
        return
    if status != "estimated":
        return
    if expected_consistency == "conflict":
        errors.append(f"{path}.status: contradictory timeline must use timeline_conflict")
    if estimate.get("consistency_status") != expected_consistency:
        errors.append(f"{path}.consistency_status: expected {expected_consistency}")
    try:
        expected_min, expected_max, _ = calculate_timeline_age_range(start, report_date)
    except (TypeError, ValueError) as exc:
        errors.append(f"{path}.anchor.start: {exc}")
        return
    if estimate.get("min_years") != expected_min or estimate.get("max_years") != expected_max:
        errors.append(f"{path}: expected inferred age range {expected_min}–{expected_max}")
    display = str(estimate.get("display", ""))
    if "推算" not in display or "非候选人自述" not in display:
        errors.append(f"{path}.display: inferred age must be clearly labeled as non-self-reported")
    if str(expected_min) not in display or str(expected_max) not in display:
        errors.append(f"{path}.display: inferred age bounds are missing")


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
        if path.endswith(".candidate_photo.data_uri"):
            return
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

    if data.get("schema_version") == "1.1.0":
        _check_candidate_photo(
            overview["candidate_photo"],
            "candidate_overview.candidate_photo",
            errors,
        )
        _check_timeline_age_estimate(
            overview["timeline_age_estimate"],
            personal["birth_information"],
            case["report_date"],
            "candidate_overview.timeline_age_estimate",
            errors,
        )

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
        signal = _personal_assessment_signal(fit_text)
        if signal:
            errors.append(
                f"candidate_overview.fit_items[{index}]: personal attribute signal {signal!r} cannot enter person-job matching"
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
        signal = _personal_assessment_signal(risk_text)
        if signal:
            errors.append(
                f"resume_risks[{index}]: personal attribute signal {signal!r} cannot be treated as a resume risk"
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
            signal = _personal_assessment_signal(rated_text)
            if signal:
                errors.append(
                    f"{path}: personal attribute signal {signal!r} cannot enter a rated question or rating signal"
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
