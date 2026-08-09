"""Build the single, client-readable task-forest HTML view."""

from __future__ import annotations

import copy
import html
import json
import re
from pathlib import Path
from typing import Any

from task_forest_ordering import sort_sibling_ids

OVERVIEW_STATUSES = {"done", "in_progress"}
OVERVIEW_FIELDS = {
    "id",
    "title",
    "kind",
    "status",
    "summary",
    "purpose",
    "desired_outcomes",
    "requirements",
    "acceptance_criteria",
    "success_metrics",
    "progress",
    "derived_progress",
    "primary_parent",
    "children",
}


def _nodes_by_id(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_nodes = graph.get("nodes", {})
    if isinstance(raw_nodes, dict):
        return {
            str(node_id): node
            for node_id, node in raw_nodes.items()
            if isinstance(node, dict)
        }
    if isinstance(raw_nodes, list):
        return {
            str(node.get("id")): node
            for node in raw_nodes
            if isinstance(node, dict) and node.get("id")
        }
    return {}


def _parents_from_structure(
    nodes: dict[str, dict[str, Any]], children: dict[str, list[str]]
) -> dict[str, str]:
    parents: dict[str, str] = {}
    for node_id, node in nodes.items():
        parent = node.get("primary_parent")
        if isinstance(parent, str) and parent in nodes:
            parents[node_id] = parent
    for parent, child_ids in children.items():
        for child in child_ids:
            parents.setdefault(child, parent)
    return parents


def _sort_sequenced_children(
    children: dict[str, list[str]], nodes: dict[str, dict[str, Any]]
) -> None:
    """Preserve source order without coupling the view to edge creation order."""

    for parent_id, child_ids in children.items():
        child_ids[:] = sort_sibling_ids(child_ids, nodes, parent_id)


def _children_from_graph(
    graph: dict[str, Any], nodes: dict[str, dict[str, Any]]
) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for node_id, node in nodes.items():
        raw_children = node.get("children")
        if not isinstance(raw_children, list):
            continue
        for child in raw_children:
            child_id = str(child)
            if child_id in nodes and child_id not in children[node_id]:
                children[node_id].append(child_id)
    raw_edges = graph.get("edges", {})
    edges = raw_edges.values() if isinstance(raw_edges, dict) else raw_edges
    if isinstance(edges, list) or hasattr(edges, "__iter__"):
        for edge in edges:
            if not isinstance(edge, dict) or edge.get("type") != "child_of":
                continue
            child = edge.get("from")
            parent = edge.get("to")
            if child in nodes and parent in nodes and child not in children[parent]:
                children[str(parent)].append(str(child))
    _sort_sequenced_children(children, nodes)
    return children


def overview_projection(graph: dict[str, Any]) -> dict[str, Any]:
    """Project one graph into the default communication view.

    Unknown fields fail closed.  Only completed and active nodes are visible;
    their ancestors are retained as hierarchy context and marked explicitly.
    """

    nodes = _nodes_by_id(graph)
    children = _children_from_graph(graph, nodes)
    parents = _parents_from_structure(nodes, children)
    visible_ids = {
        node_id
        for node_id, node in nodes.items()
        if node.get("status") in OVERVIEW_STATUSES
    }
    included_ids = set(visible_ids)
    resolved_ancestors: set[str] = set()
    for node_id in visible_ids:
        path: set[str] = set()
        current = node_id
        while (
            current in parents
            and current not in resolved_ancestors
            and current not in path
        ):
            path.add(current)
            parent = parents[current]
            included_ids.add(parent)
            current = parent
        resolved_ancestors.update(path)
        resolved_ancestors.add(current)

    projected_nodes: list[dict[str, Any]] = []
    for node_id in sorted(included_ids):
        node = nodes[node_id]
        projected = {
            key: copy.deepcopy(value)
            for key, value in node.items()
            if key in OVERVIEW_FIELDS
        }
        projected["id"] = node_id
        projected["contextOnly"] = node_id not in visible_ids
        projected["children"] = [
            child for child in children.get(node_id, []) if child in included_ids
        ]
        parent = parents.get(node_id)
        projected["primary_parent"] = parent if parent in included_ids else None
        projected_nodes.append(projected)

    included_with_parent = {
        node["id"]
        for node in projected_nodes
        if isinstance(node.get("primary_parent"), str)
    }
    root_ids = {
        node["id"] for node in projected_nodes if node["id"] not in included_with_parent
    }
    configured_roots = graph.get("roots", [])
    roots = (
        [root for root in configured_roots if root in root_ids]
        if isinstance(configured_roots, list)
        else []
    )
    remaining_roots = sorted(
        root_ids - set(roots),
        key=lambda node_id: (
            nodes[node_id].get("kind") != "global_task",
            node_id,
        ),
    )
    roots.extend(remaining_roots)
    done_count = sum(
        1 for node_id in visible_ids if nodes[node_id].get("status") == "done"
    )
    in_progress_count = sum(
        1 for node_id in visible_ids if nodes[node_id].get("status") == "in_progress"
    )
    return {
        "generatedAt": graph.get("generated_at"),
        "roots": roots,
        "nodes": projected_nodes,
        "summary": {
            "visibleNodeCount": len(visible_ids),
            "contextNodeCount": len(included_ids - visible_ids),
            "doneCount": done_count,
            "inProgressCount": in_progress_count,
        },
    }


def _projection_signature(data: dict[str, Any]) -> str:
    comparable = copy.deepcopy(data)
    comparable.pop("generatedAt", None)
    return json.dumps(
        comparable, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _baseline_projection() -> dict[str, Any]:
    return {
        "generatedAt": None,
        "roots": [],
        "nodes": [],
        "summary": {
            "visibleNodeCount": 0,
            "contextNodeCount": 0,
            "doneCount": 0,
            "inProgressCount": 0,
        },
    }


def overview_timeline(
    snapshots: list[dict[str, Any]], current: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build truthful history frames and an explicitly synthetic cold-start frame."""

    frames: list[dict[str, Any]] = []
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        raw_graph = snapshot.get("graph")
        if not isinstance(raw_graph, dict):
            continue
        frames.append(
            {
                "frameType": "saved_snapshot",
                "saved": True,
                "synthetic": False,
                "snapshotId": snapshot.get("snapshot_id"),
                "createdAt": snapshot.get("created_at"),
                "reason": snapshot.get("reason") or raw_graph.get("reason"),
                "data": overview_projection(raw_graph),
            }
        )

    if not frames:
        frames.append(
            {
                "frameType": "current_unsaved",
                "saved": False,
                "synthetic": False,
                "createdAt": current.get("generatedAt"),
                "data": current,
            }
        )
        return frames

    if _projection_signature(frames[-1]["data"]) == _projection_signature(current):
        frames[-1]["frameType"] = "current_snapshot"
        frames[-1]["data"] = current
    else:
        frames.append(
            {
                "frameType": "current_unsaved",
                "saved": False,
                "synthetic": False,
                "createdAt": current.get("generatedAt"),
                "data": current,
            }
        )

    if len(frames) == 1 and current.get("nodes"):
        frames.insert(
            0,
            {
                "frameType": "synthetic_baseline",
                "saved": False,
                "synthetic": True,
                "createdAt": None,
                "data": _baseline_projection(),
            },
        )
    return frames


def _html_json(data: Any) -> str:
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def replace_template_tokens(template: str, replacements: dict[str, str]) -> str:
    """Replace placeholders in one pass so inserted content is never rescanned."""

    if not replacements:
        return template
    pattern = re.compile("|".join(re.escape(key) for key in replacements))
    return pattern.sub(lambda match: replacements[match.group(0)], template)


def render_overview_html(graph: dict[str, Any], snapshots: list[dict[str, Any]]) -> str:
    current = overview_projection(graph)
    history = overview_timeline(snapshots, current)
    workspace_name = Path(str(graph.get("workspace_path") or "")).name or "workspace"
    nodes = {str(node.get("id")): node for node in current["nodes"]}
    root = nodes.get(current["roots"][0], {}) if current["roots"] else {}
    root_title = str(root.get("title") or "端到端建设目标")
    root_summary = str(
        root.get("summary")
        or root.get("purpose")
        or "展示已经完成与正在推进的功能建设。"
    )
    replacements = {
        "__TITLE__": html.escape(f"{root_title} - 建设进度"),
        "__WORKSPACE_NAME__": html.escape(workspace_name),
        "__ROOT_TITLE__": html.escape(root_title),
        "__ROOT_SUMMARY__": html.escape(root_summary),
        "__OVERVIEW_DATA__": _html_json(current),
        "__OVERVIEW_TIMELINE__": _html_json(history),
    }
    template_path = (
        Path(__file__).resolve().parent.parent / "assets" / "task-forest-overview.html"
    )
    template = template_path.read_text(encoding="utf-8")
    return replace_template_tokens(template, replacements)
