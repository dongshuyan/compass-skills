#!/usr/bin/env python3
"""Smoke tests for user-profile-keeper onboarding behavior."""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import parse_qs


TMP_HOME = tempfile.mkdtemp(prefix="upk-smoke-")
os.environ["COMPASS_USER_PROFILE_HOME"] = TMP_HOME

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


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    try:
        metadata = (
            Path(__file__).resolve().parents[1] / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        assert_true(
            "policy:\n  allow_implicit_invocation: false" in metadata,
            "user-profile-keeper should require explicit $skill invocation",
        )

        missing_validation = profile_store.validate(
            type("Args", (), {"user": "missing"})()
        )
        assert_true(
            missing_validation["ok"] is False
            and missing_validation["profile_exists"] is False,
            "validate should report a missing profile without initializing it",
        )
        assert_true(
            not any(Path(TMP_HOME).iterdir()),
            "validate should not create files for a missing profile",
        )

        invalid_db = profile_store.db_file("invalid")
        invalid_db.parent.mkdir(parents=True)
        invalid_db.touch()
        invalid_before = file_digest(invalid_db)
        invalid_validation = profile_store.validate(
            type("Args", (), {"user": "invalid"})()
        )
        assert_true(
            invalid_validation["ok"] is False
            and invalid_validation["profile_exists"] is True,
            "validate should report an invalid profile without repairing it",
        )
        assert_true(
            file_digest(invalid_db) == invalid_before,
            "validate should not modify an invalid profile database",
        )

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
        profile_db = profile_store.db_file("default")
        registry = Path(TMP_HOME) / "registry.json"
        before_validation = {
            "profile_db": file_digest(profile_db),
            "registry": file_digest(registry),
        }
        validation = profile_store.validate(type("Args", (), {"user": "default"})())
        after_validation = {
            "profile_db": file_digest(profile_db),
            "registry": file_digest(registry),
        }
        assert_true(validation["ok"] is True, "initialized profile should validate")
        assert_true(
            before_validation == after_validation,
            "validate should not update the profile database or registry",
        )
        if os.name != "nt":
            os.chmod(Path(TMP_HOME), 0o755)
            os.chmod(profile_db, 0o644)
            permission_validation = profile_store.validate(
                type("Args", (), {"user": "default"})()
            )
            assert_true(
                permission_validation["ok"] is False
                and permission_validation["permission_ok"] is False
                and "base_permissions_too_open:0o755" in permission_validation["issues"]
                and "db_permissions_too_open:0o644" in permission_validation["issues"],
                "validate should fail when profile paths expose group or other permissions",
            )
            os.chmod(Path(TMP_HOME), 0o700)
            os.chmod(profile_db, 0o600)

        journal_conn = sqlite3.connect(profile_db)
        journal_conn.execute("PRAGMA journal_mode = DELETE")
        journal_conn.close()
        before_journal_validation = file_digest(profile_db)
        journal_validation = profile_store.validate(
            type("Args", (), {"user": "default"})()
        )
        assert_true(
            journal_validation["ok"] is False
            and journal_validation["journal_mode_ok"] is False
            and "journal_mode_not_wal:delete" in journal_validation["issues"],
            "validate should fail when the profile database is not in WAL mode",
        )
        assert_true(
            file_digest(profile_db) == before_journal_validation,
            "validate should report a journal-mode problem without repairing it",
        )
        restore_conn = profile_store.connect("default")
        restore_conn.close()

        conn = profile_store.connect("default")
        with conn:
            normalized = [profile_store.normalize_candidate(candidate, "smoke test") for candidate in candidates]
            proposal_id = profile_store.create_proposal(conn, "default", normalized, "smoke test", [])
        pending = profile_store.proposal_list(type("Args", (), {"user": "default", "status": ["pending"]})())
        assert_true(pending["proposals"][0]["proposal_id"] == proposal_id, "proposal should be readable")
        overview = profile_store.read_view(type("Args", (), {"user": "default", "view": "profile_overview"})())
        assert_true(overview["ok"] is True and overview["view"] == "profile_overview", "profile_overview should be readable")
        conn.close()
    finally:
        shutil.rmtree(TMP_HOME, ignore_errors=True)
    print("smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
