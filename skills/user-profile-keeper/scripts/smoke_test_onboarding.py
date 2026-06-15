#!/usr/bin/env python3
"""Smoke tests for user-profile-keeper onboarding behavior."""

from __future__ import annotations

import os
import shutil
import tempfile
from urllib.parse import parse_qs


TMP_HOME = tempfile.mkdtemp(prefix="upk-smoke-")
os.environ["CODEX_USER_PROFILE_HOME"] = TMP_HOME

import onboarding_webui as webui  # noqa: E402
import profile_store  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def summaries(candidates: list[dict]) -> list[str]:
    return [candidate["value"]["summary"] for candidate in candidates]


def candidate_by_claim(candidates: list[dict], claim: str) -> dict:
    matches = [candidate for candidate in candidates if candidate["claim"] == claim]
    assert_true(len(matches) == 1, f"expected exactly one candidate for {claim}, got {len(matches)}")
    return matches[0]


def main() -> int:
    try:
        page = webui.page("default")
        assert_true("年龄段" in page, "page should include age range")
        assert_true("最高学历或在读阶段" in page, "page should include education level")
        assert_true("我应该如何指出问题、反驳假设或提醒风险" in page, "page should use clear risk/challenge wording")
        assert_true("是否希望被挑战" not in page, "page should not use ambiguous challenge wording")
        assert_true("用户自定义答案" in page, "choice fields should expose custom-answer option")

        form = parse_qs(
            "answer_length=__custom__&answer_length_custom=按任务复杂度来，简单任务短答，复杂任务给结构化依据"
            "&evidence_style=证据优先&evidence_style_custom=这段隐藏文本应被忽略"
            "&age_range=25-34&education_level=__custom__&education_level_custom=博士在读，跨学科方向"
            "&challenge_style=__custom__&challenge_style_custom=先执行明确需求，发现关键假设错误时直接指出并解释影响"
            "&always_confirm_sensitive=yes"
        )
        _display_name, candidates, redactions = webui.candidates_from_form(form)
        got = summaries(candidates)
        assert_true(not redactions, "non-secret form should not create redactions")
        assert_true("按任务复杂度来，简单任务短答，复杂任务给结构化依据" in got, "custom answer should be stored as final answer")
        assert_true("用户自定义答案" not in " ".join(got), "UI custom label should not be stored")
        assert_true("这段隐藏文本应被忽略" not in " ".join(got), "hidden custom textarea should be ignored for preset choices")
        assert_true(candidate_by_claim(candidates, "age_range")["sensitivity"] == "private", "age range should default to private")
        assert_true(candidate_by_claim(candidates, "education_level")["sensitivity"] == "private", "education should default to private")
        assert_true(candidate_by_claim(candidates, "always_confirm_sensitive_storage")["sensitivity"] == "low", "checkbox summary should be low")

        secret_form = parse_qs("major_field=api_key%3D" + "sk-" + "testtesttesttesttesttesttest")
        _display_name, candidates, redactions = webui.candidates_from_form(secret_form)
        assert_true(len(redactions) == 1, "secret-like text should create one redaction")
        assert_true("[REDACTED: potential credential omitted]" in summaries(candidates), "candidate should contain redacted placeholder")

        profile_store.init_user("default", None)
        conn = profile_store.connect("default")
        with conn:
            normalized = [profile_store.normalize_candidate(candidate, "smoke test") for candidate in candidates]
            proposal_id = profile_store.create_proposal(conn, "default", normalized, "smoke test", [])
        pending = profile_store.proposal_list(type("Args", (), {"user": "default", "status": ["pending"]})())
        assert_true(pending["proposals"][0]["proposal_id"] == proposal_id, "proposal should be readable")
        overview = profile_store.read_view(type("Args", (), {"user": "default", "view": "profile_overview"})())
        assert_true(overview["ok"] is True and overview["view"] == "profile_overview", "profile_overview should be readable")
    finally:
        shutil.rmtree(TMP_HOME, ignore_errors=True)
    print("smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
