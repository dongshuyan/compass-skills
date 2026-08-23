#!/usr/bin/env python3
"""Validate bundled JSON Schemas, cross-object references, and report data."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SKILL_DIR = Path(__file__).resolve().parent.parent
SCHEMA_FILES = {
    "job_model": SKILL_DIR / "references" / "schema-job-model.json",
    "sources": SKILL_DIR / "references" / "schema-source-record.json",
    "evidence": SKILL_DIR / "references" / "schema-evidence-ledger.json",
    "blueprint": SKILL_DIR / "references" / "schema-interview-blueprint.json",
}
BEHAVIOR_DIMENSIONS = {
    "professional_ethics_values",
    "professional_capability",
    "communication",
    "collaboration_relationships",
    "career_commitment_stability",
    "responsibility_dependability",
    "compensation_tradeoffs",
    "candidate_priorities",
    "pressure_response",
}
SUPPORTED_SCHEMA_KEYWORDS = {
    "$schema", "$id", "$defs", "$ref", "title", "description", "type",
    "properties", "required", "additionalProperties", "items", "enum", "const",
    "allOf", "if", "then", "else", "not", "minLength", "minItems", "maxItems",
    "pattern", "format", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "default",
}


def reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant is forbidden: {value}")


def loads_strict(text: str) -> Any:
    return json.loads(text, parse_constant=reject_constant)


def load_json_strict(path: Path, label: str) -> dict[str, Any]:
    value = loads_strict(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if finite_number(left) and finite_number(right):
        return float(left) == float(right)
    return type(left) is type(right) and left == right


def type_matches(value: Any, expected: str) -> bool:
    return {
        "null": value is None,
        "boolean": isinstance(value, bool),
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": finite_number(value),
    }.get(expected, False)


def resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"only local JSON Schema references are supported: {ref}")
    current: Any = root_schema
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise ValueError(f"unresolvable JSON Schema reference: {ref}")
        current = current[token]
    if not isinstance(current, dict):
        raise ValueError(f"JSON Schema reference does not resolve to an object: {ref}")
    return current


def valid_format(value: str, format_name: str) -> bool:
    try:
        if format_name == "date":
            date.fromisoformat(value)
            return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
        if format_name == "date-time":
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return "T" in value and parsed.tzinfo is not None
        if format_name == "uri":
            parsed = urlparse(value)
            return bool(parsed.scheme and (parsed.netloc or parsed.scheme == "file"))
        return False
    except ValueError:
        return False


def validate_schema(
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any] | None = None,
    path: str = "$",
) -> list[str]:
    root = root_schema or schema
    errors: list[str] = []
    if "$ref" in schema:
        try:
            target = resolve_ref(root, schema["$ref"])
        except ValueError as exc:
            return [f"{path}: {exc}"]
        return validate_schema(value, target, root, path)

    if isinstance(value, float) and not math.isfinite(value):
        errors.append(f"{path}: non-finite numbers are forbidden")

    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else expected
        if not isinstance(expected_types, list) or not all(isinstance(item, str) for item in expected_types):
            return [f"{path}: invalid type declaration in bundled schema"]
        if not any(type_matches(value, item) for item in expected_types):
            errors.append(f"{path}: expected type {' or '.join(expected_types)}")
            return errors

    if "const" in schema and not json_equal(value, schema["const"]):
        errors.append(f"{path}: value must equal {schema['const']!r}")
    if "enum" in schema and not any(json_equal(value, item) for item in schema["enum"]):
        errors.append(f"{path}: value is not in the allowed enum")

    for branch in schema.get("allOf", []):
        errors.extend(validate_schema(value, branch, root, path))
    if "if" in schema:
        condition_matches = not validate_schema(value, schema["if"], root, path)
        branch = schema.get("then") if condition_matches else schema.get("else")
        if isinstance(branch, dict):
            errors.extend(validate_schema(value, branch, root, path))
    if "not" in schema and not validate_schema(value, schema["not"], root, path):
        errors.append(f"{path}: value matches a forbidden schema")

    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    errors.extend(validate_schema(value[key], child_schema, root, f"{path}.{key}"))
            additional = schema.get("additionalProperties", True)
            if additional is False:
                for key in sorted(set(value) - set(properties)):
                    errors.append(f"{path}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                for key in sorted(set(value) - set(properties)):
                    errors.extend(validate_schema(value[key], additional, root, f"{path}.{key}"))

    if isinstance(value, list):
        if isinstance(schema.get("minItems"), int) and len(value) < schema["minItems"]:
            errors.append(f"{path}: requires at least {schema['minItems']} item(s)")
        if isinstance(schema.get("maxItems"), int) and len(value) > schema["maxItems"]:
            errors.append(f"{path}: allows at most {schema['maxItems']} item(s)")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                errors.extend(validate_schema(item, schema["items"], root, f"{path}[{index}]"))

    if isinstance(value, str):
        if isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
            errors.append(f"{path}: string is shorter than {schema['minLength']}")
        if isinstance(schema.get("pattern"), str) and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: string does not match required pattern")
        if isinstance(schema.get("format"), str) and not valid_format(value, schema["format"]):
            errors.append(f"{path}: invalid {schema['format']} format")

    if finite_number(value):
        if finite_number(schema.get("minimum")) and value < schema["minimum"]:
            errors.append(f"{path}: number is below minimum {schema['minimum']}")
        if finite_number(schema.get("maximum")) and value > schema["maximum"]:
            errors.append(f"{path}: number is above maximum {schema['maximum']}")
        if finite_number(schema.get("exclusiveMinimum")) and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: number must be greater than {schema['exclusiveMinimum']}")
        if finite_number(schema.get("exclusiveMaximum")) and value >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: number must be less than {schema['exclusiveMaximum']}")
    return errors


def audit_schema_keywords(schema: Any, path: str = "$schema") -> list[str]:
    if not isinstance(schema, dict):
        return [f"{path}: schema node must be an object"]
    errors = [f"{path}: unsupported schema keyword {key!r}" for key in schema if key not in SUPPORTED_SCHEMA_KEYWORDS]
    for container in ("$defs", "properties"):
        children = schema.get(container, {})
        if isinstance(children, dict):
            for key, child in children.items():
                errors.extend(audit_schema_keywords(child, f"{path}.{container}.{key}"))
    for key in ("items", "additionalProperties", "if", "then", "else", "not"):
        child = schema.get(key)
        if isinstance(child, dict):
            errors.extend(audit_schema_keywords(child, f"{path}.{key}"))
    branches = schema.get("allOf", [])
    if isinstance(branches, list):
        for index, child in enumerate(branches):
            errors.extend(audit_schema_keywords(child, f"{path}.allOf[{index}]"))
    return errors


def unique_id_map(items: Any, label: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(items, list):
        return result
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not nonempty(item.get("id")):
            continue
        item_id = item["id"]
        if item_id in result:
            errors.append(f"{label}[{index}]: duplicate id {item_id!r}")
        else:
            result[item_id] = item
    return result


def require_refs(refs: Any, known: set[str], path: str, errors: list[str]) -> None:
    if not isinstance(refs, list):
        return
    for ref in refs:
        if isinstance(ref, str) and ref not in known:
            errors.append(f"{path}: unresolved reference {ref!r}")


def require_accepted_source_refs(
    refs: Any,
    source_map: dict[str, dict[str, Any]],
    path: str,
    errors: list[str],
) -> None:
    if not isinstance(refs, list):
        return
    for ref in refs:
        if not isinstance(ref, str):
            continue
        source = source_map.get(ref)
        if source is None:
            errors.append(f"{path}: unresolved source reference {ref!r}")
        elif source.get("accepted") is not True or source.get("status") != "accepted":
            errors.append(f"{path}: source reference {ref!r} is not an accepted source")


def validate_timeline(blueprint: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    sections = blueprint.get("sections", [])
    questions = blueprint.get("questions", [])
    if not isinstance(sections, list) or not isinstance(questions, list):
        return
    section_orders = [item.get("order") for item in sections if isinstance(item, dict)]
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in section_orders) or sorted(section_orders) != list(range(1, len(sections) + 1)):
        errors.append("blueprint.sections: order values must be unique and consecutive from 1")
    question_orders = [item.get("order") for item in questions if isinstance(item, dict)]
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in question_orders) or sorted(question_orders) != list(range(1, len(questions) + 1)):
        errors.append("blueprint.questions: order values must be unique and consecutive from 1")
    ordered = sorted(
        (item for item in sections if isinstance(item, dict)),
        key=lambda item: item.get("order") if isinstance(item.get("order"), int) else len(sections) + 1,
    )
    duration = blueprint.get("duration_minutes")
    if ordered and finite_number(duration):
        first_start = ordered[0].get("start_minute")
        if finite_number(first_start) and abs(float(first_start)) > 1e-9:
            errors.append("blueprint.sections: timeline must start at minute 0")
        previous_end = 0.0
        for index, section in enumerate(ordered):
            start = section.get("start_minute")
            end = section.get("end_minute")
            if not finite_number(start) or not finite_number(end):
                continue
            if index and abs(float(start) - previous_end) > 1e-9:
                errors.append(f"blueprint.sections[{index}]: timeline must be continuous without gaps or overlaps")
            previous_end = float(end)
        if abs(previous_end - float(duration)) > 1e-9:
            errors.append("blueprint.sections: final end_minute must equal duration_minutes")
        if not 25 <= float(duration) <= 35:
            warnings.append("blueprint.duration_minutes is outside the default approximately-30-minute range (25-35)")


def answer_ids(state: dict[str, Any], errors: list[str]) -> set[str]:
    raw = state.get("responses", state.get("answers", state.get("scores")))
    if isinstance(raw, dict):
        return {key for key in raw if isinstance(key, str)}
    if isinstance(raw, list):
        result: set[str] = set()
        for index, item in enumerate(raw):
            qid = item.get("question_id") if isinstance(item, dict) else None
            if not nonempty(qid):
                errors.append(f"score_state.responses[{index}]: question_id is required")
            elif qid in result:
                errors.append(f"score_state.responses[{index}]: duplicate question_id {qid!r}")
            else:
                result.add(qid)
        return result
    errors.append("score_state: answers/responses/scores object is required")
    return set()


def validate_score_state(state: dict[str, Any], blueprint: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if state.get("case_id") != blueprint.get("case_id"):
        errors.append("score_state.case_id must exactly match blueprint.case_id")
    if state.get("blueprint_version") != blueprint.get("blueprint_version"):
        errors.append("score_state.blueprint_version must exactly match blueprint.blueprint_version")
    expected = {
        item["id"] for item in blueprint.get("questions", [])
        if isinstance(item, dict) and nonempty(item.get("id"))
    }
    actual = answer_ids(state, errors)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            errors.append("score_state: missing question ids: " + ", ".join(missing))
        if extra:
            errors.append("score_state: unknown question ids: " + ", ".join(extra))
    return errors


def validate_case_documents(
    job_model: dict[str, Any],
    sources: dict[str, Any],
    evidence: dict[str, Any],
    blueprint: dict[str, Any],
    score_state: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    documents = {
        "job_model": job_model,
        "sources": sources,
        "evidence": evidence,
        "blueprint": blueprint,
    }
    for label, document in documents.items():
        schema = load_json_strict(SCHEMA_FILES[label], f"{label} schema")
        errors.extend(f"{label}: {message}" for message in audit_schema_keywords(schema))
        errors.extend(f"{label}: {message}" for message in validate_schema(document, schema))

    case_values = [document.get("case_id") for document in documents.values()]
    if not all(nonempty(value) for value in case_values) or len(set(case_values)) != 1:
        errors.append("case_id must be present and identical across job model, sources, evidence, and blueprint")

    source_map = unique_id_map(sources.get("records"), "sources.records", errors)
    capability_map = unique_id_map(job_model.get("capabilities"), "job_model.capabilities", errors)
    output_map = unique_id_map(job_model.get("work_outputs", []), "job_model.work_outputs", errors)
    evidence_map = unique_id_map(evidence.get("items"), "evidence.items", errors)
    section_map = unique_id_map(blueprint.get("sections"), "blueprint.sections", errors)
    question_map = unique_id_map(blueprint.get("questions"), "blueprint.questions", errors)
    del evidence_map, question_map

    capability_ids = set(capability_map)
    output_ids = set(output_map)
    section_ids = set(section_map)

    for index, source in enumerate(sources.get("records", [])):
        if isinstance(source, dict):
            require_refs(source.get("capability_ids", []), capability_ids, f"sources.records[{index}].capability_ids", errors)
    for index, output in enumerate(job_model.get("work_outputs", [])):
        if isinstance(output, dict):
            require_accepted_source_refs(output.get("source_ids", []), source_map, f"job_model.work_outputs[{index}].source_ids", errors)
    task_ids: set[str] = set()
    for cap_index, capability in enumerate(job_model.get("capabilities", [])):
        if not isinstance(capability, dict):
            continue
        require_accepted_source_refs(capability.get("source_ids", []), source_map, f"job_model.capabilities[{cap_index}].source_ids", errors)
        for task_index, task in enumerate(capability.get("tasks", [])):
            if not isinstance(task, dict):
                continue
            task_id = task.get("id")
            if nonempty(task_id):
                if task_id in task_ids:
                    errors.append(f"job_model.capabilities[{cap_index}].tasks[{task_index}]: duplicate task id {task_id!r}")
                task_ids.add(task_id)
            require_refs(task.get("output_ids", []), output_ids, f"job_model.capabilities[{cap_index}].tasks[{task_index}].output_ids", errors)
    for index, item in enumerate(evidence.get("items", [])):
        if isinstance(item, dict):
            require_refs(item.get("capability_ids", []), capability_ids, f"evidence.items[{index}].capability_ids", errors)
            require_accepted_source_refs(item.get("source_ids", []), source_map, f"evidence.items[{index}].source_ids", errors)
    for index, question in enumerate(blueprint.get("questions", [])):
        if not isinstance(question, dict):
            continue
        require_refs(question.get("capability_ids", []), capability_ids, f"blueprint.questions[{index}].capability_ids", errors)
        if question.get("section_id") not in section_ids:
            errors.append(f"blueprint.questions[{index}].section_id: unresolved reference {question.get('section_id')!r}")
    validate_timeline(blueprint, errors, warnings)
    if score_state is not None:
        errors.extend(validate_score_state(score_state, blueprint))
    return errors, warnings


def validate_assessment_data(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required = {
        "schema_version", "case", "job_model", "resume", "candidate_perspective",
        "behavioral_hypotheses", "blueprint", "state", "sources", "limitations",
    }
    for key in sorted(required - set(data)):
        errors.append(f"assessment_data: missing required property {key!r}")
    if errors:
        return errors, warnings
    case = data.get("case")
    resume = data.get("resume")
    state = data.get("state")
    if not isinstance(case, dict) or not nonempty(case.get("id")) or not nonempty(case.get("role_title")):
        errors.append("assessment_data.case must contain non-empty id and role_title")
        return errors, warnings
    if not isinstance(resume, dict):
        errors.append("assessment_data.resume must be an object")
        return errors, warnings
    if not isinstance(state, dict) or not isinstance(state.get("answers"), dict):
        errors.append("assessment_data.state.answers must be an object")
        return errors, warnings
    job_model = data.get("job_model")
    blueprint = data.get("blueprint")
    sources_list = data.get("sources")
    evidence_items = resume.get("evidence_items", resume.get("items", []))
    if not isinstance(job_model, dict) or not isinstance(blueprint, dict):
        errors.append("assessment_data.job_model and blueprint must be objects")
        return errors, warnings
    if not isinstance(sources_list, list) or not sources_list:
        errors.append("assessment_data.sources must be a non-empty array")
        return errors, warnings
    if not isinstance(evidence_items, list):
        errors.append("assessment_data.resume.evidence_items must be an array")
        return errors, warnings
    case_id = case["id"]
    sources = {"schema_version": data.get("schema_version"), "case_id": case_id, "records": sources_list}
    evidence = {"schema_version": data.get("schema_version"), "case_id": case_id, "items": evidence_items}
    case_errors, case_warnings = validate_case_documents(job_model, sources, evidence, blueprint, state)
    errors.extend(case_errors)
    warnings.extend(case_warnings)

    score = resume.get("evidence_score")
    if score is not None and (not finite_number(score) or not 0 <= float(score) <= 100):
        errors.append("assessment_data.resume.evidence_score must be null or a finite number from 0 to 100")

    perspectives = data.get("candidate_perspective")
    if not isinstance(perspectives, list):
        errors.append("assessment_data.candidate_perspective must be an array")
    else:
        fields = {
            "cue", "job_relevance", "hypotheses", "evidence_for", "evidence_against",
            "confidence", "what_would_falsify_it", "neutral_verification_question",
        }
        for index, item in enumerate(perspectives):
            if not isinstance(item, dict):
                errors.append(f"assessment_data.candidate_perspective[{index}] must be an object")
                continue
            missing = fields - set(item)
            if missing:
                errors.append(f"assessment_data.candidate_perspective[{index}] missing: {', '.join(sorted(missing))}")
            if not isinstance(item.get("hypotheses"), list) or len(item.get("hypotheses", [])) < 2:
                errors.append(f"assessment_data.candidate_perspective[{index}].hypotheses requires at least two explanations")
            elif not any(isinstance(hypothesis, dict) and hypothesis.get("benevolent") is True for hypothesis in item["hypotheses"]):
                errors.append(f"assessment_data.candidate_perspective[{index}].hypotheses requires a benevolent=true explanation")
            if item.get("confidence") not in {"low", "medium", "high"}:
                errors.append(f"assessment_data.candidate_perspective[{index}].confidence must be low, medium, or high")

    hypotheses = data.get("behavioral_hypotheses")
    found_dimensions: set[str] = set()
    behavior_fields = {
        "dimension_id", "status", "confidence", "observable_behaviors", "evidence_for",
        "evidence_against", "alternative_explanations", "confidence_reason",
        "what_would_falsify_it", "scoring_eligible", "scoring_basis", "validation_question",
    }
    if not isinstance(hypotheses, list):
        errors.append("assessment_data.behavioral_hypotheses must be an array")
    else:
        for index, item in enumerate(hypotheses):
            if not isinstance(item, dict):
                errors.append(f"assessment_data.behavioral_hypotheses[{index}] must be an object")
                continue
            missing = behavior_fields - set(item)
            if missing:
                errors.append(f"assessment_data.behavioral_hypotheses[{index}] missing: {', '.join(sorted(missing))}")
            dimension_id = item.get("dimension_id")
            if dimension_id in found_dimensions:
                errors.append(f"assessment_data.behavioral_hypotheses[{index}]: duplicate dimension_id {dimension_id!r}")
            if isinstance(dimension_id, str):
                found_dimensions.add(dimension_id)
            if not isinstance(item.get("scoring_eligible"), bool):
                errors.append(f"assessment_data.behavioral_hypotheses[{index}].scoring_eligible must be boolean")
            if item.get("confidence") not in {"low", "medium", "high", "unknown"}:
                errors.append(f"assessment_data.behavioral_hypotheses[{index}].confidence is invalid")
            for field in ("observable_behaviors", "evidence_for", "evidence_against", "alternative_explanations"):
                if not isinstance(item.get(field), list) or not all(nonempty(value) for value in item.get(field, [])):
                    errors.append(f"assessment_data.behavioral_hypotheses[{index}].{field} must be an array of non-empty strings")
            if isinstance(item.get("alternative_explanations"), list) and len(item["alternative_explanations"]) < 2:
                errors.append(f"assessment_data.behavioral_hypotheses[{index}].alternative_explanations requires at least two explanations")
            for field in ("status", "confidence_reason", "what_would_falsify_it", "scoring_basis", "validation_question"):
                if not nonempty(item.get(field)):
                    errors.append(f"assessment_data.behavioral_hypotheses[{index}].{field} must be a non-empty string")
        if found_dimensions != BEHAVIOR_DIMENSIONS:
            missing = sorted(BEHAVIOR_DIMENSIONS - found_dimensions)
            extra = sorted(found_dimensions - BEHAVIOR_DIMENSIONS)
            if missing:
                errors.append("assessment_data.behavioral_hypotheses missing dimensions: " + ", ".join(missing))
            if extra:
                errors.append("assessment_data.behavioral_hypotheses unknown dimensions: " + ", ".join(extra))

    expected_question_ids = {
        item["id"] for item in blueprint.get("questions", [])
        if isinstance(item, dict) and nonempty(item.get("id"))
    }
    actual_question_ids = set(state["answers"])
    if actual_question_ids != expected_question_ids:
        errors.append("assessment_data.state.answers must contain every blueprint question id exactly once")
    if case_id != job_model.get("case_id") or case_id != blueprint.get("case_id"):
        errors.append("assessment_data.case.id must match embedded job_model and blueprint case_id")
    if not isinstance(data.get("limitations"), list) or not all(nonempty(item) for item in data.get("limitations", [])):
        errors.append("assessment_data.limitations must be an array of non-empty strings")
    return errors, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate all four case objects, their cross-references, timeline, score state, and optional report data.")
    parser.add_argument("--job-model", required=True, type=Path)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--evidence-ledger", required=True, type=Path)
    parser.add_argument("--blueprint", required=True, type=Path)
    parser.add_argument("--score-state", type=Path)
    parser.add_argument("--assessment-data", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        job_model = load_json_strict(args.job_model, "job model")
        sources = load_json_strict(args.sources, "sources")
        evidence = load_json_strict(args.evidence_ledger, "evidence ledger")
        blueprint = load_json_strict(args.blueprint, "blueprint")
        score_state = load_json_strict(args.score_state, "score state") if args.score_state else None
        errors, warnings = validate_case_documents(job_model, sources, evidence, blueprint, score_state)
        if args.assessment_data:
            assessment = load_json_strict(args.assessment_data, "assessment data")
            assessment_errors, assessment_warnings = validate_assessment_data(assessment)
            errors.extend(assessment_errors)
            warnings.extend(assessment_warnings)
        payload = {"ok": not errors, "errors": errors, "warnings": warnings}
        print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if not errors else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
