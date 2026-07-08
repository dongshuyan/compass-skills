#!/usr/bin/env python3
"""Run representative local smoke tests for session-handoff-prompt."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


SAMPLE_PROMPT = """你正在接手一个已经进行过多轮的 agent session。请按以下上下文恢复任务状态；不要重新讨论已定事项。如果当前文件或可验证证据与这里冲突，以当前证据为准，并明确指出冲突。

【工作目录】
<workspace>

【用户目标】
把 session-handoff-prompt 作为 COMPASS 的正式 skill 接入，支持 macOS、Linux、Windows 和主流 agent。

【必须遵守的要求】
- [已验证] 内部说明用英文；交互和输出使用用户语言，默认中文。
- [已验证] 不读取 credential、cookie、浏览器 session 或无关私有日志。

【已确认事实与决策】
- [已验证] task-forest 负责长期任务结构，session-handoff-prompt 负责生成可粘贴到新 session 的续接 prompt。
- [推断] 默认 balanced 模式最符合还原度和简洁性的平衡。

【任务森林状态】
相关长期目标：COMPASS skills ecosystem。
当前任务节点：Add portable session handoff prompt skill。
未完成 todo：run validation and update README。
依赖 / 阻塞：none.
可能未同步之处：task-forest export may be stale; verify workspace before acting.

【已完成】
- 已设计 portable skill structure.
- 已补充 privacy modes and validation scripts.

【未完成 / 待验证】
- 需要运行 py_compile、smoke test、secret/path scan 和 manifest validation.

【关键文件 / 命令 / 产物】
- skills/session-handoff-prompt/SKILL.md
- skills/session-handoff-prompt/scripts/smoke_test_handoff.py

【不要重复 / 不要做】
- 不要自动创建新 agent session。
- 不要修改 task-forest。

【下一步】
1. 更新 README 和 skills.sh.json。
2. 运行验证。
3. 报告结果和剩余风险。
"""


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_sample_codex_jsonl(path: Path) -> None:
    rows = [
        {"type": "session_meta", "payload": {"id": "sample-session", "cwd": "/mnt/c/Users/example/project"}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": "Context is too long. Create a handoff prompt."}},
        {"type": "compacted", "payload": {"message": "Important compacted summary with prior decisions."}},
        {"type": "response_item", "payload": {"type": "function_call", "name": "shell", "arguments": "{\"cmd\":\"pytest\"}"}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "call_1", "output": "tests passed in D:\\\\Data\\\\repo\\\\artifact.txt"}},
    ]
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def write_sample_task_forest(workspace: Path) -> None:
    export_dir = workspace / ".agent-workbench" / "task-forest" / "exports"
    export_dir.mkdir(parents=True)
    (export_dir / "task-forest.graph.json").write_text(json.dumps({
        "nodes": [
            {"id": "TF-0001", "kind": "global_task", "title": "Maintain COMPASS skills", "status": "in_progress"},
            {"id": "TF-0002", "kind": "task", "title": "Add session handoff prompt", "status": "review_needed"},
        ],
        "edges": [{"from": "TF-0002", "to": "TF-0001", "kind": "child_of"}],
    }, ensure_ascii=False), encoding="utf-8")
    (export_dir / "task-forest.todos.json").write_text(json.dumps([
        {"id": "TODO-1", "title": "Run smoke test", "status": "open", "priority": "high"}
    ], ensure_ascii=False), encoding="utf-8")
    (export_dir / "task-forest.timeline.json").write_text(json.dumps([
        {"event": "created", "summary": "Added handoff skill task"}
    ], ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test session-handoff-prompt scripts.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    skill_dir = Path(args.skill_dir).resolve()
    scripts = skill_dir / "scripts"

    project = import_module(scripts / "project_session_events.py", "project_session_events")
    task_forest = import_module(scripts / "read_task_forest_exports.py", "read_task_forest_exports")
    redact = import_module(scripts / "redact_handoff.py", "redact_handoff")
    validate = import_module(scripts / "validate_handoff_prompt.py", "validate_handoff_prompt")

    with tempfile.TemporaryDirectory(prefix="compass-handoff-smoke-") as tmp:
        root = Path(tmp)
        jsonl = root / "session.jsonl"
        write_sample_codex_jsonl(jsonl)
        events = project.parse_codex_jsonl(jsonl, max_chars=400, redact_paths=True)
        assert any(event.get("kind") == "compacted" for event in events), "compacted event not projected"
        assert any(event.get("kind") == "session_meta" and event.get("cwd") == "<LOCAL_PATH>" for event in events), "session cwd was not redacted"
        assert any(event.get("kind") == "tool_output" and event.get("output") == "tests passed in <LOCAL_PATH>" for event in events), "tool output missing or not redacted"

        workspace = root / "workspace"
        workspace.mkdir()
        write_sample_task_forest(workspace)
        tf_summary = task_forest.summarize(workspace)
        assert tf_summary["found"] is True, "task-forest exports not found"
        assert tf_summary["summary"].get("graph_records"), "graph records missing"

        local_result = validate.validate(SAMPLE_PROMPT, mode="balanced", privacy="local")
        assert local_result["ok"], local_result
        shareable_fail = validate.validate(SAMPLE_PROMPT + "\n/Volumes/work/demo\n", mode="balanced", privacy="shareable")
        assert not shareable_fail["ok"] and "local_path_in_shareable_prompt" in shareable_fail["hard"], shareable_fail
        path_blob = "\n".join(
            [
                "/home/example/private",
                "/Volumes/work/demo",
                "/var/folders/ab/cd/T/demo",
                "/tmp/agent-output",
                "/mnt/c/Users/example/project",
                r"D:\Data\repo\file.txt",
                r"\\server\share\repo\file.txt",
                r"\\?\C:\Users\alice\repo\file.txt",
                "~/.codex/skills/private",
            ]
        )
        redacted = redact.redact(SAMPLE_PROMPT + "\nsk-abcdefghijklmnopqrstuvwxyz\n" + path_blob + "\n", privacy="shareable")
        shareable_result = validate.validate(redacted, mode="balanced", privacy="shareable")
        assert shareable_result["ok"], shareable_result
        assert redacted.count("<LOCAL_PATH>") >= 8, "shareable path redaction missing extended path families"
        assert "sk-<REDACTED>" in redacted, "secret redaction missing"

    print("ok=session-handoff-prompt smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
