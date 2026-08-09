#!/usr/bin/env python3
"""Deterministic sibling ordering shared by task-forest exports and validation."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any


TASK_SEQUENCE_RE = re.compile(
    r"\bP(?P<phase>\d{2})(?:\.M(?P<module>\d{2}))?(?:\.T(?P<task>\d{2}))?\b",
    re.IGNORECASE,
)


def display_order_value(node: Mapping[str, Any]) -> float | None:
    """Return a finite numeric display order, or None when absent/invalid."""

    raw = node.get("display_order")
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    value = float(raw)
    return value if math.isfinite(value) else None


def task_sequence(node: Mapping[str, Any]) -> tuple[int, ...] | None:
    """Return the most specific P/M/T sequence found in tags or title."""

    tags = node.get("context_tags")
    values = [*tags] if isinstance(tags, list) else []
    values.append(node.get("title", ""))
    candidates: list[tuple[int, ...]] = []
    for value in values:
        for match in TASK_SEQUENCE_RE.finditer(str(value)):
            path = [int(match.group("phase"))]
            if match.group("module") is not None:
                path.append(int(match.group("module")))
            if match.group("task") is not None:
                path.append(int(match.group("task")))
            candidates.append(tuple(path))
    return max(candidates, key=len) if candidates else None


def relative_task_sequence(
    node: Mapping[str, Any], parent: Mapping[str, Any] | None
) -> tuple[int, ...] | None:
    """Return a business sequence only when it is meaningful under the parent."""

    child_path = task_sequence(node)
    if child_path is None:
        return None
    parent_path = task_sequence(parent) if parent is not None else None
    if parent_path is None:
        return child_path
    if (
        len(child_path) <= len(parent_path)
        or child_path[: len(parent_path)] != parent_path
    ):
        return None
    return child_path[len(parent_path) :]


def sort_sibling_ids(
    sibling_ids: Sequence[str],
    nodes: Mapping[str, Mapping[str, Any]],
    parent_id: str | None,
) -> list[str]:
    """Sort one sibling group without letting partial explicit order jump the queue."""

    known_ids = [node_id for node_id in sibling_ids if node_id in nodes]
    explicit = {node_id: display_order_value(nodes[node_id]) for node_id in known_ids}
    explicit_values = [value for value in explicit.values() if value is not None]
    if (
        known_ids
        and len(explicit_values) == len(known_ids)
        and len(set(explicit_values)) == len(explicit_values)
    ):
        return sorted(
            known_ids,
            key=lambda node_id: (
                explicit[node_id],
                str(nodes[node_id].get("created_at") or "\uffff"),
                node_id,
            ),
        )

    parent = nodes.get(parent_id) if parent_id is not None else None

    def fallback_key(node_id: str) -> tuple[object, ...]:
        node = nodes[node_id]
        sequence = relative_task_sequence(node, parent)
        created_at = str(node.get("created_at") or "\uffff")
        if sequence is not None:
            return (0, sequence, created_at, node_id)
        return (1, (), created_at, node_id)

    return sorted(known_ids, key=fallback_key)


def sibling_order_errors(
    nodes: Mapping[str, Mapping[str, Any]],
    groups: Mapping[str | None, Sequence[str]],
) -> list[str]:
    """Validate group-level display_order completeness, type, and uniqueness."""

    errors: list[str] = []
    for parent_id, sibling_ids in groups.items():
        known_ids = [node_id for node_id in sibling_ids if node_id in nodes]
        if not known_ids:
            continue
        specified = [
            node_id
            for node_id in known_ids
            if nodes[node_id].get("display_order") is not None
        ]
        invalid = [
            node_id
            for node_id in specified
            if display_order_value(nodes[node_id]) is None
        ]
        label = "根节点" if parent_id is None else f"父节点 {parent_id}"
        if invalid:
            errors.append(
                f"{label} 的 display_order 必须是有限数值：{', '.join(sorted(invalid))}"
            )
        if specified and len(specified) != len(known_ids):
            missing = sorted(set(known_ids) - set(specified))
            errors.append(
                f"{label} 只为部分兄弟节点设置 display_order；请补齐：{', '.join(missing)}"
            )
        if len(specified) == len(known_ids) and not invalid:
            by_value: dict[float, list[str]] = {}
            for node_id in specified:
                value = display_order_value(nodes[node_id])
                if value is not None:
                    by_value.setdefault(value, []).append(node_id)
            for value, duplicate_ids in sorted(by_value.items()):
                if len(duplicate_ids) > 1:
                    errors.append(
                        f"{label} 的 display_order {value:g} 重复："
                        + ", ".join(sorted(duplicate_ids))
                    )
    return errors
