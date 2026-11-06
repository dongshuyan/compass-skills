#!/usr/bin/env python3
"""Static package guards for task-clarifier.

These checks validate packaging and safety invariants only. They do not claim
that a model will follow the skill or that users will experience better
clarification.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_PATH = SKILL_DIR / "SKILL.md"


class SkillPackageError(ValueError):
    """Raised when a static skill-package invariant is violated."""


def _frontmatter_and_body(content: str) -> tuple[str, str]:
    if not content.startswith("---\n"):
        raise SkillPackageError("missing YAML frontmatter")
    match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
    if match is None:
        raise SkillPackageError("invalid YAML frontmatter fence")
    return match.group(1), content[match.end() :]


def _check_static_invariants(content: str) -> None:
    frontmatter, body = _frontmatter_and_body(content)

    name_match = re.search(r"^name:\s*([a-z0-9-]+)\s*$", frontmatter, re.MULTILINE)
    if name_match is None or name_match.group(1) != SKILL_DIR.name:
        raise SkillPackageError("frontmatter name must match the skill directory")

    description_match = re.search(
        r"^description:\s*>-\n((?:^  .*\n?)+)", frontmatter, re.MULTILINE
    )
    if description_match is None:
        raise SkillPackageError("description must use the supported folded form")
    description = " ".join(
        line.strip() for line in description_match.group(1).splitlines()
    ).strip()
    if not description or len(description) > 1024:
        raise SkillPackageError("description must be non-empty and at most 1024 characters")
    if "<" in description or ">" in description:
        raise SkillPackageError("description must not contain angle brackets")

    if re.search(r"(?:/Users/|/home/|/Volumes/|~/|[A-Za-z]:[\\/])", content):
        raise SkillPackageError("skill must not contain machine-specific absolute paths")
    if "[TODO:" in content:
        raise SkillPackageError("skill must not contain unfinished TODO placeholders")

    # Markdown links in the skill must remain portable and local. The current
    # skill has no links, but this catches a future accidental host-specific
    # or external instruction dependency without requiring a network check.
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", body):
        target = target.strip()
        if target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target_path = (SKILL_DIR / target.split("#", 1)[0]).resolve()
        if SKILL_DIR not in target_path.parents and target_path != SKILL_DIR:
            raise SkillPackageError(f"relative link escapes the skill directory: {target}")


class TaskClarifierPackageGuards(unittest.TestCase):
    def test_current_skill_meets_static_invariants(self) -> None:
        _check_static_invariants(SKILL_PATH.read_text(encoding="utf-8"))

    def test_guard_rejects_machine_path(self) -> None:
        with self.assertRaises(SkillPackageError):
            _check_static_invariants(
                "---\n"
                "name: task-clarifier\n"
                "description: >-\n"
                "  portable description\n"
                "---\n"
                "Read /Users/example/private.txt.\n"
            )

    def test_guard_rejects_external_relative_link(self) -> None:
        with self.assertRaises(SkillPackageError):
            _check_static_invariants(
                "---\n"
                "name: task-clarifier\n"
                "description: >-\n"
                "  portable description\n"
                "---\n"
                "See [outside](../outside.md).\n"
            )


if __name__ == "__main__":
    unittest.main()
