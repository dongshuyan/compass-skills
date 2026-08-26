#!/usr/bin/env python3
"""Regression tests for the builder's portable package validator."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


VALIDATOR = Path(__file__).with_name("validate_skill_package.py")


def write_skill(root: Path) -> Path:
    skill_dir = root / "sample-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: sample-skill
description: >- # folded description
  Build a reusable workflow from an observed run
  with clear evidence and validation.
license: Apache-2.0
compatibility: Requires Python 3.10 or newer
metadata: # package metadata
  category: maintenance
allowed-tools: Read Bash
---

# Sample Skill
""",
        encoding="utf-8",
    )
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "check.py").write_text("VALUE = 1\n", encoding="utf-8")
    evals_dir = skill_dir / "evals"
    evals_dir.mkdir()
    (evals_dir / "evals.json").write_text(
        json.dumps(
            {
                "evals": [
                    {
                        "id": 1,
                        "prompt": "Build a skill from this completed run.",
                        "expected_output": "A validated skill package.",
                        "expectations": ["Uses the authorized run evidence."],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return skill_dir


class ValidateSkillPackageTests(unittest.TestCase):
    def test_accepts_multiline_yaml_and_supported_optional_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = write_skill(Path(temp_dir))
            result = subprocess.run(
                [sys.executable, "-B", str(VALIDATOR), str(skill_dir), "--json"],
                check=False,
                capture_output=True,
                text=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(
            payload["validation_scope"],
            "package_structure_and_deterministic_artifact_checks",
        )
        self.assertFalse(payload["behavior_evaluated"])
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["warnings"], [])
        self.assertFalse((skill_dir / "scripts" / "__pycache__").exists())

    def test_accepts_quoted_name_with_trailing_comment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = write_skill(Path(temp_dir))
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                skill_md.read_text(encoding="utf-8").replace(
                    "name: sample-skill",
                    'name: "sample-skill" # package name',
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "-B", str(VALIDATOR), str(skill_dir), "--json"],
                check=False,
                capture_output=True,
                text=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(payload["errors"], [])

    def test_rejects_malformed_nested_metadata(self) -> None:
        for malformed_value in ("[maintenance", "team: east"):
            with self.subTest(malformed_value=malformed_value):
                with tempfile.TemporaryDirectory() as temp_dir:
                    skill_dir = write_skill(Path(temp_dir))
                    skill_md = skill_dir / "SKILL.md"
                    skill_md.write_text(
                        skill_md.read_text(encoding="utf-8").replace(
                            "  category: maintenance",
                            f"  category: {malformed_value}",
                        ),
                        encoding="utf-8",
                    )
                    result = subprocess.run(
                        [sys.executable, "-B", str(VALIDATOR), str(skill_dir), "--json"],
                        check=False,
                        capture_output=True,
                        text=True,
                    )

                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1, payload)
                self.assertTrue(
                    any("unsupported nested frontmatter value syntax" in item for item in payload["errors"]),
                    payload,
                )

    def test_success_message_does_not_claim_behavior_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = write_skill(Path(temp_dir))
            result = subprocess.run(
                [sys.executable, "-B", str(VALIDATOR), str(skill_dir)],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("structural package validation passed", result.stdout)
        self.assertIn("does not evaluate skill behavior", result.stdout)


if __name__ == "__main__":
    unittest.main()
