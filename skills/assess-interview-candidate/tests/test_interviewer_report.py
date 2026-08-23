#!/usr/bin/env python3
"""Behavior tests for the simplified interviewer-facing report."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
NO_BYTECODE_ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_interviewer_report_data import validate_interviewer_report_data  # noqa: E402


def provided(value: str, locator: str = "normalized/resume.md：基本信息") -> dict[str, str]:
    return {
        "value": value,
        "source_status": "candidate_provided",
        "source_locator": locator,
    }


def not_provided() -> dict[str, str | None]:
    return {
        "value": "未提供",
        "source_status": "not_provided",
        "source_locator": None,
    }


def rated_question(index: int) -> dict[str, object]:
    return {
        "id": f"q-{index:02d}",
        "order": index,
        "priority": "must_ask" if index <= 4 else "recommended",
        "kind": "job_core" if index <= 4 else "resume_check",
        "question": f"这是第 {index} 道可以直接照读的问题吗？",
        "purpose": "核验与目标岗位直接相关的可观察能力。",
        "evaluation_mode": "rated",
        "good_answer": "能说明本人行动、约束、结果和验证方法。",
        "average_answer": "能说明做过相关工作，但个人边界或验证不够完整。",
        "poor_answer": "只罗列术语或团队结果，无法说明本人行动。",
        "bonus_signals": ["主动说明失败和修正过程"],
        "penalty_signals": ["把未验证结果当作已经完成"],
    }


def sample_report_data() -> dict[str, object]:
    questions = [rated_question(index) for index in range(1, 11)]
    questions[1]["kind"] = "work_sample"
    questions[2]["kind"] = "soft_skill"
    questions.append(
        {
            "id": "q-11",
            "order": 11,
            "priority": "recommended",
            "kind": "logistics",
            "question": "你目前常住在哪个城市，现场办公、搬迁和到岗时间分别有什么安排？",
            "purpose": "确认双方实际工作安排是否一致，不用于判断人格或稳定性。",
            "evaluation_mode": "record_only",
            "recording_guidance": "如实记录地点、到岗和现场办公条件；不设好坏，不加分、不扣分。",
        }
    )
    questions.append(
        {
            "id": "q-12",
            "order": 12,
            "priority": "optional",
            "kind": "candidate_choice",
            "question": "方便说明一下你的婚姻状况吗？如果不方便，可以不回答。",
            "purpose": "记录候选人自愿补充的信息；是否提问由面试官决定，不用于岗位评分。",
            "evaluation_mode": "record_only",
            "recording_guidance": "如实记录或记为不便回答；不设好坏，不加分、不扣分。",
        }
    )
    return {
        "schema_version": "1.0.0",
        "case": {
            "id": "case-synthetic-candidate",
            "candidate_name": "测试候选人",
            "role_title": "AI 辅助全栈工程师",
            "report_date": "2026-08-23",
            "blueprint_version": "1.0.0",
            "human_review_status": "待面试官人工复核",
        },
        "candidate_overview": {
            "personal_info": {
                "birth_information": provided("1992-08-22"),
                "age": {
                    "display": "34岁",
                    "years": 34,
                    "approximate": False,
                    "as_of": "2026-08-23",
                    "normalized_birth": "1992-08-22",
                    "precision": "day",
                    "source_status": "candidate_provided",
                    "source_locator": "normalized/resume.md：基本信息",
                },
                "birthplace": provided("甲省乙市"),
                "hometown": provided("甲省乙市"),
                "marital_status": provided("已婚"),
                "current_city": provided("丙市"),
            },
            "profile_summary": [
                "医学与计算机双学士。",
                "目前从事医疗 AI 算法与 Agent 工程。",
            ],
            "education": [
                {
                    "school": "示例大学",
                    "degree_or_program": "医学、计算机科学与技术双学士",
                    "period": "2012–2017",
                    "city": "未提供",
                    "city_source_status": "not_provided",
                    "source_locator": "normalized/resume.md：教育背景",
                }
            ],
            "employment": [
                {
                    "organization": "示例科技公司",
                    "role": "算法策略工程师",
                    "period": "2025–至今",
                    "city": "丙市",
                    "city_source_status": "candidate_provided",
                    "source_locator": "normalized/resume.md：工作经历",
                }
            ],
            "fit_items": [
                {
                    "order": 1,
                    "capability": "AI Agent 工程",
                    "status": "match",
                    "summary": "有 Agent 与工作流编排经历。",
                    "interview_focus": "确认本人负责范围和可运行交付。",
                },
                {
                    "order": 2,
                    "capability": "前端产品工程",
                    "status": "evidence_insufficient",
                    "summary": "简历没有直接展示前端项目。",
                    "interview_focus": "通过工作样本核验，不因简历缺失直接扣分。",
                },
            ],
            "location_and_availability": {
                "company_location": "未提供",
                "distance_summary": "距离无法计算，待补充公司地址",
                "questions": [
                    "你目前常住在哪个城市？",
                    "如果工作地点不同，你是否愿意搬迁？",
                    "最早什么时候可以到岗？",
                ],
            },
        },
        "resume_risks": [
            {
                "id": "risk-1",
                "order": 1,
                "importance": 5,
                "capability": "AI 协作下的端到端交付",
                "resume_excerpt": "参与模型训练、评估与策略迭代。",
                "unclear_point": "“参与”没有说明本人具体负责哪一段。",
                "why_check": "岗位要求独立完成可运行的前后端闭环。",
                "how_to_verify": "让候选人按需求、本人实现、测试、失败和结果逐步说明。",
            }
        ],
        "interview_questions": questions,
        "footer_note": "本报告只辅助人工面试，不自动录用、淘汰或排序候选人。",
    }


class InterviewerReportDataTests(unittest.TestCase):
    def test_valid_data_passes(self) -> None:
        errors, warnings = validate_interviewer_report_data(sample_report_data())
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_exact_birth_date_age_must_match_report_date(self) -> None:
        data = sample_report_data()
        data["candidate_overview"]["personal_info"]["age"]["years"] = 33
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("age.years" in item for item in errors), errors)

    def test_converted_age_keeps_the_birth_information_source(self) -> None:
        data = sample_report_data()
        data["candidate_overview"]["personal_info"]["age"]["source_locator"] = "normalized/resume.md：其他位置"
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("age.source_locator" in item for item in errors), errors)

    def test_birth_year_is_converted_to_approximate_age(self) -> None:
        data = sample_report_data()
        data["candidate_overview"]["personal_info"]["birth_information"] = provided("1992")
        data["candidate_overview"]["personal_info"]["age"] = {
            "display": "约34岁（按出生年份估算）",
            "years": 34,
            "approximate": True,
            "as_of": "2026-08-23",
            "normalized_birth": "1992",
            "precision": "year",
            "source_status": "candidate_provided",
            "source_locator": "normalized/resume.md：基本信息",
        }
        errors, _ = validate_interviewer_report_data(data)
        self.assertEqual([], errors)

    def test_absent_birth_information_displays_age_as_not_provided(self) -> None:
        data = sample_report_data()
        data["candidate_overview"]["personal_info"]["birth_information"] = not_provided()
        data["candidate_overview"]["personal_info"]["age"] = {
            "display": "未提供",
            "years": None,
            "approximate": False,
            "as_of": "2026-08-23",
            "normalized_birth": None,
            "precision": "not_provided",
            "source_status": "not_provided",
            "source_locator": None,
        }
        errors, _ = validate_interviewer_report_data(data)
        self.assertEqual([], errors)

    def test_missing_personal_information_cannot_be_inferred(self) -> None:
        data = sample_report_data()
        data["candidate_overview"]["personal_info"]["hometown"] = {
            "value": "甲省乙市",
            "source_status": "inferred_from_school",
            "source_locator": "normalized/resume.md：教育背景",
        }
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("hometown" in item for item in errors), errors)

    def test_unwritten_school_or_work_city_cannot_be_filled(self) -> None:
        data = sample_report_data()
        education = data["candidate_overview"]["education"][0]
        education["city"] = "乙市"
        education["city_source_status"] = "not_provided"
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("education[0].city" in item for item in errors), errors)

    def test_personal_information_cannot_enter_job_fit(self) -> None:
        data = sample_report_data()
        data["candidate_overview"]["fit_items"][0]["summary"] = "年龄合适，已婚，看起来会比较稳定。"
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("fit_items[0]" in item for item in errors), errors)

    def test_personal_information_cannot_be_a_resume_risk_or_rating_signal(self) -> None:
        data = sample_report_data()
        data["resume_risks"][0]["why_check"] = "候选人已婚，需要判断是否稳定。"
        data["interview_questions"][0]["bonus_signals"] = ["年龄较小，可能更能承压"]
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("resume_risks[0]" in item for item in errors), errors)
        self.assertTrue(any("interview_questions[0]" in item for item in errors), errors)

    def test_contact_and_identity_details_cannot_enter_interviewer_data(self) -> None:
        cases = {
            "email": "联系邮箱 candidate@example.com",
            "mobile": "联系电话 13812345678",
            "identity_number": "身份证号 110105199001011234",
        }
        for label, leaked_value in cases.items():
            with self.subTest(label=label):
                data = sample_report_data()
                data["candidate_overview"]["profile_summary"][0] = leaked_value
                errors, _ = validate_interviewer_report_data(data)
                self.assertTrue(any("contact or identity detail" in item for item in errors), errors)

    def test_logistics_questions_are_record_only(self) -> None:
        data = sample_report_data()
        data["interview_questions"][9]["kind"] = "logistics"
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("logistics" in item and "record-only" in item for item in errors), errors)

    def test_question_pool_requires_each_core_question_kind(self) -> None:
        data = sample_report_data()
        data["interview_questions"][1]["kind"] = "job_core"
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("work_sample" in item for item in errors), errors)

    def test_question_pool_must_contain_twelve_to_eighteen_questions(self) -> None:
        data = sample_report_data()
        data["interview_questions"] = data["interview_questions"][:11]
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("12" in item and "18" in item for item in errors), errors)

    def test_marital_status_question_is_required_and_record_only(self) -> None:
        data = sample_report_data()
        data["interview_questions"][-1] = rated_question(12)
        errors, _ = validate_interviewer_report_data(data)
        self.assertTrue(any("marital-status question" in item for item in errors), errors)


class RenderedReportTests(unittest.TestCase):
    def render(self, output_name: str) -> tuple[subprocess.CompletedProcess[str], Path, tempfile.TemporaryDirectory[str]]:
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        data_path = root / "interviewer-report-data.json"
        data_path.write_text(json.dumps(sample_report_data(), ensure_ascii=False), encoding="utf-8")
        output = root / output_name
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "render_candidate_report.py"),
                "--data",
                str(data_path),
                "--output",
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=NO_BYTECODE_ENV,
        )
        return completed, output, temp_dir

    def test_output_filename_must_contain_candidate_name(self) -> None:
        completed, _, temp_dir = self.render("候选人评估与面试报告.html")
        self.addCleanup(temp_dir.cleanup)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("测试候选人", completed.stderr)

    def test_rendered_report_has_name_three_modules_and_offline_interactions(self) -> None:
        completed, output, temp_dir = self.render("测试候选人-候选人评估与面试报告.html")
        self.addCleanup(temp_dir.cleanup)
        self.assertEqual(0, completed.returncode, completed.stderr)
        html = output.read_text(encoding="utf-8")
        self.assertIn("<title>测试候选人｜候选人评估与面试报告</title>", html)
        self.assertIn("<h1 id=\"report-title\">测试候选人｜候选人评估与面试报告</h1>", html)
        self.assertEqual(1, html.count('id="candidate-overview"'))
        self.assertEqual(1, html.count('id="resume-risks"'))
        self.assertEqual(1, html.count('id="interview-questions"'))
        self.assertIn("localStorage", html)
        self.assertIn("可能要问", html)
        self.assertIn("一定要问", html)
        self.assertIn("备选", html)
        self.assertNotIn("window.confirm", html)
        self.assertIn("再次点击确认清空", html)
        self.assertIn("面试记录已导出", html)

        checked = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "validate_candidate_report.py"), str(output)],
            text=True,
            capture_output=True,
            check=False,
            env=NO_BYTECODE_ENV,
        )
        self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)


if __name__ == "__main__":
    unittest.main()
