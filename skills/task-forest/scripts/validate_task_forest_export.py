#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from task_forest import validate_state
from task_forest_html import render_overview_html


def run(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "命令失败：{}\nstdout:\n{}\nstderr:\n{}".format(
                " ".join(cmd), result.stdout.strip(), result.stderr.strip()
            )
        )
    return result


def extract_node_id(stdout: str) -> str:
    match = re.search(r"TF-\d{4,}", stdout)
    if not match:
        raise RuntimeError(f"无法从输出中解析节点 ID：{stdout}")
    return match.group(0)


def assert_contains(text: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise AssertionError(f"{label} 缺少内容：{', '.join(missing)}")


def assert_not_contains(text: str, needles: list[str], label: str) -> None:
    found = [needle for needle in needles if needle in text]
    if found:
        raise AssertionError(f"{label} 不应包含内容：{', '.join(found)}")


def extract_json_script(html: str, script_id: str) -> object:
    match = re.search(
        rf'<script\s+id="{re.escape(script_id)}"\s+type="application/json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError(f"HTML 缺少内嵌数据：{script_id}")
    return json.loads(match.group(1))


def digest_paths(paths: list[Path]) -> dict[str, str]:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
        if path.exists()
    }


def ordering_node(
    node_id: str,
    title: str,
    created_at: str,
    *,
    tags: list[str] | None = None,
    display_order: object | None = None,
) -> dict[str, object]:
    node: dict[str, object] = {
        "id": node_id,
        "title": title,
        "status": "in_progress" if node_id == "root" else "done",
        "kind": "global_task" if node_id == "root" else "task",
        "summary": f"{title}的排序回归说明。",
        "created_at": created_at,
        "context_tags": tags or [],
    }
    if display_order is not None:
        node["display_order"] = display_order
    return node


def ordering_graph(
    nodes: dict[str, dict[str, object]], relations: list[tuple[str, str]]
) -> dict[str, object]:
    return {
        "roots": ["root"],
        "nodes": nodes,
        "edges": {
            f"edge-{index}": {
                "id": f"edge-{index}",
                "from": child,
                "to": parent,
                "type": "child_of",
            }
            for index, (child, parent) in enumerate(relations, start=1)
        },
    }


def projected_children(graph: dict[str, object], parent_id: str) -> list[str]:
    overview = extract_json_script(
        render_overview_html(graph, []), "task-forest-overview-data"
    )
    if not isinstance(overview, dict):
        raise AssertionError("沟通 HTML 内嵌任务数据类型错误")
    nodes = overview.get("nodes", [])
    if not isinstance(nodes, list):
        raise AssertionError("沟通 HTML 内嵌节点类型错误")
    by_id = {
        str(node.get("id")): node
        for node in nodes
        if isinstance(node, dict) and node.get("id")
    }
    parent = by_id.get(parent_id)
    if not isinstance(parent, dict) or not isinstance(parent.get("children"), list):
        raise AssertionError(f"沟通 HTML 缺少父节点或子节点：{parent_id}")
    return [str(child_id) for child_id in parent["children"]]


def validate_ordering_regressions() -> None:
    root = ordering_node("root", "端到端目标", "2026-08-09T00:00:00Z")
    mixed_nodes = {
        "root": root,
        "p00": ordering_node(
            "p00", "架构基础（P00）", "2026-08-09T01:00:00Z", tags=["P00"]
        ),
        "p01": ordering_node(
            "p01", "领域基础（P01）", "2026-08-09T02:00:00Z", tags=["P01"]
        ),
        "session": ordering_node(
            "session",
            "本阶段会话收口",
            "2026-08-09T03:00:00Z",
            tags=["session-close"],
            display_order=90,
        ),
    }
    mixed_graph = ordering_graph(
        mixed_nodes, [("p00", "root"), ("p01", "root"), ("session", "root")]
    )
    if projected_children(mixed_graph, "root") != ["p00", "p01", "session"]:
        raise AssertionError("历史混合顺序必须安全回退到业务编号")
    mixed_errors, _ = validate_state(mixed_nodes, mixed_graph["edges"])
    if not any("display_order" in error for error in mixed_errors):
        raise AssertionError("当前部分 display_order 必须被校验拒绝")

    nested_nodes = {
        "root": root,
        "p04-m04": ordering_node(
            "p04-m04",
            "会议结论与结束（P04.M04）",
            "2026-08-09T01:00:00Z",
            tags=["P04.M04"],
        ),
        "t01": ordering_node(
            "t01",
            "完成四类会议结论（P04.M04.T01）",
            "2026-08-09T02:00:00Z",
            tags=["P04.M04.T01"],
        ),
        "slice": ordering_node(
            "slice",
            "受控结束会议实现切片",
            "2026-08-09T03:00:00Z",
            tags=["P04", "meeting-end"],
            display_order=40,
        ),
    }
    nested_graph = ordering_graph(
        nested_nodes,
        [("p04-m04", "root"), ("t01", "p04-m04"), ("slice", "p04-m04")],
    )
    if projected_children(nested_graph, "p04-m04") != ["t01", "slice"]:
        raise AssertionError("嵌套排序必须使用相对父节点的最具体业务编号")

    explicit_nodes = {
        "root": root,
        "later": ordering_node(
            "later", "后续任务", "2026-08-09T01:00:00Z", display_order=20
        ),
        "earlier": ordering_node(
            "earlier", "先行任务", "2026-08-09T02:00:00Z", display_order=10
        ),
    }
    explicit_graph = ordering_graph(
        explicit_nodes, [("later", "root"), ("earlier", "root")]
    )
    if projected_children(explicit_graph, "root") != ["earlier", "later"]:
        raise AssertionError("完整 display_order 必须按数值升序")

    duplicate_nodes = {
        "root": root,
        "p02": ordering_node(
            "p02",
            "第二阶段（P02）",
            "2026-08-09T01:00:00Z",
            tags=["P02"],
            display_order=10,
        ),
        "p01": ordering_node(
            "p01",
            "第一阶段（P01）",
            "2026-08-09T02:00:00Z",
            tags=["P01"],
            display_order=10,
        ),
    }
    duplicate_graph = ordering_graph(
        duplicate_nodes, [("p02", "root"), ("p01", "root")]
    )
    if projected_children(duplicate_graph, "root") != ["p01", "p02"]:
        raise AssertionError("历史重复 display_order 必须回退到业务编号")
    duplicate_errors, _ = validate_state(duplicate_nodes, duplicate_graph["edges"])
    if not any("重复" in error for error in duplicate_errors):
        raise AssertionError("当前重复 display_order 必须被校验拒绝")

    invalid_nodes = {
        "root": root,
        "invalid": ordering_node(
            "invalid",
            "非法顺序任务",
            "2026-08-09T01:00:00Z",
            display_order=True,
        ),
    }
    invalid_graph = ordering_graph(invalid_nodes, [("invalid", "root")])
    invalid_errors, _ = validate_state(invalid_nodes, invalid_graph["edges"])
    if not any("有限数值" in error for error in invalid_errors):
        raise AssertionError("非法 display_order 必须被校验拒绝")

    free_nodes = {
        "root": root,
        "newer": ordering_node("newer", "后创建任务", "2026-08-09T02:00:00Z"),
        "older": ordering_node("older", "先创建任务", "2026-08-09T01:00:00Z"),
    }
    free_graph = ordering_graph(free_nodes, [("newer", "root"), ("older", "root")])
    if projected_children(free_graph, "root") != ["older", "newer"]:
        raise AssertionError("无编号自由任务必须按创建时间稳定排序")


def validate_legacy_mixed_export(script: Path, workspace: Path) -> None:
    cli(script, workspace, "init")
    root = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "global_task",
            "--status",
            "in_progress",
            "--title",
            "端到端目标",
            "--summary",
            "验证旧混合顺序仍可安全导出。",
        ).stdout
    )
    child_ids: dict[str, str] = {}
    for alias, title, tag in [
        ("p00", "架构基础（P00）", "P00"),
        ("p01", "领域基础（P01）", "P01"),
        ("session", "本阶段会话收口", "session-close"),
    ]:
        child_ids[alias] = extract_node_id(
            cli(
                script,
                workspace,
                "add-node",
                "--kind",
                "task",
                "--status",
                "done",
                "--title",
                title,
                "--summary",
                f"{title}的回归说明。",
                "--tag",
                tag,
                "--parent",
                root,
            ).stdout
        )

    canonical = workspace / ".agent-workbench" / "task-forest"
    nodes_path = canonical / "graph" / "nodes.json"
    edges_path = canonical / "graph" / "edges.json"
    nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
    nodes[child_ids["session"]]["display_order"] = 90
    nodes_path.write_text(
        json.dumps(nodes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    before = digest_paths([nodes_path, edges_path])

    export_result = subprocess.run(
        [sys.executable, str(script), "export", "--workspace", str(workspace)],
        env=validation_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    if export_result.returncode != 0:
        raise AssertionError(
            "旧混合顺序必须保持可导出：\n" + export_result.stdout + export_result.stderr
        )
    if "HTML 已使用安全回退顺序" not in export_result.stderr:
        raise AssertionError("旧混合顺序导出必须给出安全回退警告")
    if before != digest_paths([nodes_path, edges_path]):
        raise AssertionError("旧混合顺序导出不得修改 canonical task 数据")

    overview = extract_json_script(
        (canonical / "exports" / "task-forest.html").read_text(encoding="utf-8"),
        "task-forest-overview-data",
    )
    if not isinstance(overview, dict):
        raise AssertionError("旧混合顺序导出缺少沟通视图数据")
    by_id = {
        str(node.get("id")): node
        for node in overview.get("nodes", [])
        if isinstance(node, dict) and node.get("id")
    }
    if by_id[root].get("children") != [
        child_ids["p00"],
        child_ids["p01"],
        child_ids["session"],
    ]:
        raise AssertionError("旧混合顺序导出未按业务编号安全回退")

    validate_result = subprocess.run(
        [sys.executable, str(script), "validate", "--workspace", str(workspace)],
        env=validation_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    if validate_result.returncode == 0 or "display_order" not in (
        validate_result.stdout + validate_result.stderr
    ):
        raise AssertionError("旧混合顺序必须被 validate 明确拒绝")

    blocked_proposal_id = "TFP-ordering-must-fail"
    blocked_proposal = {
        "proposal_id": blocked_proposal_id,
        "changes": [
            {
                "action": "update_node",
                "id": root,
                "fields": {"summary": "不相关更新不能绕过同级顺序校验。"},
            }
        ],
    }
    blocked_result = subprocess.run(
        [
            sys.executable,
            str(script),
            "proposal-save",
            "--proposal-json",
            json.dumps(blocked_proposal, ensure_ascii=False),
            "--workspace",
            str(workspace),
        ],
        env=validation_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    if blocked_result.returncode == 0 or "display_order" not in (
        blocked_result.stdout + blocked_result.stderr
    ):
        raise AssertionError("proposal-save 必须拒绝仍保留混合顺序的候选变更")
    if (canonical / "proposals" / f"{blocked_proposal_id}.json").exists():
        raise AssertionError("失败的顺序 proposal 不得被保存")

    repair_proposal = {
        "proposal_id": "TFP-ordering-repair",
        "changes": [
            {
                "action": "update_node",
                "id": child_ids["p00"],
                "fields": {"display_order": 0},
            },
            {
                "action": "update_node",
                "id": child_ids["p01"],
                "fields": {"display_order": 10},
            },
        ],
    }
    repair_result = subprocess.run(
        [
            sys.executable,
            str(script),
            "proposal-save",
            "--proposal-json",
            json.dumps(repair_proposal, ensure_ascii=False),
            "--workspace",
            str(workspace),
        ],
        env=validation_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    if repair_result.returncode != 0:
        raise AssertionError(
            "一次补齐整个兄弟组的 proposal 应通过：\n"
            + repair_result.stdout
            + repair_result.stderr
        )


def validation_env(**overrides: str) -> dict[str, str]:
    env = os.environ.copy()
    env["TASK_FOREST_DISABLE_GLOBAL_REGISTRY"] = "1"
    env.update(overrides)
    return env


def validate_global_registry_opt_in(script: Path, temp_root: Path) -> None:
    default_db = temp_root / "default-registry.sqlite3"
    default_env = os.environ.copy()
    default_env.pop("TASK_FOREST_DISABLE_GLOBAL_REGISTRY", None)
    default_env.pop("TASK_FOREST_ENABLE_GLOBAL_REGISTRY", None)
    default_env["AGENT_WORKBENCH_DB"] = str(default_db)
    cli(
        script,
        temp_root / "default-registry-workspace",
        "init",
        env=default_env,
    )
    if default_db.exists():
        raise AssertionError("未显式 opt-in 时不得创建或更新全局 registry")

    opted_in_db = temp_root / "opted-in-registry.sqlite3"
    opted_in_env = default_env.copy()
    opted_in_env["AGENT_WORKBENCH_DB"] = str(opted_in_db)
    opted_in_env["TASK_FOREST_ENABLE_GLOBAL_REGISTRY"] = "1"
    opted_in_workspace = temp_root / "opted-in-registry-workspace"
    cli(script, opted_in_workspace, "init", env=opted_in_env)
    if not opted_in_db.exists():
        raise AssertionError("显式 opt-in 后应更新全局 registry")
    with sqlite3.connect(opted_in_db) as conn:
        registered = conn.execute(
            "SELECT COUNT(*) FROM aw_task_forests WHERE workspace_path=?",
            (str(opted_in_workspace.resolve()),),
        ).fetchone()[0]
    if registered != 1:
        raise AssertionError("显式 opt-in 后应登记当前 workspace")


def cli(
    script: Path,
    workspace: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return run(
        [sys.executable, str(script), *args, "--workspace", str(workspace)],
        env=env or validation_env(),
    )


def validate_actor_portability(script: Path, workspace: Path) -> None:
    neutral_env = validation_env()
    neutral_env.pop("COMPASS_AGENT_NAME", None)
    neutral_env.pop("AGENT_NAME", None)
    cli(script, workspace, "init", env=neutral_env)
    cli(
        script,
        workspace,
        "add-node",
        "--kind",
        "task",
        "--title",
        "验证中性调用者",
        env=neutral_env,
    )
    events_path = (
        workspace / ".agent-workbench" / "task-forest" / "events" / "events.jsonl"
    )
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    if events[-1].get("actor") != "agent":
        raise AssertionError("未设置调用者环境变量时必须使用中性 actor")

    named_env = validation_env(
        COMPASS_AGENT_NAME="portable-agent", AGENT_NAME="fallback-agent"
    )
    cli(
        script,
        workspace,
        "add-node",
        "--kind",
        "task",
        "--title",
        "验证显式调用者",
        env=named_env,
    )
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    if events[-1].get("actor") != "portable-agent":
        raise AssertionError("COMPASS_AGENT_NAME 必须优先于其他调用者名称")


def validate_process_probe_portability(script: Path) -> None:
    spec = importlib.util.spec_from_file_location("task_forest_portability", script)
    if spec is None or spec.loader is None:
        raise AssertionError("无法加载 task_forest.py 做跨平台进程探测验证")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if module._classify_posix_kill_outcome(None) is not True:
        raise AssertionError("POSIX 存活进程探测分类错误")
    if module._classify_posix_kill_outcome(ProcessLookupError()) is not False:
        raise AssertionError("POSIX 不存在进程探测分类错误")
    if module._classify_posix_kill_outcome(PermissionError()) is not True:
        raise AssertionError("POSIX 无权限进程必须按存活处理")
    if (
        module._classify_windows_probe(module.WINDOWS_ERROR_INVALID_PARAMETER, None)
        is not False
    ):
        raise AssertionError("Windows 不存在进程探测分类错误")
    if (
        module._classify_windows_probe(module.WINDOWS_ERROR_ACCESS_DENIED, None)
        is not True
    ):
        raise AssertionError("Windows 无权限进程必须按存活处理")
    if module._classify_windows_probe(None, module.WAIT_OBJECT_0) is not False:
        raise AssertionError("Windows 已退出进程探测分类错误")
    if module._classify_windows_probe(None, module.WAIT_TIMEOUT) is not True:
        raise AssertionError("Windows 存活进程探测分类错误")


def build_sample_graph(script: Path, workspace: Path) -> None:
    cli(script, workspace, "init")
    root = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "global_task",
            "--status",
            "in_progress",
            "--title",
            "端到端实现第一版产品 Demo",
            "--summary",
            "完成从用户登录、业务操作到结果交付的可演示闭环。",
            "--purpose",
            "让甲方可以按完整流程体验第一版产品能力",
            "--desired-outcome",
            "形成可连续操作并能说明建设进度的 Demo",
            "--acceptance",
            "HTML 能独立展示已完成、正在推进和历史变化",
            "--success-metric",
            "导出 HTML 满足 html-visualization-contract",
            "--progress",
            "35",
            "--priority",
            "1",
            "--difficulty",
            "high",
            "--confidence",
            "0.85",
            "--fields-json",
            '{"progress_source":"manual"}',
        ).stdout
    )
    implementation = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "task",
            "--status",
            "in_progress",
            "--title",
            "打通用户登录与访问权限",
            "--summary",
            "用户可以使用演示账号登录，并且只能查看自己有权限的数据。",
            "--purpose",
            "建立后续业务流程所需的安全访问入口",
            "--acceptance",
            "validate 通过",
            "--acceptance",
            "HTML 导出通过回归检查",
            "--progress",
            "93",
            "--priority",
            "1",
            "--fields-json",
            '{"display_order":40}',
            "--parent",
            root,
        ).stdout
    )
    _dashboard = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "subtask",
            "--status",
            "done",
            "--title",
            "完成演示账号登录",
            "--summary",
            "管理员和医生可以使用各自的演示账号进入对应工作台。",
            "--progress",
            "100",
            "--priority",
            "2",
            "--parent",
            implementation,
        ).stdout
    )
    public = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "subtask",
            "--status",
            "done",
            "--title",
            "完成病例成员权限控制",
            "--summary",
            "主管医生和受邀医生可以打开病例，其他账号会被明确拒绝。",
            "--progress",
            "100",
            "--priority",
            "2",
            "--parent",
            implementation,
        ).stdout
    )
    integration = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "follow_up",
            "--status",
            "ready",
            "--title",
            "未开始的报告自动生成",
            "--summary",
            "会议完成后生成最终报告。",
            "--progress",
            "25",
            "--priority",
            "1",
            "--parent",
            implementation,
        ).stdout
    )
    evergreen = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "risk",
            "--status",
            "review_needed",
            "--title",
            "待复核的性能优化",
            "--summary",
            "检查大数据量下的页面响应速度。",
            "--progress",
            "65",
            "--priority",
            "2",
            "--fields-json",
            '{"display_order":50}',
            "--parent",
            root,
        ).stdout
    )
    html = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "subtask",
            "--status",
            "done",
            "--title",
            "完成建设进度展示",
            "--summary",
            "页面用清晰层级、任务详情和历史播放说明项目建设进度。",
            "--progress",
            "100",
            "--priority",
            "1",
            "--parent",
            implementation,
        ).stdout
    )
    materials_phase = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "milestone",
            "--status",
            "in_progress",
            "--title",
            "完成资料协作与 AI 总结",
            "--summary",
            "医生共享病例资料，系统基于锁定版本生成总结并由本人确认。",
            "--progress",
            "72",
            "--priority",
            "1",
            "--fields-json",
            '{"display_order":30}',
            "--parent",
            root,
        ).stdout
    )
    materials_module = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "task",
            "--status",
            "done",
            "--title",
            "完成多医生资料共享",
            "--summary",
            "主管医生和参与医生可以编辑、发布并查看各自的专科资料。",
            "--progress",
            "100",
            "--priority",
            "1",
            "--parent",
            materials_phase,
        ).stdout
    )
    extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "subtask",
            "--status",
            "done",
            "--title",
            "发布医生专科资料",
            "--summary",
            "每位医生提交本人负责的文字、图片和 PDF 资料。",
            "--progress",
            "100",
            "--priority",
            "2",
            "--parent",
            materials_module,
        ).stdout
    )
    summary_module = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "task",
            "--status",
            "in_progress",
            "--title",
            "生成并确认医生总结",
            "--summary",
            "资料锁定后生成四份医生总结，并由每位医生确认本人内容。",
            "--progress",
            "80",
            "--priority",
            "1",
            "--parent",
            materials_phase,
        ).stdout
    )
    extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "subtask",
            "--status",
            "in_progress",
            "--title",
            "完成四位医生总结确认",
            "--summary",
            "四位医生逐一核对并确认本人总结，完成后开放演示稿阶段。",
            "--progress",
            "75",
            "--priority",
            "1",
            "--parent",
            summary_module,
        ).stdout
    )
    cli(
        script,
        workspace,
        "add-edge",
        "--from",
        integration,
        "--to",
        public,
        "--type",
        "depends_on",
        "--reason",
        "对外契约和公开包稳定后，再让其他插件读取 exports 更稳妥。",
    )
    cli(
        script,
        workspace,
        "add-edge",
        "--from",
        integration,
        "--to",
        root,
        "--type",
        "contributes_to",
        "--reason",
        "下游集成贡献到长期 skill 生态。",
    )
    cli(
        script,
        workspace,
        "add-edge",
        "--from",
        html,
        "--to",
        integration,
        "--type",
        "contributes_to",
        "--reason",
        "新增派生字段和可视化能力为下游读取提供稳定上游。",
    )
    cli(
        script,
        workspace,
        "add-edge",
        "--from",
        evergreen,
        "--to",
        root,
        "--type",
        "clarifies",
        "--reason",
        "澄清长期目标生命周期风险的当前处理方式。",
    )


