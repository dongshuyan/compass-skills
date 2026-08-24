#!/usr/bin/env python3
"""Behavior tests for resume-photo display and timeline age estimation."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
TESTS_DIR = Path(__file__).resolve().parent
NO_BYTECODE_ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from test_interviewer_report import not_provided, sample_report_data  # noqa: E402
from derive_timeline_age import calculate_timeline_age_range  # noqa: E402
from validate_interviewer_report_data import validate_interviewer_report_data  # noqa: E402


JPEG_WITH_METADATA = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAASABIAAD/4QBMRXhpZgAATU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAAA6ABAAMAAAABAAEAAKAC"
    "AAQAAAABAAAAYKADAAQAAAABAAAAgAAAAAD/7QA4UGhvdG9zaG9wIDMuMAA4QklNBAQAAAAAAAA4QklNBCUAAAAAABDUHYzZ"
    "jwCyBOmACZjs+EJ+/8AAEQgAgABgAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAAAAAAAAABAgMEBQYHCAkKC//EALUQAAIB"
    "AwMCBAMFBQQEAAABfQECAwAEEQUSITFBBhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nzg5OkNE"
    "RUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfI"
    "ycrS09TV1tfY2drh4uPk5ebn6Onq8fLz9PX29/j5+v/EAB8BAAMBAQEBAQEBAQEAAAAAAAABAgMEBQYHCAkKC//EALURAAIB"
    "AgQEAwQHBQQEAAECdwABAgMRBAUhMQYSQVEHYXETIjKBCBRCkaGxwQkjM1LwFWJy0QoWJDThJfEXGBkaJicoKSo1Njc4OTpD"
    "REVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoKDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXG"
    "x8jJytLT1NXW19jZ2uLj5OXm5+jp6vLz9PX29/j5+v/bAEMAAgICAgICAwICAwUDAwMFBgUFBQUGCAYGBgYGCAoICAgICAgK"
    "CgoKCgoKCgwMDAwMDA4ODg4ODw8PDw8PDw8PD//bAEMBAgICBAQEBwQEBxALCQsQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQ"
    "EBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEP/dAAQABv/aAAwDAQACEQMRAD8AKKKKACiiigAooooAKKKKACiiigAooooA/9Ao"
    "oooAKKKKACiiigAooooAKKKKACiiigD/0SiiigAooooAKKKKACiiigAooooAKKKKAP/SKKKKACiiigAooooAKKKKACiiigAo"
    "oooA/9MooooAKKKKACiiigAooooAKKKKACiiigD/1CiiigAooooAKKKKACiiigAooooAKKKKAP/VKKKKACiiigAooooAKKKK"
    "ACiiigAooooA/9YooooAKKKKACiiigAooooAKKKKACiiigD/2Q=="
)


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def png_bytes(width: int = 96, height: int = 128) -> bytes:
    """Return a small standards-compliant RGB PNG without external libraries."""

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + (b"\x80\x80\x80" * width)
    pixels = zlib.compress(row * height)
    return signature + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", pixels) + png_chunk(b"IEND", b"")


def png_with_private_metadata_and_trailing_bytes() -> bytes:
    raw = png_bytes()
    iend_offset = raw.index(b"\x00\x00\x00\x00IEND")
    metadata = png_chunk(b"tEXt", b"contact\x00private-person@example.com")
    return raw[:iend_offset] + metadata + raw[iend_offset:] + b"private-tail@example.com"


def truncated_png(width: int = 96, height: int = 128) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return signature + png_chunk(b"IHDR", ihdr)


def png_with_invalid_compressed_data(width: int = 96, height: int = 128) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        signature
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", b"not-a-zlib-stream")
        + png_chunk(b"IEND", b"")
    )


def png_with_huge_declared_dimensions() -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 0xFFFFFFFF, 0xFFFFFFFF, 8, 2, 0, 0, 0)
    return (
        signature
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(b"\x00"))
        + png_chunk(b"IEND", b"")
    )


def jpeg_without_pixel_data() -> bytes:
    frame = b"\x00\x0b\x08\x00\x60\x00\x60\x01\x01\x11\x00"
    scan = b"\x00\x08\x01\x01\x00\x00\x3f\x00"
    return b"\xff\xd8\xff\xc0" + frame + b"\xff\xda" + scan + b"\xff\xd9"


def write_canonical_resume_pdf(root: Path, raw: bytes = b"%PDF-1.4\n%%EOF\n") -> Path:
    input_dir = root / "input"
    input_dir.mkdir()
    resume_path = input_dir / "resume-original.pdf"
    resume_path.write_bytes(raw)
    return resume_path


def no_candidate_photo() -> dict[str, object]:
    return {
        "status": "not_present",
        "data_uri": None,
        "mime_type": None,
        "byte_length": None,
        "pixel_width": None,
        "pixel_height": None,
        "sha256": None,
        "provenance": None,
    }


def included_candidate_photo() -> dict[str, object]:
    raw = png_bytes()
    return {
        "status": "included",
        "data_uri": "data:image/png;base64," + base64.b64encode(raw).decode("ascii"),
        "mime_type": "image/png",
        "byte_length": len(raw),
        "pixel_width": 96,
        "pixel_height": 128,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "provenance": {
            "source_kind": "resume_pdf",
            "source_document": "input/resume-original.pdf",
            "source_document_sha256": "a" * 64,
            "page": 1,
            "extraction_method": "embedded_image",
            "image_index": 3,
            "crop_box": None,
        },
    }


def unavailable_candidate_photo(status: str = "ambiguous") -> dict[str, object]:
    value = no_candidate_photo()
    value.update(
        {
            "status": status,
            "provenance": {
                "source_kind": "resume_pdf",
                "source_document": "input/resume-original.pdf",
                "source_document_sha256": "b" * 64,
                "page": 1,
                "extraction_method": "not_completed",
                "image_index": None,
                "crop_box": None,
            },
        }
    )
    return value


def no_timeline_estimate() -> dict[str, object]:
    return {
        "status": "not_needed",
        "display": "候选人已提供出生信息，不进行履历年龄推算",
        "as_of": "2026-08-23",
        "min_years": None,
        "max_years": None,
        "anchor": None,
        "assumptions": {
            "undergraduate_start_age_min": 16,
            "undergraduate_start_age_typical": 18,
            "undergraduate_start_age_max": 20,
        },
        "consistency_status": "not_checked",
        "consistency_checks": [],
    }


def estimated_from_undergraduate_start(start: str = "2012") -> dict[str, object]:
    min_years, max_years = (29, 34) if start == "2012" else (29, 33)
    precision = "year" if len(start) == 4 else "month"
    return {
        "status": "estimated",
        "display": f"约{min_years}–{max_years}岁（按{start}本科入学、入学年龄18±2岁推算；非候选人自述）",
        "as_of": "2026-08-23",
        "min_years": min_years,
        "max_years": max_years,
        "anchor": {
            "kind": "undergraduate_start",
            "start": start,
            "precision": precision,
            "source_locators": ["normalized/resume.md：教育背景"],
            "graduation_date": None,
            "degree_duration_years": None,
        },
        "assumptions": {
            "undergraduate_start_age_min": 16,
            "undergraduate_start_age_typical": 18,
            "undergraduate_start_age_max": 20,
        },
        "consistency_status": "not_checked",
        "consistency_checks": [],
    }


def report_with_enrichment() -> dict[str, object]:
    data = copy.deepcopy(sample_report_data())
    overview = data["candidate_overview"]
    overview["candidate_photo"] = no_candidate_photo()
    overview["timeline_age_estimate"] = no_timeline_estimate()
    return data


def clear_birth_information(data: dict[str, object]) -> None:
    personal = data["candidate_overview"]["personal_info"]
    personal["birth_information"] = not_provided()
    personal["age"] = {
        "display": "未提供",
        "years": None,
        "approximate": False,
        "as_of": "2026-08-23",
        "normalized_birth": None,
        "precision": "not_provided",
        "source_status": "not_provided",
        "source_locator": None,
    }


class EnrichmentContractTests(unittest.TestCase):
    def test_v11_accepts_photo_and_timeline_as_overview_siblings(self) -> None:
        data = report_with_enrichment()
        errors, warnings = validate_interviewer_report_data(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_v11_rejects_legacy_enrichment_inside_candidate_provided_facts(self) -> None:
        data = report_with_enrichment()
        data["candidate_overview"]["personal_info"]["photo"] = no_candidate_photo()
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("personal_info" in error and "photo" in error for error in errors), errors)

    def test_v10_cannot_bypass_enrichment_validation_with_v11_fields(self) -> None:
        data = report_with_enrichment()
        data["schema_version"] = "1.0.0"
        data["candidate_overview"]["candidate_photo"] = included_candidate_photo()
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("forbidden schema" in error for error in errors), errors)

    def test_clear_resume_photo_with_structured_pdf_provenance_is_valid(self) -> None:
        data = report_with_enrichment()
        data["candidate_overview"]["candidate_photo"] = included_candidate_photo()
        errors, _ = validate_interviewer_report_data(data)
        self.assertEqual([], errors)

    def test_non_resume_photo_provenance_is_rejected(self) -> None:
        data = report_with_enrichment()
        photo = included_candidate_photo()
        photo["provenance"]["source_kind"] = "public_profile"
        data["candidate_overview"]["candidate_photo"] = photo
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("source_kind" in error for error in errors), errors)

    def test_ambiguous_resume_photo_is_recorded_without_image_payload(self) -> None:
        data = report_with_enrichment()
        data["candidate_overview"]["candidate_photo"] = unavailable_candidate_photo()
        errors, _ = validate_interviewer_report_data(data)
        self.assertEqual([], errors)

    def test_ambiguous_resume_photo_cannot_carry_image_bytes(self) -> None:
        data = report_with_enrichment()
        photo = unavailable_candidate_photo()
        photo["data_uri"] = included_candidate_photo()["data_uri"]
        data["candidate_overview"]["candidate_photo"] = photo
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("non-included photo" in error for error in errors), errors)

    def test_birth_information_takes_precedence_over_timeline_estimate(self) -> None:
        data = report_with_enrichment()
        data["candidate_overview"]["timeline_age_estimate"] = estimated_from_undergraduate_start()
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("not_needed" in error or "birth information" in error for error in errors), errors)

    def test_year_only_undergraduate_start_uses_conservative_date_uncertainty(self) -> None:
        data = report_with_enrichment()
        clear_birth_information(data)
        data["candidate_overview"]["timeline_age_estimate"] = estimated_from_undergraduate_start("2012")
        errors, _ = validate_interviewer_report_data(data)
        self.assertEqual([], errors)

    def test_month_undergraduate_start_uses_month_precision(self) -> None:
        data = report_with_enrichment()
        clear_birth_information(data)
        data["candidate_overview"]["timeline_age_estimate"] = estimated_from_undergraduate_start("2012-09")
        errors, _ = validate_interviewer_report_data(data)
        self.assertEqual([], errors)

    def test_timeline_conflict_retains_anchor_and_sources_without_numeric_range(self) -> None:
        data = report_with_enrichment()
        clear_birth_information(data)
        estimate = estimated_from_undergraduate_start("2012")
        estimate.update(
            {
                "status": "timeline_conflict",
                "display": "履历时间存在冲突，无法可靠推算年龄区间",
                "min_years": None,
                "max_years": None,
                "consistency_status": "conflict",
                "consistency_checks": [
                    {
                        "event": "employment_start",
                        "date": "2010",
                        "precision": "year",
                        "source_locator": "normalized/resume.md：工作经历",
                    }
                ],
            }
        )
        data["candidate_overview"]["timeline_age_estimate"] = estimate
        errors, _ = validate_interviewer_report_data(data)
        self.assertEqual([], errors)

    def test_inferred_age_is_rejected_from_a_rated_decision_path(self) -> None:
        data = report_with_enrichment()
        clear_birth_information(data)
        data["candidate_overview"]["timeline_age_estimate"] = estimated_from_undergraduate_start()
        data["interview_questions"][0]["good_answer"] = "年龄在29至34岁区间可以加分。"
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("interview_questions[0]" in error and "年龄" in error for error in errors), errors)

    def test_candidate_photo_cannot_be_a_job_fit_signal(self) -> None:
        data = report_with_enrichment()
        data["candidate_overview"]["fit_items"][0]["summary"] = "候选人照片形象专业，可作为岗位匹配加分项。"
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("fit_items[0]" in error and "照片" in error for error in errors), errors)

    def test_numeric_age_range_cannot_be_a_rating_signal(self) -> None:
        data = report_with_enrichment()
        data["interview_questions"][0]["good_answer"] = "29–34岁可以加分。"
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("interview_questions[0]" in error and "岁" in error for error in errors), errors)

    def test_young_or_old_language_cannot_be_a_rating_signal(self) -> None:
        data = report_with_enrichment()
        data["interview_questions"][0]["good_answer"] = "看起来年轻者可以加分。"
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("interview_questions[0]" in error and "年轻" in error for error in errors), errors)

    def test_unqualified_photo_appearance_language_cannot_be_a_rating_signal(self) -> None:
        for phrase, expected_label in (
            ("照片好看可以加分。", "照片"),
            ("Professional appearance is preferred.", "photo"),
        ):
            with self.subTest(phrase=phrase):
                data = report_with_enrichment()
                data["interview_questions"][0]["good_answer"] = phrase
                errors, _ = validate_interviewer_report_data(data)
                self.assertTrue(
                    any("interview_questions[0]" in error and expected_label in error.lower() for error in errors),
                    errors,
                )

    def test_age_cohort_language_cannot_be_a_rating_signal(self) -> None:
        data = report_with_enrichment()
        data["interview_questions"][0]["good_answer"] = "95后可以加分。"
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("interview_questions[0]" in error and "年龄段" in error for error in errors), errors)

    def test_english_age_or_candidate_photo_language_cannot_enter_scoring(self) -> None:
        for phrase, expected_label in (
            ("Candidate photo should improve the score.", "photo"),
            ("Age 29 to 34 is preferred.", "age"),
        ):
            with self.subTest(phrase=phrase):
                data = report_with_enrichment()
                data["interview_questions"][0]["good_answer"] = phrase
                errors, _ = validate_interviewer_report_data(data)
                self.assertTrue(
                    any("interview_questions[0]" in error and expected_label in error.lower() for error in errors),
                    errors,
                )

    def test_additional_age_and_appearance_scoring_variants_are_rejected(self) -> None:
        phrases = (
            "年纪较轻者可以加分。",
            "30周岁以下优先。",
            "三十岁以下优先。",
            "Younger candidates should receive a higher score.",
            "Applicants aged 29–34 are preferred.",
            "Applicants under 35 are preferred.",
            "A polished headshot is a positive signal.",
            "A youthful look is a positive signal.",
            "Under-35 applicants are preferred.",
            "Applicants younger than 35 are preferred.",
            "Attractive candidates should receive a higher score.",
            "未满三十者优先。",
            "外形出众者可以加分。",
            "外貌应作为 UI 岗位加分项。",
            "Good looks should count when evaluating UI developers.",
            "She is attractive and should receive a higher score.",
            "He looks attractive, so this is a positive signal.",
            "她很漂亮，可以加分。",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                data = report_with_enrichment()
                data["interview_questions"][0]["good_answer"] = phrase
                errors, _ = validate_interviewer_report_data(data)
                self.assertTrue(any("interview_questions[0]" in error for error in errors), errors)

    def test_technical_uses_of_looks_are_not_misclassified_as_appearance(self) -> None:
        phrases = (
            "The candidate's architecture looks robust.",
            "The dashboard has a professional appearance and clear information hierarchy.",
            "The UI has a polished look and handles responsive breakpoints correctly.",
            "候选人设计的界面很好看，信息层级清晰。",
            "The function looks correct and handles empty input.",
            "The database schema looks normalized and supports the required queries.",
            "The test output looks correct for the failure case.",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                data = report_with_enrichment()
                data["interview_questions"][0]["good_answer"] = phrase
                errors, _ = validate_interviewer_report_data(data)
                self.assertEqual([], errors)


class PhotoPreparationScriptTests(unittest.TestCase):
    def test_helper_records_image_and_source_pdf_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.png"
            resume_path = write_canonical_resume_pdf(root)
            raw = png_bytes()
            image_path.write_bytes(raw)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "3",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(len(raw), payload["byte_length"])
        self.assertEqual([96, 128], [payload["pixel_width"], payload["pixel_height"]])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), payload["sha256"])
        self.assertEqual("resume_pdf", payload["provenance"]["source_kind"])
        self.assertEqual(hashlib.sha256(b"%PDF-1.4\n%%EOF\n").hexdigest(), payload["provenance"]["source_document_sha256"])

    def test_helper_rejects_unreasonably_large_pixel_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.png"
            resume_path = write_canonical_resume_pdf(root)
            image_path.write_bytes(png_bytes(5000, 2))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "page_crop",
                    "--crop-box",
                    "10,20,200,260",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("dimensions", completed.stderr)

    def test_helper_rejects_too_small_portrait_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.png"
            resume_path = write_canonical_resume_pdf(root)
            image_path.write_bytes(png_bytes(32, 64))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("dimensions", completed.stderr)

    def test_helper_rejects_image_files_over_two_megabytes_before_embedding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.png"
            resume_path = write_canonical_resume_pdf(root)
            image_path.write_bytes(png_bytes() + (b"0" * (2 * 1024 * 1024)))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("byte limit", completed.stderr)

    def test_helper_rejects_locator_fields_for_the_wrong_extraction_method(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.png"
            resume_path = write_canonical_resume_pdf(root)
            image_path.write_bytes(png_bytes())
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "0",
                    "--crop-box",
                    "10,20,100,120",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("must not include --crop-box", completed.stderr)

    def test_helper_rejects_a_non_pdf_provenance_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.png"
            resume_path = write_canonical_resume_pdf(root, b"not a PDF")
            image_path.write_bytes(png_bytes())
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("PDF header", completed.stderr)

    def test_helper_sanitizes_png_metadata_and_trailing_bytes_before_embedding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.png"
            resume_path = write_canonical_resume_pdf(root)
            raw = png_with_private_metadata_and_trailing_bytes()
            image_path.write_bytes(raw)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        sanitized = base64.b64decode(payload["data_uri"].split(",", 1)[1])
        self.assertNotIn(b"private-person@example.com", sanitized)
        self.assertNotIn(b"private-tail@example.com", sanitized)
        self.assertLess(len(sanitized), len(raw))
        self.assertEqual(hashlib.sha256(sanitized).hexdigest(), payload["sha256"])

    def test_helper_rejects_truncated_png_without_image_data_or_end_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.png"
            resume_path = write_canonical_resume_pdf(root)
            image_path.write_bytes(truncated_png())
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("PNG", completed.stderr)

    def test_helper_reports_invalid_png_compression_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.png"
            resume_path = write_canonical_resume_pdf(root)
            image_path.write_bytes(png_with_invalid_compressed_data())
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("PNG image data", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_helper_requires_jpeg_to_be_converted_to_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.jpg"
            resume_path = write_canonical_resume_pdf(root)
            image_path.write_bytes(JPEG_WITH_METADATA + b"private-tail@example.com")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("PNG", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_helper_rejects_structural_jpeg_without_pixel_data_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.jpg"
            resume_path = write_canonical_resume_pdf(root)
            image_path.write_bytes(jpeg_without_pixel_data())
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("PNG", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_helper_rejects_huge_png_dimensions_before_decompression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.png"
            resume_path = write_canonical_resume_pdf(root)
            image_path.write_bytes(png_with_huge_declared_dimensions())
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("dimensions", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_validator_rejects_unsanitized_png_payload(self) -> None:
        data = report_with_enrichment()
        raw = png_with_private_metadata_and_trailing_bytes()
        photo = included_candidate_photo()
        photo.update(
            {
                "data_uri": "data:image/png;base64," + base64.b64encode(raw).decode("ascii"),
                "byte_length": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        data["candidate_overview"]["candidate_photo"] = photo
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("candidate_photo" in error and "sanitized" in error for error in errors), errors)

    def test_helper_rejects_noncanonical_resume_pdf_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "portrait.png"
            resume_path = root / "resume.pdf"
            image_path.write_bytes(png_bytes())
            resume_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "prepare_candidate_photo.py"),
                    "--input",
                    str(image_path),
                    "--resume-pdf",
                    str(resume_path),
                    "--page",
                    "1",
                    "--extraction-method",
                    "embedded_image",
                    "--image-index",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=NO_BYTECODE_ENV,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("input/resume-original.pdf", completed.stderr)


class TimelineAgeScriptTests(unittest.TestCase):
    def test_cli_derives_year_precision_range(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "derive_timeline_age.py"),
                "--report-date",
                "2026-08-23",
                "--undergraduate-start",
                "2012",
                "--source-locator",
                "normalized/resume.md：教育背景",
            ],
            text=True,
            capture_output=True,
            check=False,
            env=NO_BYTECODE_ENV,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual([29, 34], [payload["min_years"], payload["max_years"]])
        self.assertEqual("year", payload["anchor"]["precision"])

    def test_exact_start_date_has_no_calendar_precision_padding(self) -> None:
        minimum, maximum, precision = calculate_timeline_age_range("2012-09-01", "2026-08-23")
        self.assertEqual((29, 33, "day"), (minimum, maximum, precision))

    def test_cli_can_derive_start_from_explicit_graduation_and_duration(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "derive_timeline_age.py"),
                "--report-date",
                "2026-08-23",
                "--undergraduate-graduation",
                "2016-06",
                "--degree-duration-years",
                "4",
                "--source-locator",
                "normalized/resume.md：教育背景",
            ],
            text=True,
            capture_output=True,
            check=False,
            env=NO_BYTECODE_ENV,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("2012", payload["anchor"]["start"])
        self.assertEqual("year", payload["anchor"]["precision"])
        self.assertEqual("undergraduate_start_derived_from_graduation_and_duration", payload["anchor"]["kind"])

    def test_graduation_fallback_requires_explicit_degree_duration(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "derive_timeline_age.py"),
                "--report-date",
                "2026-08-23",
                "--undergraduate-graduation",
                "2016",
                "--source-locator",
                "normalized/resume.md：教育背景",
            ],
            text=True,
            capture_output=True,
            check=False,
            env=NO_BYTECODE_ENV,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("both graduation date and explicit degree duration", completed.stderr)

    def test_cli_turns_a_contradictory_later_event_into_timeline_conflict(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "derive_timeline_age.py"),
                "--report-date",
                "2026-08-23",
                "--undergraduate-start",
                "2012",
                "--source-locator",
                "normalized/resume.md：教育背景",
                "--consistency-check-json",
                json.dumps(
                    {
                        "event": "employment_start",
                        "date": "2010",
                        "source_locator": "normalized/resume.md：工作经历",
                    },
                    ensure_ascii=False,
                ),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=NO_BYTECODE_ENV,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("timeline_conflict", payload["status"])
        self.assertEqual("conflict", payload["consistency_status"])
        self.assertIsNone(payload["min_years"])
        self.assertEqual("year", payload["consistency_checks"][0]["precision"])


class TemplateLayoutTests(unittest.TestCase):
    def test_photo_column_is_opt_in_instead_of_reserved_when_hidden(self) -> None:
        template = (SKILL_DIR / "assets" / "candidate-assessment-template.html").read_text(encoding="utf-8")
        self.assertIn(".overview-header.has-photo", template)
        self.assertIn('if (photoIncluded) overviewHeader.classList.add("has-photo")', template)
        self.assertNotIn("append(overviewHeader, photoPanel, infoGrid)", template)


if __name__ == "__main__":
    unittest.main()
