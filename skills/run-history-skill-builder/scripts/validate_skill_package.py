#!/usr/bin/env python3
"""Validate a portable skill package built from run history."""

from __future__ import annotations

import argparse
import json
import py_compile
import re
import sys
import tempfile
from pathlib import Path

ALLOWED_TOP_LEVEL = {"SKILL.md", "agents", "assets", "evals", "references", "scripts"}
SUPPORTED_FRONTMATTER_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
PRIVATE_PATTERNS = [
    re.compile(r"(?<!\w)/(Users|home|Volumes)/[^\s`'\"\)\]]+"),
    re.compile(r"(?<!\w)/private/var/[^\s`'\"\)\]]+"),
    re.compile(r"(?<!\w)/var/folders/[^\s`'\"\)\]]+"),
    re.compile(r"(?<!\w)/mnt/[A-Za-z]/[^\s`'\"\)\]]+"),
    re.compile(r"\\\\\?\\[A-Za-z]:\\[^\s`'\"\)\]]+"),
    re.compile(r"[A-Za-z]:\\[^\s`'\"\)\]]+"),
    re.compile(r"\\\\[^\\/\s`'\"\)\]]+(?:\\[^\\/\s`'\"\)\]]+){1,}"),
    re.compile(r"(?<!\w)~/(?:\.codex|\.claude)(?:/[^\s`'\"\)\]]+)?"),
]
FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(?:[ \t]*(.*))?$")
NESTED_FRONTMATTER_RE = re.compile(r"^( +)([A-Za-z0-9_.-]+):(?:[ \t]*(.*))?$")
BLOCK_SCALAR_RE = re.compile(r"^[>|](?:(?:[+-][1-9]?)|(?:[1-9][+-]?))?$")
KebabName = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_inline_comment(value: str) -> str:
    quote: str | None = None
    index = 0
    while index < len(value):
        char = value[index]
        if quote == "'":
            if char == "'" and index + 1 < len(value) and value[index + 1] == "'":
                index += 2
                continue
            if char == "'":
                quote = None
        elif quote == '"':
            if char == "\\":
                index += 2
                continue
            if char == '"':
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
        index += 1
    return value.strip()


def _decode_scalar(value: str) -> str:
    value = _strip_inline_comment(value)
    if not value:
        return ""
    if value[0] in "[{&*!":
        raise ValueError("collection, anchor, alias, and tag syntax is outside the supported scalar subset")
    if value[0] == "'" and value[-1] != "'":
        raise ValueError("unterminated single-quoted scalar")
    if value[0] == '"' and value[-1] != '"':
        raise ValueError("unterminated double-quoted scalar")
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid double-quoted scalar: {exc.msg}") from exc
        return decoded if isinstance(decoded, str) else value
    if re.search(r":[ \t]|:$", value):
        raise ValueError("an unquoted colon cannot be followed by whitespace")
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, str], str] | tuple[None, str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None, "missing opening frontmatter fence"
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None, "missing closing frontmatter fence"

    block = lines[1:end]
    data: dict[str, str] = {}
    index = 0
    while index < len(block):
        line = block[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if line[0].isspace():
            return None, f"unexpected indented frontmatter line {index + 2}"
        match = FRONTMATTER_KEY_RE.fullmatch(line)
        if not match:
            return None, f"unsupported top-level frontmatter syntax on line {index + 2}"
        key, value = match.group(1), (match.group(2) or "")
        if key in data:
            return None, f"duplicate frontmatter key {key!r}"
        normalized_value = _strip_inline_comment(value)
        if BLOCK_SCALAR_RE.fullmatch(normalized_value):
            continuation: list[str] = []
            index += 1
            while index < len(block) and (not block[index].strip() or block[index][0].isspace()):
                continuation.append(block[index])
                index += 1
            indents = [len(item) - len(item.lstrip()) for item in continuation if item.strip()]
            indent = min(indents) if indents else 0
            data[key] = " ".join(item[indent:].strip() for item in continuation if item.strip())
            continue
        if key == "metadata" and not normalized_value:
            nested_indent: int | None = None
            nested_keys: set[str] = set()
            index += 1
            while index < len(block):
                nested_line = block[index]
                if not nested_line.strip() or nested_line.lstrip().startswith("#"):
                    index += 1
                    continue
                if not nested_line[0].isspace():
                    break
                nested_match = NESTED_FRONTMATTER_RE.fullmatch(nested_line)
                if not nested_match:
                    return None, f"unsupported nested frontmatter syntax on line {index + 2}"
                indent = len(nested_match.group(1))
                nested_key = nested_match.group(2)
                nested_value = nested_match.group(3) or ""
                if nested_indent is None:
                    nested_indent = indent
                elif indent != nested_indent:
                    return None, f"unsupported nested frontmatter indentation on line {index + 2}"
                if nested_key in nested_keys:
                    return None, f"duplicate nested metadata key {nested_key!r}"
                if not nested_value.strip():
                    return None, f"nested metadata value must be a scalar on line {index + 2}"
                try:
                    _decode_scalar(nested_value)
                except ValueError:
                    return None, f"unsupported nested frontmatter value syntax on line {index + 2}"
                nested_keys.add(nested_key)
                index += 1
            data[key] = "<mapping>"
            continue
        try:
            data[key] = _decode_scalar(value)
        except ValueError as exc:
            return None, f"unsupported frontmatter scalar on line {index + 2}: {exc}"
        index += 1
    return data, ""


def find_relative_refs(text: str) -> set[str]:
    refs = set()
    for match in re.finditer(r"(?:`|\()((?:agents|assets|evals|references|scripts)/[^`)\s]+)", text):
        refs.add(match.group(1))
    return refs


def scan_privacy(path: Path, text: str, warnings: list[str]) -> None:
    for pattern in PRIVATE_PATTERNS:
        for match in pattern.finditer(text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            prefix = text[line_start:match.start()]
            if "re.compile(" in prefix:
                continue
            warnings.append(f"{path}: contains a machine-specific path pattern matching {pattern.pattern!r}")
            return


def validate_openai_yaml(path: Path, errors: list[str]) -> None:
    text = load_text(path)
    for required in ("display_name:", "short_description:", "default_prompt:"):
        if required not in text:
            errors.append(f"{path}: missing {required.rstrip(':')}")


def validate_evals(path: Path, errors: list[str]) -> None:
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
    with tempfile.TemporaryDirectory(prefix="skill-validator-pycache-") as cache_dir:
        for index, script in enumerate(scripts_dir.rglob("*.py")):
            try:
                py_compile.compile(
                    str(script),
                    cfile=str(Path(cache_dir) / f"{index}.pyc"),
                    doraise=True,
                )
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
        missing = {"name", "description"} - keys
        unsupported = keys - SUPPORTED_FRONTMATTER_KEYS
        if missing:
            errors.append(f"{skill_md}: missing required frontmatter fields {sorted(missing)}")
        if unsupported:
            errors.append(f"{skill_md}: unsupported frontmatter fields {sorted(unsupported)}")
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
        validate_evals(evals_json, errors)

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
        print(
            json.dumps(
                {
                    "skill_dir": str(skill_dir),
                    "validation_scope": "package_structure_and_deterministic_artifact_checks",
                    "behavior_evaluated": False,
                    "errors": errors,
                    "warnings": warnings,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
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
            print(
                f"{skill_dir}: structural package validation passed; "
                "this check does not evaluate skill behavior"
            )

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
