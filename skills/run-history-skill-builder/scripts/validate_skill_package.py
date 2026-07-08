#!/usr/bin/env python3
"""Validate a portable skill package built from run history."""

from __future__ import annotations

import argparse
import json
import py_compile
import re
import sys
from pathlib import Path

ALLOWED_TOP_LEVEL = {"SKILL.md", "agents", "assets", "evals", "references", "scripts"}
PRIVATE_PATTERNS = [
    re.compile(r"/Users/[^/\s]+"),
    re.compile(r"/home/[^/\s]+"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\[^\\\s]+"),
    re.compile(r"~/.codex/skills"),
    re.compile(r"~/.claude"),
]
FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):")
KebabName = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str] | tuple[None, str]:
    if not text.startswith("---\n"):
        return None, "missing opening frontmatter fence"
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, "missing closing frontmatter fence"
    block = text[4:end].splitlines()
    data: dict[str, str] = {}
    for line in block:
        match = FRONTMATTER_KEY_RE.match(line)
        if match:
            data[match.group(1)] = line.split(":", 1)[1].strip()
    return data, ""


def find_relative_refs(text: str) -> set[str]:
    refs = set()
    for match in re.finditer(r"(?:`|\()((?:agents|assets|evals|references|scripts)/[^`)\s]+)", text):
        refs.add(match.group(1))
    return refs


def scan_privacy(path: Path, text: str, warnings: list[str]) -> None:
    for pattern in PRIVATE_PATTERNS:
        for match in pattern.finditer(text):
            prefix = text[max(0, match.start() - 24):match.start()]
            if "re.compile(" in prefix:
                continue
            warnings.append(f"{path}: contains a machine-specific path pattern matching {pattern.pattern!r}")
            return


def validate_openai_yaml(path: Path, errors: list[str]) -> None:
    text = load_text(path)
    for required in ("display_name:", "short_description:", "default_prompt:"):
        if required not in text:
            errors.append(f"{path}: missing {required.rstrip(':')}")


def validate_evals(path: Path, errors: list[str], warnings: list[str]) -> None:
    try:
        payload = json.loads(load_text(path))
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid JSON ({exc})")
        return
    if not isinstance(payload, dict):
        errors.append(f"{path}: top-level JSON must be an object")
        return
    evals = payload.get("evals")
    if not isinstance(evals, list) or not evals:
        errors.append(f"{path}: 'evals' must be a non-empty list")
        return
    if len(evals) < 5:
        warnings.append(f"{path}: fewer than 5 eval cases; consider adding more trigger and boundary coverage")
    for index, item in enumerate(evals, start=1):
        if not isinstance(item, dict):
            errors.append(f"{path}: eval #{index} is not an object")
            continue
        for field in ("id", "prompt", "expected_output", "expectations"):
            if field not in item:
                errors.append(f"{path}: eval #{index} missing field '{field}'")
        expectations = item.get("expectations")
        if expectations is not None and (not isinstance(expectations, list) or not expectations):
            errors.append(f"{path}: eval #{index} expectations must be a non-empty list")


def validate_python_scripts(skill_dir: Path, errors: list[str]) -> None:
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return
    for script in scripts_dir.rglob("*.py"):
        try:
            py_compile.compile(str(script), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{script}: py_compile failed ({exc.msg})")


def validate_skill(skill_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not skill_dir.is_dir():
        return [f"{skill_dir}: skill directory not found"], warnings

    unknown_top = [p.name for p in skill_dir.iterdir() if p.name not in ALLOWED_TOP_LEVEL]
    if unknown_top:
        warnings.append(f"{skill_dir}: unknown top-level entries: {', '.join(sorted(unknown_top))}")

    readmes = [p for p in skill_dir.rglob("*") if p.is_file() and p.name.lower().startswith("readme")]
    if readmes:
        errors.append(f"{skill_dir}: per-skill README files are not allowed in this package")

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        errors.append(f"{skill_dir}: missing SKILL.md")
        return errors, warnings

    skill_text = load_text(skill_md)
    frontmatter, frontmatter_error = parse_frontmatter(skill_text)
    if frontmatter is None:
        errors.append(f"{skill_md}: {frontmatter_error}")
    else:
        keys = set(frontmatter)
        if keys != {"name", "description"}:
            errors.append(f"{skill_md}: frontmatter must contain only name and description, found {sorted(keys)}")
        name = frontmatter.get("name", "")
        if not KebabName.fullmatch(name):
            errors.append(f"{skill_md}: name must be kebab-case")
        if name and name != skill_dir.name:
            errors.append(f"{skill_md}: frontmatter name {name!r} does not match directory name {skill_dir.name!r}")
        description = frontmatter.get("description", "")
        if len(description) < 40:
            warnings.append(f"{skill_md}: description looks short; confirm trigger coverage")

    for rel_ref in sorted(find_relative_refs(skill_text)):
        target = skill_dir / rel_ref
        if not target.exists():
            errors.append(f"{skill_md}: referenced path does not exist: {rel_ref}")

    for path in skill_dir.rglob("*"):
        if not path.is_file():
            continue
        text_extensions = {".md", ".json", ".py", ".yaml", ".yml", ".txt"}
        if path.suffix.lower() in text_extensions or path.name == "SKILL.md":
            scan_privacy(path, load_text(path), warnings)

    openai_yaml = skill_dir / "agents" / "openai.yaml"
    if openai_yaml.exists():
        validate_openai_yaml(openai_yaml, errors)

    evals_json = skill_dir / "evals" / "evals.json"
    if evals_json.exists():
        validate_evals(evals_json, errors, warnings)

    validate_python_scripts(skill_dir, errors)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", help="Path to the skill package to validate")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of plain text")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    errors, warnings = validate_skill(skill_dir)

    if args.json:
        print(json.dumps({"skill_dir": str(skill_dir), "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    else:
        if errors:
            print("Errors:")
            for item in errors:
                print(f"- {item}")
        if warnings:
            print("Warnings:")
            for item in warnings:
                print(f"- {item}")
        if not errors and not warnings:
            print(f"{skill_dir}: validation passed")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
