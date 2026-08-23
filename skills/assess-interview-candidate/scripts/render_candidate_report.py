#!/usr/bin/env python3
"""Render minimal interviewer-report JSON into a self-contained HTML file."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from validate_case_contract import loads_strict
from validate_interviewer_report_data import validate_interviewer_report_data


DATA_PLACEHOLDER = "__INTERVIEWER_REPORT_DATA_JSON__"
TITLE_PLACEHOLDER = "__REPORT_TITLE_HTML__"
DEFAULT_TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "candidate-assessment-template.html"
WINDOWS_RESERVED_BASENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely embed interviewer-report JSON into the offline HTML template. Existing output is preserved unless --force is explicit."
    )
    parser.add_argument(
        "--data",
        dest="report_data",
        required=True,
        type=Path,
        help="Simplified interviewer-report-data JSON object",
    )
    parser.add_argument("--output", required=True, type=Path, help="Destination .html file")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="Bundled simplified report template")
    parser.add_argument("--force", action="store_true", help="Explicitly replace an existing output file")
    return parser.parse_args()


def safe_json_for_script(value: dict[str, Any]) -> str:
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return (
        serialized.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def safe_filename_component(value: str) -> str:
    """Return a portable filename fragment while preserving readable names."""
    cleaned = re.sub(r"[\x00-\x1f/\\:*?\"<>|]+", "_", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        raise ValueError("candidate name cannot be converted to a safe filename component")
    if cleaned.split(".", 1)[0].upper() in WINDOWS_RESERVED_BASENAMES:
        cleaned = "_" + cleaned
    return cleaned


def write_exclusive(path: Path, content: str, force: bool) -> None:
    if not path.parent.is_dir():
        raise ValueError(f"output parent does not exist: {path.parent}")
    if path.is_symlink():
        raise ValueError(f"refusing to write through symbolic link: {path}")
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing output: {path}")
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if force else os.O_EXCL)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    args = parse_args()
    try:
        report_data = loads_strict(args.report_data.expanduser().read_text(encoding="utf-8"))
        if not isinstance(report_data, dict):
            raise ValueError("interviewer report JSON must contain an object")
        contract_errors, contract_warnings = validate_interviewer_report_data(report_data)
        if contract_errors:
            raise ValueError("interviewer report contract invalid: " + " | ".join(contract_errors))
        template = args.template.expanduser().read_text(encoding="utf-8")
        data_occurrences = template.count(DATA_PLACEHOLDER)
        title_occurrences = template.count(TITLE_PLACEHOLDER)
        if data_occurrences != 1:
            raise ValueError(f"template must contain exactly one {DATA_PLACEHOLDER}; found {data_occurrences}")
        if title_occurrences != 2:
            raise ValueError(f"template must contain exactly two {TITLE_PLACEHOLDER}; found {title_occurrences}")

        output = args.output.expanduser()
        if output.suffix.lower() != ".html":
            raise ValueError("--output must use the .html extension")
        candidate_name = report_data["case"]["candidate_name"]
        safe_name = safe_filename_component(candidate_name)
        if safe_name not in output.stem:
            raise ValueError(
                f"--output filename must contain candidate name {safe_name!r}; "
                f"recommended: {safe_name}-候选人评估与面试报告.html"
            )
        report_title = f"{candidate_name}｜候选人评估与面试报告"
        rendered = template.replace(DATA_PLACEHOLDER, safe_json_for_script(report_data))
        rendered = rendered.replace(TITLE_PLACEHOLDER, html.escape(report_title, quote=True))
        write_exclusive(output, rendered, args.force)
        print(json.dumps({
            "ok": True,
            "output": str(output.resolve()),
            "candidate_name": candidate_name,
            "bytes": output.stat().st_size,
            "warnings": contract_warnings,
        }, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
