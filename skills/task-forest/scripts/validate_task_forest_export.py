#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
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


def cli(script: Path, workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(script), *args, "--workspace", str(workspace)])


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
            "Build a personal AI workbench",
            "--summary",
            "Maintain a repo-local task map, history, and visualization for long-running AI work.",
            "--purpose",
            "让用户长期看清当前 repo 的真实任务结构和进展",
            "--desired-outcome",
            "用户能看到任务森林和历史变化",
            "--acceptance",
            "HTML 能展示树视图、DAG 视图、历史和未完成事项",
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
            "review_needed",
            "--title",
            "Set up the task-forest skill",
            "--summary",
            "完成 repo-local DAG、proposal、并发控制、目标对齐、todo 和 HTML 导出。",
            "--purpose",
            "Provide durable task structure for long-running projects.",
            "--acceptance",
            "validate 通过",
            "--acceptance",
            "HTML 导出通过回归检查",
            "--progress",
            "93",
            "--priority",
            "1",
            "--parent",
            root,
        ).stdout
    )
    dashboard = extract_node_id(
        cli(
            script,
            workspace,
            "add-node",
            "--kind",
            "subtask",
            "--status",
            "done",
            "--title",
            "Add task-forest to a shareable skills package",
            "--summary",
            "dashboard 同步是 task-forest 安装和可见性验收的一部分。",
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
            "Prepare a public-safe task-forest package",
            "--summary",
            "The public-safe package makes task-forest easier to share and reuse.",
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
            "Let downstream planning tools read task-forest exports",
            "--summary",
            "下游插件读取 exports 契约，不能直接修改正式任务图。",
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
            "显式支持 evergreen 长期目标生命周期",
            "--summary",
            "长期目标没有自然 100% 完成时刻，进度只是当前成熟度估计。",
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
            "重构 task-forest HTML 与 DAG 关系可视化",
            "--summary",
            "HTML/DAG 视图是 task-forest 完整实现与复核前完善的一部分。",
            "--progress",
            "100",
            "--priority",
            "1",
            "--parent",
            implementation,
        ).stdout
    )
    cli(script, workspace, "add-edge", "--from", integration, "--to", public, "--type", "depends_on", "--reason", "Downstream tools are safer after the export contract is stable.")
    cli(script, workspace, "add-edge", "--from", integration, "--to", root, "--type", "contributes_to", "--reason", "Downstream integrations contribute to the broader AI workbench.")
    cli(script, workspace, "add-edge", "--from", html, "--to", integration, "--type", "contributes_to", "--reason", "新增派生字段和可视化能力为下游读取提供稳定上游。")
    cli(script, workspace, "add-edge", "--from", evergreen, "--to", root, "--type", "clarifies", "--reason", "澄清长期目标生命周期风险的当前处理方式。")


def validate_exports(workspace: Path) -> None:
    export_dir = workspace / ".agent-workbench" / "task-forest" / "exports"
    graph_path = export_dir / "task-forest.graph.json"
    todo_path = export_dir / "task-forest.todos.json"
    timeline_path = export_dir / "task-forest.timeline.json"
    html_path = export_dir / "task-forest.html"
    for path in [graph_path, todo_path, timeline_path, html_path]:
        if not path.exists():
            raise AssertionError(f"缺少导出文件：{path}")
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
    if len(graph.get("status_queues", {}).get("review_needed", [])) < 2:
        raise AssertionError("样例图应包含至少两个待复核节点")
    if not todos:
        raise AssertionError("todo 导出不应为空")
    if len(timeline) < 2:
        raise AssertionError("timeline 应包含多个快照，供历史播放验证")

    assert_contains(
        html,
        [
            "树视图",
            "DAG 视图",
            "全部展开",
            "全部折叠",
            "清除筛选",
            "重置布局",
            "历史与队列",
            "节点详情",
            "边详情",
            "子任务",
            "依赖",
            "贡献",
            "澄清",
            "待复核要看什么",
            "复制通过复核指令",
            "复制记录缺口指令",
            "dag-node",
            "dag-edge-label",
            "startDagNodeDrag",
            "updateDagGeometry",
            "syncStickyOffsets",
            "--sticky-rail-top",
            "resetDagLayout",
            "playSnapshot",
            "zoomFit",
        ],
        "HTML",
    )
    assert_not_contains(html, ["父子分解", "DAG 边"], "HTML")


def main() -> int:
    parser = argparse.ArgumentParser(description="从零验证 task-forest 导出 HTML 是否满足可视化契约。")
    parser.add_argument("--skill-dir", required=True, help="task-forest skill 目录")
    parser.add_argument("--keep-workspace", action="store_true", help="保留临时 workspace，便于人工检查")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).expanduser().resolve()
    script = skill_dir / "scripts" / "task_forest.py"
    if not script.exists():
        raise SystemExit(f"找不到 task_forest.py：{script}")

    temp = tempfile.TemporaryDirectory(prefix="task-forest-export-")
    workspace = Path(temp.name) / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    try:
        build_sample_graph(script, workspace)
        cli(script, workspace, "validate")
        cli(script, workspace, "export")
        validate_exports(workspace)
        html_path = workspace / ".agent-workbench" / "task-forest" / "exports" / "task-forest.html"
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
