#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

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


def validation_env(**overrides: str) -> dict[str, str]:
    env = os.environ.copy()
    env["TASK_FOREST_DISABLE_GLOBAL_REGISTRY"] = "1"
    env.update(overrides)
    return env


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
    if root_child_titles.index("完成资料协作与 AI 总结") > root_child_titles.index(
        "打通用户登录与访问权限"
    ):
        raise AssertionError("沟通 HTML 未按显式 display_order 排列阶段")
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
        validate_process_probe_portability(script)
        validate_actor_portability(script, Path(temp.name) / "actor-workspace")
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
