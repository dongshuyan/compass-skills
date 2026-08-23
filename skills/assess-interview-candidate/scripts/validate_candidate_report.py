#!/usr/bin/env python3
"""Validate the simplified offline interviewer report and interaction contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from render_candidate_report import safe_filename_component
from validate_case_contract import loads_strict
from validate_interviewer_report_data import validate_interviewer_report_data


DATA_PLACEHOLDER = "__INTERVIEWER_REPORT_DATA_JSON__"
TITLE_PLACEHOLDER = "__REPORT_TITLE_HTML__"
REQUIRED_IDS = {
    "report-root",
    "report-title",
    "interviewer-report-data",
    "candidate-overview",
    "resume-risks",
    "interview-questions",
    "export-state",
    "reset-state",
    "storage-status",
}
FORBIDDEN_OLD_IDS = {
    "assessment-root",
    "assessment-data",
    "resume-evidence-score",
    "interview-score",
    "core-interview-score",
    "coverage",
    "core-coverage",
    "gate-status",
    "comparability",
    "behavioral-hypotheses",
    "source-ledger",
}
REQUIRED_INTERACTION_MARKERS = {
    "localStorage",
    "loadState",
    "saveState",
    "applyDefaultHighlight",
    "exportInterviewState",
    "resetInterviewState",
}
NETWORK_JS = {
    "fetch()": re.compile(r"\bfetch\s*\(", re.I),
    "XMLHttpRequest": re.compile(r"\bXMLHttpRequest\b", re.I),
    "WebSocket": re.compile(r"\bWebSocket\s*\(", re.I),
    "EventSource": re.compile(r"\bEventSource\s*\(", re.I),
    "dynamic import": re.compile(r"\bimport\s*\(", re.I),
}


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.non_embedded_dependencies: list[str] = []
        self.meta_refresh = False
        self.executable_scripts: list[str] = []
        self.report_data: list[str] = []
        self.report_data_script_count = 0
        self.styles: list[str] = []
        self.titles: list[str] = []
        self.h1_text: list[str] = []
        self.report_section_count = 0
        self._inside_executable_script = False
        self._inside_report_data = False
        self._inside_style = False
        self._inside_title = False
        self._inside_report_h1 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        tag = tag.lower()
        classes = set(attributes.get("class", "").split())
        if tag == "section" and "report-section" in classes:
            self.report_section_count += 1
        resource_attributes = {
            "script": "src",
            "link": "href",
            "img": "src",
            "source": "src",
            "audio": "src",
            "video": "src",
            "iframe": "src",
            "embed": "src",
            "object": "data",
        }
        attribute = resource_attributes.get(tag)
        if attribute:
            value = attributes.get(attribute, "").strip()
            if value and not value.startswith("data:"):
                self.non_embedded_dependencies.append(f"<{tag} {attribute}={value!r}>")
        if tag == "meta" and attributes.get("http-equiv", "").lower() == "refresh":
            self.meta_refresh = True
        if tag == "script":
            script_type = attributes.get("type", "").strip().lower()
            self._inside_executable_script = script_type in {"", "text/javascript", "application/javascript", "module"}
            self._inside_report_data = script_type == "application/json" and attributes.get("id") == "interviewer-report-data"
            if self._inside_report_data:
                self.report_data_script_count += 1
        elif tag == "style":
            self._inside_style = True
        elif tag == "title":
            self._inside_title = True
        elif tag == "h1" and attributes.get("id") == "report-title":
            self._inside_report_h1 = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script":
            self._inside_executable_script = False
            self._inside_report_data = False
        elif tag.lower() == "style":
            self._inside_style = False
        elif tag.lower() == "title":
            self._inside_title = False
        elif tag.lower() == "h1":
            self._inside_report_h1 = False

    def handle_data(self, data: str) -> None:
        if self._inside_report_data:
            self.report_data.append(data)
        elif self._inside_executable_script:
            self.executable_scripts.append(data)
        elif self._inside_style:
            self.styles.append(data)
        elif self._inside_title:
            self.titles.append(data)
        elif self._inside_report_h1:
            self.h1_text.append(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate simplified report structure, embedded data, offline persistence, and highlighting controls.")
    parser.add_argument("report", type=Path, help="Rendered candidate interview HTML")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        path = args.report.expanduser().resolve(strict=True)
        text = path.read_text(encoding="utf-8")
        parser = ReportParser()
        parser.feed(text)
        errors: list[str] = []
        warnings: list[str] = []
        if DATA_PLACEHOLDER in text or TITLE_PLACEHOLDER in text:
            errors.append("report template placeholder remains")
        missing_ids = sorted(REQUIRED_IDS - parser.ids)
        if missing_ids:
            errors.append(f"missing required element ids: {', '.join(missing_ids)}")
        forbidden_ids = sorted(FORBIDDEN_OLD_IDS & parser.ids)
        if forbidden_ids:
            errors.append(f"obsolete detailed-report element ids remain: {', '.join(forbidden_ids)}")
        if parser.report_section_count != 3:
            errors.append(f"report must contain exactly three main report sections; found {parser.report_section_count}")
        for marker in sorted(REQUIRED_INTERACTION_MARKERS):
            if marker not in text:
                errors.append(f"missing offline interaction marker: {marker}")
        if parser.non_embedded_dependencies:
            errors.append("non-embedded runtime dependencies found: " + "; ".join(parser.non_embedded_dependencies))
        if parser.meta_refresh:
            errors.append("meta refresh is forbidden")
        if parser.report_data_script_count != 1:
            errors.append(f"report must contain exactly one interviewer-report-data JSON script; found {parser.report_data_script_count}")
        embedded = "".join(parser.report_data).strip()
        report_data: dict[str, Any] | None = None
        if parser.report_data_script_count == 1:
            try:
                value = loads_strict(embedded)
                if not isinstance(value, dict):
                    errors.append("embedded interviewer-report-data must be a JSON object")
                else:
                    report_data = value
                    contract_errors, contract_warnings = validate_interviewer_report_data(report_data)
                    errors.extend("embedded interviewer-report-data: " + item for item in contract_errors)
                    warnings.extend(contract_warnings)
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(f"embedded interviewer-report-data is not strict JSON: {exc}")
        if report_data is not None:
            candidate_name = report_data["case"]["candidate_name"]
            expected_title = f"{candidate_name}｜候选人评估与面试报告"
            title_text = "".join(parser.titles).strip()
            h1_text = "".join(parser.h1_text).strip()
            if title_text != expected_title:
                errors.append(f"document title must equal {expected_title!r}")
            if h1_text != expected_title:
                errors.append(f"page heading must equal {expected_title!r}")
            safe_name = safe_filename_component(candidate_name)
            if safe_name not in path.stem:
                errors.append(f"report filename must contain candidate name {safe_name!r}")
        executable_javascript = "\n".join(parser.executable_scripts)
        inline_css = "\n".join(parser.styles)
        if re.search(r"url\s*\(\s*['\"]?\s*(?!data:|#)[^)]+", inline_css, re.I):
            errors.append("non-embedded CSS url() dependency found")
        for label, pattern in NETWORK_JS.items():
            if pattern.search(executable_javascript):
                errors.append(f"network-capable JavaScript is forbidden in offline report: {label}")
        payload: dict[str, Any] = {
            "ok": not errors,
            "report": str(path),
            "bytes": path.stat().st_size,
            "required_ids": sorted(REQUIRED_IDS),
            "errors": errors,
            "warnings": warnings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    except (OSError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
