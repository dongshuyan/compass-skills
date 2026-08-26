#!/usr/bin/env python3
"""Guard task-clarifier's explicit-invocation contract."""

from __future__ import annotations

from pathlib import Path
import re


SKILL_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    metadata = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")

    assert "$task-clarifier" in skill
    assert "trigger phrases" not in skill
    assert "policy:\n  allow_implicit_invocation: false" in metadata
    short_description = re.search(r'^  short_description: "(.*)"$', metadata, re.MULTILINE)
    assert short_description is not None
    assert 25 <= len(short_description.group(1)) <= 64

    print("ok=task-clarifier explicit trigger contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
