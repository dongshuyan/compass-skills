#!/usr/bin/env python3
"""Copy original inputs and normalize trusted text without fabricating extraction."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".rst"}
CONVERSION_EXTENSIONS = {".pdf", ".docx", ".doc", ".rtf", ".odt"}


def fail(message: str, code: int = 2, **details: Any) -> int:
    payload: dict[str, Any] = {"ok": False, "error": message}
    payload.update(details)
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    return code


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_regular_file(path: Path, label: str) -> Path:
    expanded = path.expanduser()
    if not expanded.exists() or not expanded.is_file():
        raise ValueError(f"{label} is not a regular file: {expanded}")
    return expanded.resolve(strict=True)


def read_trusted_text(path: Path, label: str) -> str:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        raise ValueError(f"{label} must be UTF-8 plain text or Markdown")
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError(f"{label} contains NUL bytes and is not safe plain text")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not valid UTF-8: {exc}") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip() + "\n" if text.strip() else ""


def copy_exclusive(source: Path, destination: Path) -> None:
    with source.open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())
    shutil.copystat(source, destination, follow_symlinks=True)
    destination.chmod(0o600)


def write_text_exclusive(destination: Path, text: str) -> None:
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy original resume/JD files into an existing case and normalize UTF-8 text. "
            "For PDF/DOC/DOCX/RTF/ODT, pass trusted upper-layer conversions with the "
            "corresponding --*-extracted-text option. Existing targets are never overwritten."
        )
    )
    parser.add_argument("--case-dir", required=True, type=Path, help="Case created by create_candidate_case.py")
    parser.add_argument("--resume", required=True, type=Path, help="Original resume file")
    parser.add_argument("--job-description", required=True, type=Path, help="Original job description file")
    parser.add_argument("--resume-extracted-text", type=Path, help="Trusted UTF-8 text/Markdown extracted from a non-text resume")
    parser.add_argument(
        "--job-description-extracted-text",
        type=Path,
        help="Trusted UTF-8 text/Markdown extracted from a non-text job description",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        case_dir = args.case_dir.expanduser().resolve(strict=True)
        if not case_dir.is_dir():
            raise ValueError("--case-dir is not a directory")
        input_dir = case_dir / "input"
        normalized_dir = case_dir / "normalized"
        audit_dir = case_dir / "audit"
        for required in (input_dir, normalized_dir, audit_dir):
            if not required.is_dir() or required.is_symlink():
                raise ValueError(f"invalid or missing case directory: {required}")

        sources = {
            "resume": require_regular_file(args.resume, "--resume"),
            "job_description": require_regular_file(args.job_description, "--job-description"),
        }
        extracted_args = {
            "resume": args.resume_extracted_text,
            "job_description": args.job_description_extracted_text,
        }
        if sources["resume"] == sources["job_description"]:
            raise ValueError("resume and job description must be different files")

        plan: dict[str, dict[str, Any]] = {}
        targets: list[Path] = [audit_dir / "input-normalization.json"]
        for kind, source in sources.items():
            extension = source.suffix.lower()
            original_target = input_dir / f"{kind.replace('_', '-')}-original{extension or '.bin'}"
            normalized_target = normalized_dir / f"{kind.replace('_', '-')}.md"
            targets.append(original_target)
            extracted_path: Path | None = None
            normalized_text: str | None = None
            method = "conversion_required"
            if extension in TEXT_EXTENSIONS:
                if extracted_args[kind] is not None:
                    raise ValueError(f"--{kind.replace('_', '-')}-extracted-text is unnecessary for a text original")
                normalized_text = read_trusted_text(source, kind)
                method = "direct_utf8_text"
                targets.append(normalized_target)
            elif extracted_args[kind] is not None:
                extracted_path = require_regular_file(extracted_args[kind], f"--{kind.replace('_', '-')}-extracted-text")
                normalized_text = read_trusted_text(extracted_path, f"{kind} extracted text")
                method = "trusted_upper_layer_conversion"
                targets.append(normalized_target)
            elif extension not in CONVERSION_EXTENSIONS:
                method = "unsupported_conversion_required"
            plan[kind] = {
                "source": source,
                "original_target": original_target,
                "normalized_target": normalized_target,
                "normalized_text": normalized_text,
                "extracted_path": extracted_path,
                "method": method,
            }

        existing = [str(path) for path in targets if path.exists() or path.is_symlink()]
        if existing:
            return fail("refusing to overwrite existing normalization outputs", 1, existing_targets=existing)

        records: dict[str, Any] = {}
        conversion_required: list[str] = []
        for kind, item in plan.items():
            source = item["source"]
            original_target = item["original_target"]
            copy_exclusive(source, original_target)
            source_hash = sha256_file(source)
            copied_hash = sha256_file(original_target)
            if source_hash != copied_hash:
                raise OSError(f"hash mismatch while copying {kind}")
            record: dict[str, Any] = {
                "original_filename": source.name,
                "stored_original": str(original_target.relative_to(case_dir)),
                "original_sha256": source_hash,
                "bytes": source.stat().st_size,
                "normalization_method": item["method"],
                "normalized_path": None,
                "normalized_sha256": None,
            }
            if item["normalized_text"] is not None:
                write_text_exclusive(item["normalized_target"], item["normalized_text"])
                record["normalized_path"] = str(item["normalized_target"].relative_to(case_dir))
                record["normalized_sha256"] = sha256_file(item["normalized_target"])
                if item["extracted_path"] is not None:
                    record["extracted_text_sha256"] = sha256_file(item["extracted_path"])
            else:
                conversion_required.append(kind)
            records[kind] = record

        manifest = {
            "schema_version": "1.0",
            "normalized_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "needs_conversion" if conversion_required else "complete",
            "conversion_required": conversion_required,
            "inputs": records,
        }
        manifest_target = audit_dir / "input-normalization.json"
        write_text_exclusive(manifest_target, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        payload = {"ok": not conversion_required, "status": manifest["status"], "manifest": str(manifest_target)}
        if conversion_required:
            payload["conversion_required"] = conversion_required
            payload["instruction"] = "Use an approved PDF/DOCX extraction tool, then rerun in a fresh case with --*-extracted-text."
            print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
            return 3
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        return fail(str(exc), 1)


if __name__ == "__main__":
    raise SystemExit(main())
