#!/usr/bin/env python3
"""Public-package privacy and portability regression tests."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.dont_write_bytecode = True


SKILL_DIR = Path(__file__).resolve().parents[1]
REQUIRED_FILES = {
    "SKILL.md",
    "agents/openai.yaml",
    "assets/candidate-assessment-template.html",
    "evals/evals.json",
    "references/agent-portability.md",
    "scripts/create_candidate_case.py",
    "scripts/render_candidate_report.py",
    "scripts/validate_candidate_report.py",
    "tests/test_interviewer_report.py",
}
TEXT_SUFFIXES = {".html", ".json", ".md", ".py", ".yaml", ".yml"}
MACHINE_PATH_PATTERNS = (
    re.compile(r"/Users/[^/<\\s]+"),
    re.compile(r"/home/[^/<\\s]+"),
    re.compile(r"/Volumes/[^/<\\s]+"),
    re.compile(r"/private/(?:var|tmp)/"),
    re.compile(r"/var/folders/"),
    re.compile(r"/mnt/[a-zA-Z]/"),
    re.compile(r"[a-zA-Z]:\\Users\\", re.IGNORECASE),
    re.compile(r"\\\\[A-Za-z0-9._-]+\\[A-Za-z0-9.$_-]+(?:\\|$)"),
)


def public_text_files() -> list[Path]:
    return sorted(
        path
        for path in SKILL_DIR.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and path != Path(__file__).resolve()
        and "__pycache__" not in path.parts
    )


class PublicPackageTests(unittest.TestCase):
    def test_required_public_files_exist(self) -> None:
        missing = sorted(relative for relative in REQUIRED_FILES if not (SKILL_DIR / relative).is_file())
        self.assertEqual([], missing)

    def test_skill_contract_is_agent_and_platform_neutral(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## 可移植运行约定", skill)
        self.assertIn("references/agent-portability.md", skill)
        self.assertIn("<python>", skill)
        self.assertNotIn("python3 <skill-dir>", skill)
        self.assertNotIn("```bash", skill)
        self.assertNotRegex(skill, re.compile(r"\\\\\n\s+--"))

    def test_package_has_no_machine_specific_paths(self) -> None:
        findings: list[str] = []
        for path in public_text_files():
            text = path.read_text(encoding="utf-8")
            for pattern in MACHINE_PATH_PATTERNS:
                if pattern.search(text):
                    findings.append(f"{path.relative_to(SKILL_DIR)}: machine path matching {pattern.pattern!r}")
        self.assertEqual([], findings)

    def test_machine_path_patterns_cover_major_platform_forms(self) -> None:
        examples = (
            "/Users/private-user/work",
            "/home/private-user/work",
            "/Volumes/private-disk/work",
            "/private/var/work",
            "/var/folders/work",
            "/mnt/c/work",
            "C:\\Users\\private-user\\work",
            "\\\\private-server\\private-share\\work",
        )
        misses = [example for example in examples if not any(pattern.search(example) for pattern in MACHINE_PATH_PATTERNS)]
        self.assertEqual([], misses)

    def test_optional_openai_metadata_is_not_a_runtime_dependency(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("codex", skill)
        self.assertNotIn("claude code", skill)
        self.assertNotIn("openai", skill)

    def test_json_resources_parse(self) -> None:
        for path in sorted(SKILL_DIR.rglob("*.json")):
            with self.subTest(path=path.relative_to(SKILL_DIR)):
                json.loads(path.read_text(encoding="utf-8"))

    def test_python_scripts_compile(self) -> None:
        paths = sorted((SKILL_DIR / "scripts").glob("*.py"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(python_310_syntax=path.name):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))
        with tempfile.TemporaryDirectory(prefix="candidate-pycache-") as cache_dir:
            completed = subprocess.run(
                [sys.executable, "-m", "py_compile", *(str(path) for path in paths)],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "PYTHONPYCACHEPREFIX": cache_dir},
            )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_case_creation_accepts_spaces_and_non_ascii_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="candidate package ") as temp_dir:
            root = Path(temp_dir) / "跨平台 cases"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SKILL_DIR / "scripts" / "create_candidate_case.py"),
                    "--root",
                    str(root),
                    "--role-slug",
                    "full-stack-ai-engineer",
                ],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            result = json.loads(completed.stdout)
            self.assertTrue(Path(result["case_dir"]).is_dir())

    def test_filename_helper_handles_windows_reserved_names(self) -> None:
        module_path = SKILL_DIR / "scripts" / "render_candidate_report.py"
        sys.path.insert(0, str(module_path.parent))
        self.addCleanup(lambda: sys.path.remove(str(module_path.parent)))
        spec = importlib.util.spec_from_file_location("candidate_report_renderer", module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec else None)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        self.assertEqual("_CON", module.safe_filename_component("CON"))
        self.assertEqual("_lpt1", module.safe_filename_component("lpt1"))

    def test_package_contains_no_runtime_caches(self) -> None:
        forbidden = [
            path.relative_to(SKILL_DIR)
            for path in SKILL_DIR.rglob("*")
            if path.name in {".DS_Store", ".ruff_cache", "__pycache__"}
            and path.parent != SKILL_DIR / "tests"
        ]
        self.assertEqual([], forbidden)


if __name__ == "__main__":
    unittest.main()
