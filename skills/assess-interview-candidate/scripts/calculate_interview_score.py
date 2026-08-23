#!/usr/bin/env python3
"""Calculate interview-only scores, coverage, comparability, and gates."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

from validate_case_contract import loads_strict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate a 0-100 interview score from 1-5 human ratings. Null/unasked items "
            "are excluded; resume evidence is reported separately and never enters the score."
        )
    )
    parser.add_argument("--blueprint", required=True, type=Path, help="Interview blueprint JSON with questions[]")
    parser.add_argument("--state", required=True, type=Path, help="Interview state JSON with answers{} or scores{}")
    parser.add_argument("--output", type=Path, help="Optional JSON output; stdout is always available")
    parser.add_argument("--force", action="store_true", help="Explicitly replace an existing --output file")
    return parser.parse_args()


def load_object(path: Path, label: str) -> dict[str, Any]:
    value = loads_strict(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def normalize_answers(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = state.get("responses", state.get("answers", state.get("scores", {})))
    if isinstance(raw, list):
        mapped: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(raw):
            if not isinstance(item, dict) or not isinstance(item.get("question_id"), str):
                raise ValueError(f"answers[{index}] must contain string question_id")
            qid = item["question_id"]
            if qid in mapped:
                raise ValueError(f"duplicate answer question_id: {qid}")
            mapped[qid] = item
        return mapped
    if not isinstance(raw, dict):
        raise ValueError("state.answers must be an object or array")
    mapped = {}
    for question_id, item in raw.items():
        if not isinstance(question_id, str):
            raise ValueError("answer keys must be strings")
        if isinstance(item, dict):
            mapped[question_id] = item
        elif item is None or finite_number(item):
            mapped[question_id] = {"asked": item is not None, "score": item}
        else:
            raise ValueError(f"answer for {question_id} must be an object, number, or null")
    return mapped


def write_json(path: Path, value: dict[str, Any], force: bool) -> None:
    path = path.expanduser()
    if not path.parent.is_dir():
        raise ValueError(f"output parent does not exist: {path.parent}")
    if path.is_symlink():
        raise ValueError(f"refusing to write through symbolic link: {path}")
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing output: {path}")
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if force else os.O_EXCL)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def calculate(blueprint: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    blueprint_case_id = blueprint.get("case_id")
    state_case_id = state.get("case_id")
    if not isinstance(blueprint_case_id, str) or not blueprint_case_id.strip():
        raise ValueError("blueprint.case_id must be a non-empty string")
    if not isinstance(state_case_id, str) or not state_case_id.strip():
        raise ValueError("state.case_id must be a non-empty string")
    if state_case_id != blueprint_case_id:
        raise ValueError("state.case_id must exactly match blueprint.case_id")
    blueprint_version = blueprint.get("blueprint_version")
    state_blueprint_version = state.get("blueprint_version")
    if not isinstance(blueprint_version, str) or not blueprint_version.strip():
        raise ValueError("blueprint.blueprint_version must be a non-empty string")
    if not isinstance(state_blueprint_version, str) or not state_blueprint_version.strip():
        raise ValueError("state.blueprint_version must be a non-empty string")
    if state_blueprint_version != blueprint_version:
        raise ValueError("state.blueprint_version must exactly match blueprint.blueprint_version")

    questions = blueprint.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("blueprint.questions must be a non-empty array")
    answers = normalize_answers(state)
    human_review_status = state.get("human_review_status", "pending")
    if human_review_status not in {"pending", "in_progress", "reviewed", "approved"}:
        raise ValueError("state.human_review_status must be pending, in_progress, reviewed, or approved")

    seen: set[str] = set()
    question_ids: set[str] = set()
    planned_weight = 0.0
    answered_weight = 0.0
    weighted_sum = 0.0
    core_weight = 0.0
    core_answered_weight = 0.0
    core_weighted_sum = 0.0
    answered_count = 0
    planned_count = 0
    gate_details: list[dict[str, Any]] = []
    item_results: list[dict[str, Any]] = []

    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            raise ValueError(f"questions[{index}] must be an object")
        question_id = question.get("id", question.get("question_id"))
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"questions[{index}] needs a non-empty id")
        if question_id in seen:
            raise ValueError(f"duplicate question id: {question_id}")
        seen.add(question_id)
        question_ids.add(question_id)
        scored = question.get("scored", True)
        if not isinstance(scored, bool):
            raise ValueError(f"question {question_id}: scored must be boolean")
        core = question.get("core", False)
        gate = question.get("gate", False)
        if not isinstance(core, bool) or not isinstance(gate, bool):
            raise ValueError(f"question {question_id}: core and gate must be boolean")
        gate_min = question.get("gate_threshold", question.get("gate_min_score"))
        if gate and (not scored or not core):
            raise ValueError(f"question {question_id}: gate questions must be scored and core")
        if core and not scored:
            raise ValueError(f"question {question_id}: core questions must be scored")
        if gate and gate_min is None:
            raise ValueError(f"question {question_id}: gate_threshold is required for gate questions")
        if gate and (not finite_number(gate_min) or not 1 <= float(gate_min) <= 5):
            raise ValueError(f"question {question_id}: gate_threshold must be from 1 to 5")
        if not scored:
            if gate:
                gate_details.append(
                    {"question_id": question_id, "status": "unresolved", "score": None, "minimum": float(gate_min)}
                )
            continue
        weight = question.get("weight")
        if not finite_number(weight) or weight <= 0:
            raise ValueError(f"question {question_id}: weight must be a finite positive number")
        weight = float(weight)

        planned_count += 1
        planned_weight += weight
        if core:
            core_weight += weight
        answer = answers.get(question_id, {"asked": False, "score": None})
        asked = answer.get("asked", answer.get("score") is not None)
        score = answer.get("score")
        confirmed = answer.get("human_confirmed", False)
        if not isinstance(asked, bool):
            raise ValueError(f"answer {question_id}: asked must be boolean")
        if not isinstance(confirmed, bool):
            raise ValueError(f"answer {question_id}: human_confirmed must be boolean")
        if not asked and score is not None:
            raise ValueError(f"answer {question_id}: unasked item cannot have a score")
        if score is not None and (not finite_number(score) or float(score) not in {1.0, 2.0, 3.0, 4.0, 5.0}):
            raise ValueError(f"answer {question_id}: score must be null or one of 1, 2, 3, 4, 5")
        answered = asked and score is not None and confirmed
        normalized_score: float | None = None
        if answered:
            score = float(score)
            normalized_score = (score - 1.0) / 4.0 * 100.0
            weighted_sum += weight * normalized_score
            answered_weight += weight
            answered_count += 1
            if core:
                core_answered_weight += weight
                core_weighted_sum += weight * normalized_score
        item_results.append(
            {
                "question_id": question_id,
                "weight": weight,
                "core": core,
                "gate": gate,
                "asked": asked,
                "score": score,
                "human_confirmed": confirmed,
                "counted": answered,
                "normalized_score": round(normalized_score, 2) if normalized_score is not None else None,
            }
        )
        if gate:
            if not answered:
                gate_status = "unresolved"
            elif float(score) < float(gate_min):
                gate_status = "failed"
            else:
                gate_status = "passed"
            gate_details.append(
                {
                    "question_id": question_id,
                    "status": gate_status,
                    "score": score,
                    "minimum": float(gate_min),
                }
            )

    unknown = sorted(set(answers) - question_ids)
    if unknown:
        raise ValueError(f"state contains unknown question ids: {', '.join(unknown)}")
    missing = sorted(question_ids - set(answers))
    if missing:
        raise ValueError(f"state must contain every blueprint question id, including unasked items: {', '.join(missing)}")

    interview_score = round(weighted_sum / answered_weight, 1) if answered_weight else None
    core_score = round(core_weighted_sum / core_answered_weight, 1) if core_answered_weight else None
    coverage = round(answered_weight / planned_weight * 100.0, 1) if planned_weight else None
    core_coverage = round(core_answered_weight / core_weight * 100.0, 1) if core_weight else None
    scoring = blueprint.get("scoring", {})
    if not isinstance(scoring, dict):
        raise ValueError("blueprint.scoring must be an object")
    minimum_core_ratio = scoring.get("comparability_core_coverage_min", 1.0)
    if not finite_number(minimum_core_ratio) or float(minimum_core_ratio) != 1.0:
        raise ValueError("scoring.comparability_core_coverage_min must equal 1.0")
    minimum_core_coverage = 100.0

    if any(item["status"] == "failed" for item in gate_details):
        gate_status = "threshold_not_met"
    elif any(item["status"] == "unresolved" for item in gate_details):
        gate_status = "insufficient_evidence"
    elif gate_details:
        gate_status = "threshold_met"
    else:
        gate_status = "not_configured"

    if core_weight == 0:
        comparability = "not_configured"
        comparability_reason = "题本未配置共同核心题，当前结果不可用于跨候选人比较。"
    elif core_coverage is None or core_coverage < minimum_core_coverage:
        comparability = "insufficient_core_coverage"
        comparability_reason = "共同核心题覆盖不足，当前结果不可用于跨候选人比较。"
    elif gate_status == "insufficient_evidence":
        comparability = "gate_evidence_incomplete"
        comparability_reason = "共同核心覆盖达标，但门槛题证据尚未完整。"
    elif coverage == 100.0:
        comparability = "all_planned_comparable"
        comparability_reason = "共同核心分与完整题本综合分均可在相同蓝图版本内比较。"
    else:
        comparability = "core_comparable_composite_incomplete"
        comparability_reason = "共同核心分可比较；动态综合分因计划题覆盖不足而不可比较。"
    core_comparable = comparability in {"all_planned_comparable", "core_comparable_composite_incomplete"}
    composite_comparable = comparability == "all_planned_comparable"

    resume = state.get("resume", state.get("resume_evidence", {}))
    if resume is None:
        resume = {}
    if finite_number(resume):
        resume = {"score": float(resume), "human_confirmed": False}
    if not isinstance(resume, dict):
        raise ValueError("state.resume_evidence must be an object, number, or null")
    resume_score = resume.get("evidence_score", resume.get("score"))
    if resume_score is not None and (not finite_number(resume_score) or not 0 <= float(resume_score) <= 100):
        raise ValueError("resume_evidence.score must be null or a number from 0 to 100")
    resume_confirmed = resume.get("human_confirmed", False)
    if not isinstance(resume_confirmed, bool):
        raise ValueError("resume_evidence.human_confirmed must be boolean")

    return {
        "schema_version": "1.0.0",
        "case_id": blueprint_case_id,
        "blueprint_version": blueprint_version,
        "human_review_status": human_review_status,
        "metrics": {
            "interview_composite": interview_score,
            "core_score": core_score,
            "comparable_score": core_score,
            "coverage": coverage,
            "core_coverage": core_coverage,
            "gate_status": gate_status,
            "comparability": comparability,
            "core_comparable": core_comparable,
            "composite_comparable": composite_comparable,
        },
        "interview": {
            "score": interview_score,
            "core_score": core_score,
            "comparable_score": core_score,
            "scale": "0-100",
            "formula": "weighted mean of (rating-1)/4*100 over asked, rated, human-confirmed interview items only",
            "answered_questions": answered_count,
            "planned_questions": planned_count,
            "answered_weight": round(answered_weight, 6),
            "planned_weight": round(planned_weight, 6),
            "coverage": coverage,
            "core_coverage": core_coverage,
            "comparable": core_comparable,
            "core_comparable": core_comparable,
            "composite_comparable": composite_comparable,
            "comparability": comparability,
            "comparability_reason": comparability_reason,
            "human_confirmed": all(item["human_confirmed"] for item in item_results) if item_results else False,
            "provisional": not composite_comparable,
            "gate_status": gate_status,
            "gate_details": gate_details,
            "items": item_results,
        },
        "resume_evidence": {
            "score": round(float(resume_score), 2) if resume_score is not None else None,
            "scale": "0-100",
            "human_confirmed": resume_confirmed,
            "included_in_interview_score": False,
        },
    }


def main() -> int:
    args = parse_args()
    try:
        result = calculate(load_object(args.blueprint, "blueprint"), load_object(args.state, "state"))
        if args.output:
            write_json(args.output, result, args.force)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