def validate_exports(workspace: Path) -> None:
    export_dir = workspace / ".agent-workbench" / "task-forest" / "exports"
    graph_path = export_dir / "task-forest.graph.json"
    todo_path = export_dir / "task-forest.todos.json"
    timeline_path = export_dir / "task-forest.timeline.json"
    html_path = export_dir / "task-forest.html"
    expected_paths = [graph_path, todo_path, timeline_path, html_path]
    for path in expected_paths:
        if not path.exists():
            raise AssertionError(f"缺少导出文件：{path}")
    actual_names = {path.name for path in export_dir.iterdir() if path.is_file()}
    expected_names = {path.name for path in expected_paths}
    if actual_names != expected_names:
        raise AssertionError(
            f"导出文件集合不正确：expected={sorted(expected_names)} actual={sorted(actual_names)}"
        )
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    todos = json.loads(todo_path.read_text(encoding="utf-8"))
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    if graph.get("summary", {}).get("node_count", 0) < 7:
        raise AssertionError("样例图节点数量不足")
    if graph.get("summary", {}).get("edge_count", 0) < 9:
        raise AssertionError("样例图边数量不足")
    for edge_type in ["child_of", "depends_on", "contributes_to", "clarifies"]:
        if graph.get("edge_type_counts", {}).get(edge_type, 0) < 1:
            raise AssertionError(f"样例图缺少边类型：{edge_type}")
    if len(graph.get("status_queues", {}).get("review_needed", [])) < 1:
        raise AssertionError("样例图应包含待复核节点，用于验证沟通视图会隐藏它")
    if not todos:
        raise AssertionError("todo 导出不应为空")
    if len(timeline) < 2:
        raise AssertionError("timeline 应包含多个快照，供历史播放验证")

    assert_contains(
        html,
        [
            'data-view="communication"',
            "端到端实现第一版产品 Demo",
            "按目标、阶段和功能层级展示已经完成与正在推进的工作",
            "全部展开",
            "收起已完成",
            "定位正在推进",
            "任务详情",
            "预期成果",
            "验收标准",
            "建设演进",
            "从头播放",
            "historySlider",
            "startPlayback",
            "detailTrigger",
        ],
        "HTML",
    )
    assert_not_contains(
        html,
        [
            "task-forest.audit.html",
            "未开始的报告自动生成",
            "待复核的性能优化",
            "DAG 视图",
            "待复核要看什么",
        ],
        "HTML",
    )

    overview = extract_json_script(html, "task-forest-overview-data")
    history = extract_json_script(html, "task-forest-overview-history")
    if not isinstance(overview, dict) or not isinstance(history, list):
        raise AssertionError("HTML 内嵌任务或历史数据类型错误")
    visible_nodes = overview.get("nodes", [])
    if not visible_nodes:
        raise AssertionError("沟通 HTML 不应为空")
    for node in visible_nodes:
        if not node.get("title") or not (node.get("summary") or node.get("purpose")):
            raise AssertionError(f"可见任务缺少独立说明：{node.get('id')}")
        if not node.get("contextOnly") and node.get("status") not in {
            "done",
            "in_progress",
        }:
            raise AssertionError(f"沟通 HTML 泄露未交付状态：{node.get('status')}")
    visible_by_title = {node.get("title"): node for node in visible_nodes}
    expected_hierarchy = {
        "完成资料协作与 AI 总结": "端到端实现第一版产品 Demo",
        "完成多医生资料共享": "完成资料协作与 AI 总结",
        "发布医生专科资料": "完成多医生资料共享",
        "生成并确认医生总结": "完成资料协作与 AI 总结",
        "完成四位医生总结确认": "生成并确认医生总结",
    }
    id_by_title = {title: node.get("id") for title, node in visible_by_title.items()}
    for title, parent_title in expected_hierarchy.items():
        node = visible_by_title.get(title)
        if node is None:
            raise AssertionError(f"沟通 HTML 丢失权威任务层级节点：{title}")
        if node.get("primary_parent") != id_by_title.get(parent_title):
            raise AssertionError(
                f"沟通 HTML 压缩或破坏任务层级：{title} -> {parent_title}"
            )
    root_node = visible_by_title["端到端实现第一版产品 Demo"]
    root_child_titles = [
        next(node["title"] for node in visible_nodes if node["id"] == child_id)
        for child_id in root_node.get("children", [])
    ]
    if root_child_titles != [
        "完成资料协作与 AI 总结",
        "打通用户登录与访问权限",
    ]:
        raise AssertionError(
            f"沟通 HTML 未按显式 display_order 排列阶段：{root_child_titles}"
        )
    graph_nodes = graph.get("nodes", {})
    graph_by_title = {
        node.get("title"): node
        for node in graph_nodes.values()
        if isinstance(node, dict) and node.get("title")
    }
    canonical_root_children = [
        graph_nodes[child_id]["title"]
        for child_id in graph_by_title["端到端实现第一版产品 Demo"].get("children", [])
    ]
    if canonical_root_children != [
        "完成资料协作与 AI 总结",
        "打通用户登录与访问权限",
        "待复核的性能优化",
    ]:
        raise AssertionError(
            f"兼容 JSON 根阶段未复用共享排序：{canonical_root_children}"
        )
    numbered_graph = {
        "roots": ["root"],
        "nodes": {
            "root": {
                "id": "root",
                "title": "编号顺序回归",
                "status": "in_progress",
                "kind": "global_task",
                "summary": "验证没有显式顺序时仍能识别业务编号。",
            },
            "phase-02": {
                "id": "phase-02",
                "title": "第二阶段（P02）",
                "status": "done",
                "kind": "milestone",
                "summary": "第二阶段任务。",
            },
            "phase-01": {
                "id": "phase-01",
                "title": "第一阶段（P01）",
                "status": "done",
                "kind": "milestone",
                "summary": "第一阶段任务。",
            },
        },
        "edges": {
            "edge-02": {
                "id": "edge-02",
                "from": "phase-02",
                "to": "root",
                "type": "child_of",
            },
            "edge-01": {
                "id": "edge-01",
                "from": "phase-01",
                "to": "root",
                "type": "child_of",
            },
        },
    }
    numbered_overview = extract_json_script(
        render_overview_html(numbered_graph, []), "task-forest-overview-data"
    )
    numbered_by_id = {node["id"]: node for node in numbered_overview["nodes"]}
    if numbered_by_id["root"]["children"] != ["phase-01", "phase-02"]:
        raise AssertionError("沟通 HTML 未按可识别的任务编号排列阶段")
    if sum(1 for frame in history if frame.get("saved")) != len(timeline):
        raise AssertionError("HTML 历史帧与真实快照数量不一致")
    if 'node-title">${escapeHtml(node.id' in html:
        raise AssertionError("卡片不得把内部任务 ID 当作主要名称")

    zero_history = extract_json_script(
        render_overview_html(graph, []), "task-forest-overview-history"
    )
    if not isinstance(zero_history, list) or len(zero_history) != 1:
        raise AssertionError("0 快照时应只有一个当前状态画面")
    if (
        zero_history[0].get("saved")
        or zero_history[0].get("frameType") != "current_unsaved"
    ):
        raise AssertionError("0 快照画面必须明确标记为未保存当前状态")

    one_history = extract_json_script(
        render_overview_html(graph, [timeline[0]]), "task-forest-overview-history"
    )
    if (
        not isinstance(one_history, list)
        or sum(1 for frame in one_history if frame.get("saved")) != 1
    ):
        raise AssertionError("1 快照时必须精确保留一份真实快照")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从零验证 task-forest 导出 HTML 是否满足可视化契约。"
    )
    parser.add_argument("--skill-dir", required=True, help="task-forest skill 目录")
    parser.add_argument(
        "--keep-workspace", action="store_true", help="保留临时 workspace，便于人工检查"
    )
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).expanduser().resolve()
    script = skill_dir / "scripts" / "task_forest.py"
    if not script.exists():
        raise SystemExit(f"找不到 task_forest.py：{script}")

    temp = tempfile.TemporaryDirectory(prefix="task-forest-export-")
    workspace = Path(temp.name) / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    try:
        validate_ordering_regressions()
        validate_process_probe_portability(script)
        validate_global_registry_opt_in(script, Path(temp.name))
        validate_actor_portability(script, Path(temp.name) / "actor-workspace")
        validate_legacy_mixed_export(script, Path(temp.name) / "legacy-workspace")
        build_sample_graph(script, workspace)
        cli(script, workspace, "validate")
        canonical = workspace / ".agent-workbench" / "task-forest"
        authoritative = [
            canonical / "config.json",
            canonical / "graph" / "nodes.json",
            canonical / "graph" / "edges.json",
            canonical / "events" / "events.jsonl",
        ]
        before = digest_paths(authoritative)
        stale_audit = canonical / "exports" / "task-forest.audit.html"
        stale_audit.write_text("retired", encoding="utf-8")
        cli(script, workspace, "export")
        after = digest_paths(authoritative)
        if before != after:
            raise AssertionError("export 不得修改 canonical task 数据")
        if stale_audit.exists():
            raise AssertionError("export 应清理旧的 task-forest.audit.html")
        validate_exports(workspace)
        html_path = (
            workspace
            / ".agent-workbench"
            / "task-forest"
            / "exports"
            / "task-forest.html"
        )
        print(f"task-forest export 回归通过：{html_path}")
        if args.keep_workspace:
            print(f"已保留 workspace：{workspace}")
            temp._finalizer.detach()
        return 0
    finally:
        if not args.keep_workspace:
            temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
