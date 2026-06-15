#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import copy
import html
import json
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_LOCK_TIMEOUT_SECONDS = 30.0
DEFAULT_STALE_LOCK_SECONDS = 6 * 60 * 60
DEAD_PID_GRACE_SECONDS = 2.0
DEFAULT_AGENT_WORKBENCH_DB = Path.home() / ".agent-workbench" / "agent-workbench.sqlite3"

NODE_KINDS = {
    "global_task",
    "milestone",
    "task",
    "subtask",
    "requirement",
    "decision",
    "risk",
    "question",
    "follow_up",
}

NODE_STATUSES = {
    "proposed",
    "ready",
    "in_progress",
    "blocked",
    "review_needed",
    "done",
    "deprecated",
    "archived",
}

EDGE_TYPES = {
    "child_of",
    "depends_on",
    "contributes_to",
    "related_to",
    "duplicates",
    "supersedes",
    "clarifies",
    "derived_from",
}

BLOCKING_EDGE_TYPES = {"child_of", "depends_on"}
OPEN_STATUSES = {"proposed", "ready", "in_progress", "blocked", "review_needed"}
DONE_STATUSES = {"done", "deprecated", "archived"}
DIFFICULTIES = {"low", "medium", "high", "very_high", "unknown"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def clamp_progress(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(100.0, number))


def normalize_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def stable_registry_id(prefix: str, text: str) -> str:
    return f"{prefix}_{uuid.uuid5(uuid.NAMESPACE_URL, text).hex[:20]}"


def sha256_path(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def update_global_registry(workspace: Path, command: str, error: str | None = None) -> None:
    if os.environ.get("TASK_FOREST_DISABLE_GLOBAL_REGISTRY") in {"1", "true", "yes"}:
        return
    db_path = Path(os.environ.get("AGENT_WORKBENCH_DB") or DEFAULT_AGENT_WORKBENCH_DB).expanduser()
    root = workspace / ".agent-workbench" / "task-forest"
    exports = root / "exports"
    graph_path = exports / "task-forest.graph.json"
    todos_path = exports / "task-forest.todos.json"
    timeline_path = exports / "task-forest.timeline.json"
    html_path = exports / "task-forest.html"
    graph_hash = sha256_path(graph_path)
    status = "ok" if graph_path.exists() and todos_path.exists() and not error else "missing"
    if error:
        status = "error"
    summary = {
        "node_count": 0,
        "edge_count": 0,
        "ready_count": 0,
        "review_needed_count": 0,
        "blocked_count": 0,
        "evergreen_count": 0,
    }
    if graph_path.exists():
        try:
            graph = read_json(graph_path, {})
            queues = graph.get("status_queues") if isinstance(graph, dict) else {}
            if not isinstance(queues, dict):
                queues = {}
            nodes = graph.get("nodes") if isinstance(graph, dict) else {}
            edges = graph.get("edges") if isinstance(graph, dict) else {}
            summary.update(
                {
                    "node_count": len(nodes) if isinstance(nodes, (dict, list)) else 0,
                    "edge_count": len(edges) if isinstance(edges, (dict, list)) else 0,
                    "ready_count": len(queues.get("ready") or []),
                    "review_needed_count": len(queues.get("review_needed") or []),
                    "blocked_count": len(queues.get("blocked") or []),
                    "evergreen_count": len(queues.get("evergreen_open_goals") or []),
                }
            )
        except Exception as exc:  # noqa: BLE001 - registry must not break canonical task-forest.
            status = "error"
            error = f"读取导出摘要失败：{exc}"
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS aw_workspaces (
              workspace_id TEXT PRIMARY KEY,
              path TEXT NOT NULL UNIQUE,
              display_name TEXT,
              created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
              updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
              archived_at TEXT
            );
            CREATE TABLE IF NOT EXISTS aw_task_forests (
              forest_id TEXT PRIMARY KEY,
              workspace_id TEXT REFERENCES aw_workspaces(workspace_id) ON DELETE SET NULL,
              workspace_path TEXT NOT NULL UNIQUE,
              task_forest_root TEXT NOT NULL,
              exports_dir TEXT NOT NULL,
              graph_export_path TEXT NOT NULL,
              todos_export_path TEXT NOT NULL,
              timeline_export_path TEXT NOT NULL,
              html_export_path TEXT NOT NULL,
              last_graph_hash TEXT,
              last_export_at TEXT,
              node_count INTEGER NOT NULL DEFAULT 0 CHECK (node_count >= 0),
              edge_count INTEGER NOT NULL DEFAULT 0 CHECK (edge_count >= 0),
              ready_count INTEGER NOT NULL DEFAULT 0 CHECK (ready_count >= 0),
              review_needed_count INTEGER NOT NULL DEFAULT 0 CHECK (review_needed_count >= 0),
              blocked_count INTEGER NOT NULL DEFAULT 0 CHECK (blocked_count >= 0),
              evergreen_count INTEGER NOT NULL DEFAULT 0 CHECK (evergreen_count >= 0),
              status TEXT NOT NULL DEFAULT 'unknown' CHECK (status IN ('ok', 'missing', 'stale', 'error', 'unknown')),
              last_error TEXT,
              created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
              updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );
            CREATE TABLE IF NOT EXISTS aw_task_forest_runs (
              run_id TEXT PRIMARY KEY,
              forest_id TEXT REFERENCES aw_task_forests(forest_id) ON DELETE SET NULL,
              workspace_id TEXT REFERENCES aw_workspaces(workspace_id) ON DELETE SET NULL,
              workspace_path TEXT NOT NULL,
              command TEXT NOT NULL,
              status TEXT NOT NULL CHECK (status IN ('ok', 'missing', 'stale', 'error', 'unknown')),
              graph_hash_before TEXT,
              graph_hash_after TEXT,
              summary_json TEXT,
              error_excerpt TEXT,
              started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
              ended_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );
            CREATE INDEX IF NOT EXISTS idx_aw_task_forests_workspace ON aw_task_forests(workspace_path);
            CREATE INDEX IF NOT EXISTS idx_aw_task_forest_runs_forest ON aw_task_forest_runs(forest_id, ended_at DESC);
            """
        )
        workspace_id = stable_registry_id("ws", str(workspace))
        forest_id = stable_registry_id("tf", str(workspace))
        timestamp = now_iso()
        last_export_at = None
        existing = [path for path in [graph_path, todos_path, timeline_path, html_path] if path.exists()]
        if existing:
            last_export_at = datetime.fromtimestamp(max(path.stat().st_mtime for path in existing), timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        conn.execute(
            """
            INSERT INTO aw_workspaces(workspace_id, path, display_name, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET display_name = excluded.display_name, updated_at = excluded.updated_at
            """,
            (workspace_id, str(workspace), workspace.name, timestamp),
        )
        conn.execute(
            """
            INSERT INTO aw_task_forests(
              forest_id, workspace_id, workspace_path, task_forest_root, exports_dir,
              graph_export_path, todos_export_path, timeline_export_path, html_export_path,
              last_graph_hash, last_export_at, node_count, edge_count, ready_count,
              review_needed_count, blocked_count, evergreen_count, status, last_error, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(workspace_path) DO UPDATE SET
              workspace_id = excluded.workspace_id,
              task_forest_root = excluded.task_forest_root,
              exports_dir = excluded.exports_dir,
              graph_export_path = excluded.graph_export_path,
              todos_export_path = excluded.todos_export_path,
              timeline_export_path = excluded.timeline_export_path,
              html_export_path = excluded.html_export_path,
              last_graph_hash = excluded.last_graph_hash,
              last_export_at = excluded.last_export_at,
              node_count = excluded.node_count,
              edge_count = excluded.edge_count,
              ready_count = excluded.ready_count,
              review_needed_count = excluded.review_needed_count,
              blocked_count = excluded.blocked_count,
              evergreen_count = excluded.evergreen_count,
              status = excluded.status,
              last_error = excluded.last_error,
              updated_at = excluded.updated_at
            """,
            (
                forest_id,
                workspace_id,
                str(workspace),
                str(root),
                str(exports),
                str(graph_path),
                str(todos_path),
                str(timeline_path),
                str(html_path),
                graph_hash,
                last_export_at,
                summary["node_count"],
                summary["edge_count"],
                summary["ready_count"],
                summary["review_needed_count"],
                summary["blocked_count"],
                summary["evergreen_count"],
                status,
                error[:1000] if error else None,
                timestamp,
            ),
        )
        conn.execute(
            """
            INSERT INTO aw_task_forest_runs(
              run_id, forest_id, workspace_id, workspace_path, command, status,
              graph_hash_after, summary_json, error_excerpt, started_at, ended_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"tfrun_{uuid.uuid4().hex[:20]}",
                forest_id,
                workspace_id,
                str(workspace),
                command,
                status,
                graph_hash,
                json.dumps(summary, ensure_ascii=False, sort_keys=True),
                error[:1000] if error else None,
                timestamp,
                timestamp,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:  # noqa: BLE001 - registry must not break canonical task-forest.
        print(f"警告：task-forest 全局 registry 更新失败：{exc}", file=sys.stderr)


def stable_event_id() -> str:
    return f"tfevt_{uuid.uuid4().hex[:20]}"


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def graph_hash(nodes: dict[str, Any], edges: dict[str, Any]) -> str:
    payload = {"nodes": nodes, "edges": edges, "schema_version": SCHEMA_VERSION}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def resolve_workspace(raw: str | None) -> Path:
    return Path(raw or os.getcwd()).expanduser().resolve()


def state_root(workspace: Path, raw_root: str | None = None) -> Path:
    env_root = os.environ.get("TASK_FOREST_DIR")
    if raw_root:
        return Path(raw_root).expanduser().resolve()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return workspace / ".agent-workbench" / "task-forest"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


class FileLock:
    def __init__(
        self,
        path: Path,
        timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
        stale_seconds: float = DEFAULT_STALE_LOCK_SECONDS,
    ) -> None:
        self.path = path
        self.timeout = timeout
        self.stale_seconds = stale_seconds
        self.token = uuid.uuid4().hex
        self.fd: int | None = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self.timeout
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                metadata = {
                    "token": self.token,
                    "pid": os.getpid(),
                    "started_at": now_iso(),
                    "path": str(self.path),
                }
                os.write(self.fd, canonical_json(metadata).encode("utf-8"))
                os.write(self.fd, b"\n")
                os.fsync(self.fd)
                return self
            except FileExistsError:
                self._break_stale_lock_if_safe()
                if time.time() >= deadline:
                    owner = self._read_owner_text()
                    raise RuntimeError(f"无法获得锁：{self.path}；当前锁信息：{owner}")
                time.sleep(0.1)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self._unlink_if_owned()

    def _read_owner_text(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8").strip()
        except OSError:
            return "<无法读取锁文件>"

    def _read_metadata(self) -> dict[str, Any] | None:
        try:
            raw = self.path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            parts = raw.split()
            if not parts:
                return None
            try:
                pid = int(parts[0])
            except ValueError:
                pid = None
            return {"pid": pid, "started_at": parts[1] if len(parts) > 1 else None, "legacy": True}

    def _lock_age(self, metadata: dict[str, Any]) -> float | None:
        raw = metadata.get("started_at")
        if not isinstance(raw, str) or not raw:
            return None
        try:
            started = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        return max(0.0, (datetime.now(timezone.utc) - started).total_seconds())

    def _pid_alive(self, pid: Any) -> bool | None:
        if not isinstance(pid, int) or pid <= 0:
            return None
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return None

    def _break_stale_lock_if_safe(self) -> None:
        metadata = self._read_metadata()
        if not metadata:
            return
        age = self._lock_age(metadata)
        pid_alive = self._pid_alive(metadata.get("pid"))
        if pid_alive is True:
            return
        dead_pid_stale = pid_alive is False and age is not None and age >= DEAD_PID_GRACE_SECONDS
        unknown_stale = pid_alive is None and age is not None and age >= self.stale_seconds
        if not dead_pid_stale and not unknown_stale:
            return
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _unlink_if_owned(self) -> None:
        metadata = self._read_metadata()
        if metadata and metadata.get("token") != self.token:
            return
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class Store:
    def __init__(self, workspace: Path, root: Path) -> None:
        self.workspace = workspace
        self.root = root
        self.config_path = root / "config.json"
        self.nodes_path = root / "graph" / "nodes.json"
        self.edges_path = root / "graph" / "edges.json"
        self.forest_path = root / "graph" / "forest.json"
        self.events_path = root / "events" / "events.jsonl"
        self.deviations_path = root / "deviations" / "deviations.jsonl"
        self.alignments_path = root / "alignments" / "alignments.jsonl"
        self.todos_path = root / "todos" / "todos.json"
        self.lock_path = root / "lock"

    def lock(self, timeout: float | None = None) -> FileLock:
        return FileLock(
            self.lock_path,
            timeout=timeout if timeout is not None else DEFAULT_LOCK_TIMEOUT_SECONDS,
            stale_seconds=float(os.environ.get("TASK_FOREST_STALE_LOCK_SECONDS", DEFAULT_STALE_LOCK_SECONDS)),
        )

    def is_initialized(self) -> bool:
        return self.config_path.exists() and self.nodes_path.exists() and self.edges_path.exists()

    def ensure_dirs(self) -> None:
        for rel in [
            "graph",
            "events",
            "sessions",
            "proposals",
            "deviations",
            "alignments",
            "todos",
            "snapshots",
            "exports",
        ]:
            (self.root / rel).mkdir(parents=True, exist_ok=True)

    def init(self) -> None:
        self.ensure_dirs()
        created = False
        if not self.config_path.exists():
            config = {
                "schema_version": SCHEMA_VERSION,
                "workspace_path": str(self.workspace),
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "next_node_number": 1,
                "next_edge_number": 1,
                "next_snapshot_number": 1,
            }
            write_json_atomic(self.config_path, config)
            created = True
        if not self.nodes_path.exists():
            write_json_atomic(self.nodes_path, {})
            created = True
        if not self.edges_path.exists():
            write_json_atomic(self.edges_path, {})
            created = True
        if created:
            self.rebuild_generated(write_snapshot=False)

    def load(self, assume_locked: bool = False) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        if not self.is_initialized():
            if assume_locked:
                self.init()
            else:
                with self.lock():
                    self.init()
        config = read_json(self.config_path, {})
        nodes = read_json(self.nodes_path, {})
        edges = read_json(self.edges_path, {})
        return config, nodes, edges

    def save(self, config: dict[str, Any], nodes: dict[str, Any], edges: dict[str, Any]) -> None:
        config["updated_at"] = now_iso()
        config["graph_hash"] = graph_hash(nodes, edges)
        write_json_atomic(self.config_path, config)
        write_json_atomic(self.nodes_path, nodes)
        write_json_atomic(self.edges_path, edges)

    def next_node_id(self, config: dict[str, Any]) -> str:
        number = int(config.get("next_node_number", 1))
        config["next_node_number"] = number + 1
        return f"TF-{number:04d}"

    def next_edge_id(self, config: dict[str, Any]) -> str:
        number = int(config.get("next_edge_number", 1))
        config["next_edge_number"] = number + 1
        return f"TFE-{number:04d}"

    def next_snapshot_id(self, config: dict[str, Any]) -> str:
        number = int(config.get("next_snapshot_number", 1))
        config["next_snapshot_number"] = number + 1
        return f"{number:04d}"

    def record_event(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "event_id": stable_event_id(),
            "event_type": event_type,
            "actor": actor,
            "created_at": now_iso(),
            "workspace_path": str(self.workspace),
            "payload": payload,
            "before": before,
            "after": after,
        }
        append_jsonl(self.events_path, event)
        return event

    def write_snapshot(
        self,
        config: dict[str, Any],
        nodes: dict[str, Any],
        edges: dict[str, Any],
        reason: str,
        event_id: str | None,
    ) -> None:
        snapshot_id = self.next_snapshot_id(config)
        snapshot = build_export(config, nodes, edges, reason=reason, event_id=event_id)
        snapshot["snapshot_id"] = snapshot_id
        snapshot["created_at"] = now_iso()
        write_json_atomic(self.root / "snapshots" / f"{snapshot_id}.json", snapshot)

    def rebuild_generated(self, write_snapshot: bool = False) -> None:
        config, nodes, edges = read_json(self.config_path, {}), read_json(self.nodes_path, {}), read_json(self.edges_path, {})
        if not config:
            return
        export = build_export(config, nodes, edges, reason="rebuild", event_id=None)
        write_json_atomic(self.forest_path, export["graph"])
        write_json_atomic(self.todos_path, export["todos"])
        write_json_atomic(self.root / "exports" / "task-forest.graph.json", export["graph"])
        write_json_atomic(self.root / "exports" / "task-forest.todos.json", export["todos"])
        write_json_atomic(self.root / "exports" / "task-forest.timeline.json", load_snapshots(self.root))
        html_text = render_html(export["graph"], load_snapshots(self.root), export["todos"])
        (self.root / "exports").mkdir(parents=True, exist_ok=True)
        write_text_atomic(self.root / "exports" / "task-forest.html", html_text)
        if write_snapshot:
            self.write_snapshot(config, nodes, edges, "rebuild", None)
            write_json_atomic(self.config_path, config)


def node_defaults(node_id: str, title: str) -> dict[str, Any]:
    ts = now_iso()
    return {
        "id": node_id,
        "title": title.strip(),
        "kind": "task",
        "status": "proposed",
        "summary": "",
        "purpose": "",
        "desired_outcomes": [],
        "requirements": [],
        "acceptance_criteria": [],
        "success_metrics": [],
        "non_goals": [],
        "assumptions": [],
        "alignment": {
            "user_goal": "",
            "fit": "unknown",
            "fit_confidence": 0.0,
            "why_this_task": "",
            "why_not_enough": "",
            "validation_plan": [],
        },
        "alignment_records": [],
        "progress": 0.0,
        "progress_source": "manual",
        "priority": 3,
        "difficulty": "unknown",
        "estimated_total_minutes": None,
        "remaining_minutes_min": None,
        "remaining_minutes_max": None,
        "confidence": 0.6,
        "context_tags": [],
        "execution_hints": [],
        "source_sessions": [],
        "evidence": [],
        "deviations": [],
        "created_at": ts,
        "updated_at": ts,
        "deprecated_at": None,
    }


def normalize_node(raw: dict[str, Any], node_id: str, title: str | None = None) -> dict[str, Any]:
    base = node_defaults(node_id, title or str(raw.get("title", "")).strip())
    base.update(raw)
    base["id"] = node_id
    base["title"] = str(base.get("title", "")).strip()
    base["kind"] = str(base.get("kind", "task"))
    base["status"] = str(base.get("status", "proposed"))
    base["desired_outcomes"] = normalize_list(base.get("desired_outcomes"))
    base["requirements"] = normalize_list(base.get("requirements"))
    base["acceptance_criteria"] = normalize_list(base.get("acceptance_criteria"))
    base["success_metrics"] = normalize_list(base.get("success_metrics"))
    base["non_goals"] = normalize_list(base.get("non_goals"))
    base["assumptions"] = normalize_list(base.get("assumptions"))
    if not isinstance(base.get("alignment"), dict):
        base["alignment"] = node_defaults(node_id, base["title"])["alignment"]
    base["alignment"]["validation_plan"] = normalize_list(base["alignment"].get("validation_plan"))
    try:
        base["alignment"]["fit_confidence"] = float(base["alignment"].get("fit_confidence") or 0.0)
    except (TypeError, ValueError):
        base["alignment"]["fit_confidence"] = 0.0
    base["alignment_records"] = normalize_list(base.get("alignment_records"))
    base["context_tags"] = normalize_list(base.get("context_tags"))
    base["execution_hints"] = normalize_list(base.get("execution_hints"))
    base["source_sessions"] = normalize_list(base.get("source_sessions"))
    base["evidence"] = normalize_list(base.get("evidence"))
    base["deviations"] = normalize_list(base.get("deviations"))
    base["progress"] = clamp_progress(base.get("progress"))
    base["priority"] = int(base.get("priority") or 3)
    base["confidence"] = float(base.get("confidence") or 0.0)
    base["updated_at"] = now_iso()
    if not base.get("created_at"):
        base["created_at"] = now_iso()
    return base


def edge_defaults(edge_id: str, source: str, target: str, edge_type: str) -> dict[str, Any]:
    ts = now_iso()
    return {
        "id": edge_id,
        "from": source,
        "to": target,
        "type": edge_type,
        "blocking": edge_type in BLOCKING_EDGE_TYPES,
        "reason": "",
        "confidence": 0.6,
        "created_from_session": None,
        "created_at": ts,
        "updated_at": ts,
    }


def normalize_edge(raw: dict[str, Any], edge_id: str, source: str, target: str, edge_type: str) -> dict[str, Any]:
    base = edge_defaults(edge_id, source, target, edge_type)
    base.update(raw)
    base["id"] = edge_id
    base["from"] = source
    base["to"] = target
    base["type"] = edge_type
    base["blocking"] = bool(base.get("blocking", edge_type in BLOCKING_EDGE_TYPES))
    base["confidence"] = float(base.get("confidence") or 0.0)
    base["updated_at"] = now_iso()
    if not base.get("created_at"):
        base["created_at"] = now_iso()
    return base


def merge_fields(node: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(node)
    for key, value in fields.items():
        if key in {"id", "created_at"}:
            continue
        if key in {
            "desired_outcomes",
            "requirements",
            "acceptance_criteria",
            "success_metrics",
            "non_goals",
            "assumptions",
            "alignment_records",
            "context_tags",
            "execution_hints",
            "source_sessions",
            "evidence",
            "deviations",
        }:
            updated[key] = normalize_list(value)
        elif key == "progress":
            updated[key] = clamp_progress(value)
        else:
            updated[key] = value
    updated["updated_at"] = now_iso()
    return normalize_node(updated, node["id"])


def detect_cycle(edges: dict[str, Any], edge_type: str) -> list[str] | None:
    graph: dict[str, list[str]] = {}
    for edge in edges.values():
        if edge.get("type") == edge_type:
            graph.setdefault(edge["from"], []).append(edge["to"])
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            if node in stack:
                return stack[stack.index(node) :] + [node]
            return [node]
        if node in visited:
            return None
        visiting.add(node)
        stack.append(node)
        for nxt in graph.get(node, []):
            found = visit(nxt)
            if found:
                return found
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in list(graph):
        found = visit(node)
        if found:
            return found
    return None


def validate_state(nodes: dict[str, Any], edges: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    child_parent_count: dict[str, int] = {}
    seen_edge_keys: set[tuple[str, str, str]] = set()

    for node_id, node in nodes.items():
        if node.get("id") != node_id:
            errors.append(f"节点 key 与 id 不一致：{node_id}")
        if not str(node.get("title", "")).strip():
            errors.append(f"节点缺少 title：{node_id}")
        if node.get("kind") not in NODE_KINDS:
            errors.append(f"节点 {node_id} 的 kind 非法：{node.get('kind')}")
        if node.get("status") not in NODE_STATUSES:
            errors.append(f"节点 {node_id} 的 status 非法：{node.get('status')}")
        if node.get("difficulty") not in DIFFICULTIES:
            warnings.append(f"节点 {node_id} 的 difficulty 未规范化：{node.get('difficulty')}")
        if not (0 <= clamp_progress(node.get("progress")) <= 100):
            errors.append(f"节点 {node_id} 的 progress 非法")

    for edge_id, edge in edges.items():
        if edge.get("id") != edge_id:
            errors.append(f"边 key 与 id 不一致：{edge_id}")
        source = edge.get("from")
        target = edge.get("to")
        edge_type = edge.get("type")
        if edge_type not in EDGE_TYPES:
            errors.append(f"边 {edge_id} 的 type 非法：{edge_type}")
        if source not in nodes:
            errors.append(f"边 {edge_id} 指向不存在的 from 节点：{source}")
        if target not in nodes:
            errors.append(f"边 {edge_id} 指向不存在的 to 节点：{target}")
        if source == target:
            errors.append(f"边 {edge_id} 不能自指：{source}")
        key = (str(source), str(target), str(edge_type))
        if key in seen_edge_keys:
            errors.append(f"重复边：{source} -[{edge_type}]-> {target}")
        seen_edge_keys.add(key)
        if edge_type == "child_of":
            child_parent_count[str(source)] = child_parent_count.get(str(source), 0) + 1

    for node_id, count in child_parent_count.items():
        if count > 1:
            errors.append(f"节点 {node_id} 有多个 child_of 父节点；请改用 contributes_to 表达多归属")

    for edge_type in ("child_of", "depends_on"):
        cycle = detect_cycle(edges, edge_type)
        if cycle:
            errors.append(f"{edge_type} 出现环：{' -> '.join(cycle)}")

    return errors, warnings


def build_children(edges: dict[str, Any]) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {}
    for edge in edges.values():
        if edge.get("type") == "child_of":
            children.setdefault(edge["to"], []).append(edge["from"])
    for values in children.values():
        values.sort()
    return children


def build_parents(edges: dict[str, Any]) -> dict[str, str]:
    parents: dict[str, str] = {}
    for edge in edges.values():
        if edge.get("type") == "child_of":
            parents[edge["from"]] = edge["to"]
    return parents


def criterion_done(item: Any) -> bool:
    if isinstance(item, dict):
        return str(item.get("status", "")).lower() in {"done", "passed", "complete", "completed"}
    return False


def derived_progress(node_id: str, nodes: dict[str, Any], children: dict[str, list[str]], memo: dict[str, float]) -> float:
    if node_id in memo:
        return memo[node_id]
    node = nodes[node_id]
    if node.get("status") == "done":
        memo[node_id] = 100.0
        return memo[node_id]
    if node.get("status") in {"deprecated", "archived"}:
        memo[node_id] = clamp_progress(node.get("progress"))
        return memo[node_id]

    child_ids = children.get(node_id, [])
    criteria = normalize_list(node.get("acceptance_criteria"))
    if child_ids and node.get("progress_source") != "manual":
        value = sum(derived_progress(child, nodes, children, memo) for child in child_ids) / len(child_ids)
    elif criteria and all(isinstance(item, dict) for item in criteria):
        value = 100.0 * sum(1 for item in criteria if criterion_done(item)) / max(1, len(criteria))
    else:
        value = clamp_progress(node.get("progress"))
    memo[node_id] = round(value, 1)
    return memo[node_id]


def dependency_status(node_id: str, nodes: dict[str, Any], edges: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    for edge in edges.values():
        if edge.get("type") == "depends_on" and edge.get("from") == node_id:
            dep = edge.get("to")
            if dep in nodes and nodes[dep].get("status") != "done":
                blockers.append(dep)
    return len(blockers) == 0, blockers


def estimate_remaining(node: dict[str, Any], progress: float) -> tuple[int | None, int | None]:
    low = node.get("remaining_minutes_min")
    high = node.get("remaining_minutes_max")
    if isinstance(low, int) and isinstance(high, int):
        return low, high
    total = node.get("estimated_total_minutes")
    if isinstance(total, int) and total > 0:
        remaining = int(round(total * max(0.0, 100.0 - progress) / 100.0))
        return remaining, remaining
    return None, None


STATUS_LEGEND = {
    "proposed": "已提出但尚未确认或排期",
    "ready": "可开始执行，当前没有未满足依赖",
    "in_progress": "正在推进或作为长期目标持续演进",
    "blocked": "被依赖、信息或外部条件阻塞",
    "review_needed": "产物或判断已到可检查阶段，但需要复核验收标准、证据、不足风险和实际结果后，才能标为已完成。",
    "done": "已完成并通过验收",
    "deprecated": "已废止但保留历史",
    "archived": "已归档，通常不参与当前 todo",
}


EDGE_TYPE_LEGEND = {
    "child_of": "子任务关系：起点任务是目标任务的子任务，构成默认树/森林",
    "depends_on": "执行依赖边，起点任务必须等待目标任务完成",
    "contributes_to": "多目标贡献边，不改变主父节点",
    "related_to": "弱相关边，不影响 ready 或进度判断",
    "duplicates": "重复语义边，通常应合并或废止其中一个节点",
    "supersedes": "替代边，from 替代 to",
    "clarifies": "澄清边，起点任务澄清目标任务的要求或问题",
    "derived_from": "来源边，起点任务从目标任务拆解或派生",
}


def build_edge_view(edges: dict[str, Any]) -> dict[str, Any]:
    tree_edges: list[str] = []
    cross_edges: list[str] = []
    edge_type_counts: dict[str, int] = {edge_type: 0 for edge_type in sorted(EDGE_TYPES)}
    for edge_id, edge in edges.items():
        edge_type = str(edge.get("type"))
        edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
        if edge_type == "child_of":
            tree_edges.append(edge_id)
        else:
            cross_edges.append(edge_id)
    return {
        "tree_edges": sorted(tree_edges),
        "cross_edges": sorted(cross_edges),
        "edge_type_counts": edge_type_counts,
    }


def build_edge_index(nodes: dict[str, Any], edges: dict[str, Any]) -> dict[str, Any]:
    index = {
        node_id: {
            "incoming": [],
            "outgoing": [],
            "tree_parent_edge": None,
            "tree_child_edges": [],
            "blocking_edges": [],
            "cross_edges": [],
        }
        for node_id in nodes
    }
    for edge_id, edge in edges.items():
        source = edge.get("from")
        target = edge.get("to")
        edge_type = edge.get("type")
        if source in index:
            index[source]["outgoing"].append(edge_id)
            if edge.get("blocking"):
                index[source]["blocking_edges"].append(edge_id)
            if edge_type != "child_of":
                index[source]["cross_edges"].append(edge_id)
        if target in index:
            index[target]["incoming"].append(edge_id)
            if edge_type == "child_of":
                index[target]["tree_child_edges"].append(edge_id)
            elif edge_type != "child_of":
                index[target]["cross_edges"].append(edge_id)
        if edge_type == "child_of" and source in index:
            index[source]["tree_parent_edge"] = edge_id
    for value in index.values():
        for key, items in value.items():
            if isinstance(items, list):
                items.sort()
    return index


def build_status_queues(nodes: dict[str, Any], todos: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, list[str]] = {status: [] for status in sorted(NODE_STATUSES)}
    for node_id, node in nodes.items():
        by_status.setdefault(str(node.get("status")), []).append(node_id)
    for values in by_status.values():
        values.sort()
    actionable = [
        item["id"]
        for item in todos
        if not (item.get("kind") == "global_task" and item.get("status") == "in_progress" and item.get("remaining_minutes_min") is None)
    ]
    evergreen = [
        node_id
        for node_id, node in nodes.items()
        if node.get("kind") == "global_task"
        and node.get("status") in OPEN_STATUSES
        and node.get("progress_source") == "manual"
        and node.get("remaining_minutes_min") is None
    ]
    return {
        "by_status": by_status,
        "open": sorted([node_id for node_id, node in nodes.items() if node.get("status") in OPEN_STATUSES]),
        "review_needed": by_status.get("review_needed", []),
        "blocked": by_status.get("blocked", []),
        "ready": by_status.get("ready", []),
        "actionable_todos": actionable,
        "evergreen_open_goals": sorted(evergreen),
    }


def build_todos(nodes: dict[str, Any], edges: dict[str, Any], progress_by_id: dict[str, float]) -> list[dict[str, Any]]:
    todos: list[dict[str, Any]] = []
    for node_id, node in nodes.items():
        if node.get("status") not in OPEN_STATUSES:
            continue
        deps_satisfied, blockers = dependency_status(node_id, nodes, edges)
        progress = progress_by_id.get(node_id, clamp_progress(node.get("progress")))
        rem_min, rem_max = estimate_remaining(node, progress)
        todos.append(
            {
                "id": node_id,
                "title": node.get("title"),
                "purpose": node.get("purpose", ""),
                "kind": node.get("kind"),
                "status": node.get("status"),
                "progress": progress,
                "priority": node.get("priority", 3),
                "difficulty": node.get("difficulty", "unknown"),
                "remaining_minutes_min": rem_min,
                "remaining_minutes_max": rem_max,
                "ready": deps_satisfied and node.get("status") != "blocked",
                "blocked_by": blockers,
                "next_action": next_action_for(node, blockers),
                "confidence": node.get("confidence", 0.0),
                "context_tags": node.get("context_tags", []),
                "desired_outcomes": node.get("desired_outcomes", []),
                "success_metrics": node.get("success_metrics", []),
                "alignment": node.get("alignment", {}),
            }
        )
    todos.sort(key=lambda item: (not item["ready"], -int(item.get("priority") or 0), item["id"]))
    return todos


def next_action_for(node: dict[str, Any], blockers: list[str]) -> str:
    if blockers:
        return f"先完成依赖：{', '.join(blockers)}"
    if node.get("status") == "review_needed":
        return "复核产物并决定是否标记完成"
    if node.get("status") == "blocked":
        return "澄清阻塞原因并决定解除或废止"
    hints = normalize_list(node.get("execution_hints"))
    if hints:
        return str(hints[0])
    criteria = normalize_list(node.get("acceptance_criteria"))
    if criteria:
        first = criteria[0]
        if isinstance(first, dict):
            return str(first.get("text") or first.get("title") or "完成下一条验收标准")
        return str(first)
    return "补充下一步动作或开始执行"


def build_export(
    config: dict[str, Any],
    nodes: dict[str, Any],
    edges: dict[str, Any],
    reason: str,
    event_id: str | None,
) -> dict[str, Any]:
    children = build_children(edges)
    parents = build_parents(edges)
    progress_memo: dict[str, float] = {}
    progress_by_id = {node_id: derived_progress(node_id, nodes, children, progress_memo) for node_id in nodes}
    roots = [node_id for node_id in nodes if node_id not in parents]
    roots.sort(key=lambda nid: (nodes[nid].get("kind") != "global_task", nid))
    enriched_nodes = copy.deepcopy(nodes)
    for node_id, progress in progress_by_id.items():
        enriched_nodes[node_id]["derived_progress"] = progress
        enriched_nodes[node_id]["primary_parent"] = parents.get(node_id)
        enriched_nodes[node_id]["children"] = children.get(node_id, [])
    todos = build_todos(enriched_nodes, edges, progress_by_id)
    edge_view = build_edge_view(edges)
    status_queues = build_status_queues(enriched_nodes, todos)
    graph = {
        "schema_version": SCHEMA_VERSION,
        "workspace_path": config.get("workspace_path"),
        "generated_at": now_iso(),
        "reason": reason,
        "event_id": event_id,
        "roots": roots,
        "nodes": enriched_nodes,
        "edges": edges,
        "tree_edges": edge_view["tree_edges"],
        "cross_edges": edge_view["cross_edges"],
        "edge_index": build_edge_index(enriched_nodes, edges),
        "edge_type_counts": edge_view["edge_type_counts"],
        "status_queues": status_queues,
        "status_legend": STATUS_LEGEND,
        "edge_type_legend": EDGE_TYPE_LEGEND,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "open_count": sum(1 for node in nodes.values() if node.get("status") in OPEN_STATUSES),
            "done_count": sum(1 for node in nodes.values() if node.get("status") == "done"),
            "blocked_count": sum(1 for node in nodes.values() if node.get("status") == "blocked"),
            "review_needed_count": sum(1 for node in nodes.values() if node.get("status") == "review_needed"),
        },
    }
    return {"graph": graph, "todos": todos}


def load_snapshots(root: Path) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    snap_dir = root / "snapshots"
    if not snap_dir.exists():
        return snapshots
    for path in sorted(snap_dir.glob("*.json")):
        try:
            snapshots.append(read_json(path, {}))
        except json.JSONDecodeError:
            continue
    return snapshots


def add_node(
    config: dict[str, Any],
    nodes: dict[str, Any],
    fields: dict[str, Any],
    node_id: str | None = None,
) -> str:
    title = str(fields.get("title", "")).strip()
    if not title:
        raise ValueError("新增节点必须提供 title")
    actual_id = node_id or fields.get("id") or f"TF-{int(config.get('next_node_number', 1)):04d}"
    if actual_id in nodes:
        raise ValueError(f"节点已存在：{actual_id}")
    if actual_id.startswith("TF-") and actual_id == f"TF-{int(config.get('next_node_number', 1)):04d}":
        config["next_node_number"] = int(config.get("next_node_number", 1)) + 1
    node = normalize_node(fields, actual_id, title=title)
    nodes[actual_id] = node
    return actual_id


def add_edge(
    config: dict[str, Any],
    nodes: dict[str, Any],
    edges: dict[str, Any],
    source: str,
    target: str,
    edge_type: str,
    fields: dict[str, Any] | None = None,
    edge_id: str | None = None,
) -> str:
    if source not in nodes:
        raise ValueError(f"from 节点不存在：{source}")
    if target not in nodes:
        raise ValueError(f"to 节点不存在：{target}")
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"边类型非法：{edge_type}")
    if source == target:
        raise ValueError("边不能自指")
    actual_id = edge_id or config_id(config, "edge")
    edge = normalize_edge(fields or {}, actual_id, source, target, edge_type)
    edges[actual_id] = edge
    errors, _ = validate_state(nodes, edges)
    if errors:
        edges.pop(actual_id, None)
        raise ValueError("; ".join(errors))
    return actual_id


def config_id(config: dict[str, Any], kind: str) -> str:
    if kind == "edge":
        number = int(config.get("next_edge_number", 1))
        config["next_edge_number"] = number + 1
        return f"TFE-{number:04d}"
    raise ValueError(f"未知 ID 类型：{kind}")


def apply_changes(
    config: dict[str, Any],
    nodes: dict[str, Any],
    edges: dict[str, Any],
    changes: list[dict[str, Any]],
) -> dict[str, str]:
    aliases: dict[str, str] = {}

    def resolve(value: str) -> str:
        return aliases.get(value, value)

    for change in changes:
        action = change.get("action")
        if action == "add_node":
            raw_node = dict(change.get("node") or {})
            alias = change.get("alias") or raw_node.pop("alias", None)
            node_id = add_node(config, nodes, raw_node)
            if alias:
                aliases[str(alias)] = node_id
        elif action == "update_node":
            node_id = resolve(str(change.get("id")))
            if node_id not in nodes:
                raise ValueError(f"更新目标不存在：{node_id}")
            nodes[node_id] = merge_fields(nodes[node_id], dict(change.get("fields") or {}))
        elif action == "set_status":
            node_id = resolve(str(change.get("id")))
            if node_id not in nodes:
                raise ValueError(f"状态目标不存在：{node_id}")
            fields = {"status": change.get("status")}
            if "progress" in change:
                fields["progress"] = change.get("progress")
            nodes[node_id] = merge_fields(nodes[node_id], fields)
        elif action == "deprecate_node":
            node_id = resolve(str(change.get("id")))
            if node_id not in nodes:
                raise ValueError(f"废止目标不存在：{node_id}")
            nodes[node_id] = merge_fields(
                nodes[node_id],
                {"status": "deprecated", "deprecated_at": now_iso(), "summary": change.get("reason", nodes[node_id].get("summary", ""))},
            )
        elif action == "add_edge":
            source = resolve(str(change.get("from")))
            target = resolve(str(change.get("to")))
            add_edge(config, nodes, edges, source, target, str(change.get("type")), dict(change.get("edge") or {}))
        elif action == "remove_edge":
            edge_id = change.get("id")
            if edge_id:
                edges.pop(str(edge_id), None)
            else:
                source = resolve(str(change.get("from")))
                target = resolve(str(change.get("to")))
                edge_type = str(change.get("type"))
                to_remove = [eid for eid, edge in edges.items() if edge["from"] == source and edge["to"] == target and edge["type"] == edge_type]
                for eid in to_remove:
                    edges.pop(eid, None)
        elif action == "record_deviation":
            deviation = dict(change.get("deviation") or {})
            deviation.setdefault("id", f"TFD-{uuid.uuid4().hex[:10]}")
            deviation.setdefault("created_at", now_iso())
            related = [resolve(str(item)) for item in normalize_list(deviation.get("related_task_ids"))]
            deviation["related_task_ids"] = related
            for node_id in related:
                if node_id in nodes:
                    nodes[node_id].setdefault("deviations", []).append(deviation["id"])
            change["deviation"] = deviation
        elif action == "record_alignment":
            alignment = dict(change.get("alignment") or {})
            alignment.setdefault("id", f"TFA-{uuid.uuid4().hex[:10]}")
            alignment.setdefault("created_at", now_iso())
            related = [resolve(str(item)) for item in normalize_list(alignment.get("related_task_ids"))]
            alignment["related_task_ids"] = related
            for node_id in related:
                if node_id in nodes:
                    nodes[node_id].setdefault("alignment_records", []).append(alignment["id"])
                    if isinstance(alignment.get("node_alignment"), dict):
                        nodes[node_id]["alignment"] = alignment["node_alignment"]
                    nodes[node_id] = normalize_node(nodes[node_id], node_id)
            change["alignment"] = alignment
        else:
            raise ValueError(f"未知 proposal action：{action}")

    errors, _ = validate_state(nodes, edges)
    if errors:
        raise ValueError("; ".join(errors))
    return aliases


def load_text_arg(value: str | None, file_value: str | None) -> str:
    if file_value:
        return Path(file_value).expanduser().read_text(encoding="utf-8")
    return value or ""


def parse_json_arg(value: str | None, file_value: str | None, default: Any) -> Any:
    raw = load_text_arg(value, file_value).strip()
    if not raw:
        return default
    return json.loads(raw)


def print_human_node(node: dict[str, Any]) -> None:
    print(f"{node['id']} | {node.get('status')} | {node.get('kind')} | {node.get('derived_progress', node.get('progress', 0))}% | {node.get('title')}")
    if node.get("summary"):
        print(f"  摘要：{node['summary']}")
    if node.get("purpose"):
        print(f"  目的：{node['purpose']}")
    if node.get("primary_parent"):
        print(f"  主父节点：{node['primary_parent']}")
    if node.get("children"):
        print(f"  子节点：{', '.join(node['children'])}")


def cmd_init(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    with store.lock(args.lock_timeout):
        store.init()
        store.rebuild_generated()
    update_global_registry(workspace, "init")
    print(f"已初始化 task-forest：{store.root}")
    return 0


def cmd_add_node(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    with store.lock(args.lock_timeout):
        config, nodes, edges = store.load(assume_locked=True)
        before = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        fields = {
            "title": args.title,
            "kind": args.kind,
            "status": args.status,
            "summary": args.summary or "",
            "purpose": args.purpose or "",
            "desired_outcomes": args.desired_outcome,
            "requirements": args.requirement,
            "acceptance_criteria": args.acceptance,
            "success_metrics": args.success_metric,
            "non_goals": args.non_goal,
            "assumptions": args.assumption,
            "progress": args.progress,
            "priority": args.priority,
            "difficulty": args.difficulty,
            "estimated_total_minutes": args.estimate,
            "remaining_minutes_min": args.remaining_min,
            "remaining_minutes_max": args.remaining_max,
            "confidence": args.confidence,
            "context_tags": args.tag,
            "execution_hints": args.hint,
            "source_sessions": [args.session_id] if args.session_id else [],
            "evidence": args.evidence,
        }
        if args.alignment_json:
            fields["alignment"] = json.loads(args.alignment_json)
        extra = parse_json_arg(args.fields_json, args.fields_file, {})
        fields.update(extra)
        node_id = add_node(config, nodes, fields)
        for parent in args.parent:
            add_edge(config, nodes, edges, node_id, parent, "child_of", {"reason": "CLI add-node --parent"})
        for dep in args.depends_on:
            add_edge(config, nodes, edges, node_id, dep, "depends_on", {"reason": "CLI add-node --depends-on"})
        for target in args.contributes_to:
            add_edge(config, nodes, edges, node_id, target, "contributes_to", {"reason": "CLI add-node --contributes-to"})
        errors, _ = validate_state(nodes, edges)
        if errors:
            raise ValueError("; ".join(errors))
        after = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        event = store.record_event("add_node", args.actor, {"node_id": node_id, "title": args.title}, before, after)
        store.write_snapshot(config, nodes, edges, "add_node", event["event_id"])
        store.save(config, nodes, edges)
        store.rebuild_generated()
    print(f"已新增节点：{node_id}")
    return 0


def cmd_update_node(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    with store.lock(args.lock_timeout):
        config, nodes, edges = store.load(assume_locked=True)
        if args.id not in nodes:
            raise ValueError(f"节点不存在：{args.id}")
        before = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        fields: dict[str, Any] = {}
        for key in ["title", "kind", "status", "summary", "priority", "difficulty", "estimate", "remaining_min", "remaining_max", "confidence"]:
            value = getattr(args, key)
            if value is not None:
                target_key = {
                    "estimate": "estimated_total_minutes",
                    "remaining_min": "remaining_minutes_min",
                    "remaining_max": "remaining_minutes_max",
                }.get(key, key)
                fields[target_key] = value
        if args.progress is not None:
            fields["progress"] = args.progress
            fields["progress_source"] = "manual"
        for list_key, arg_name in [
            ("desired_outcomes", "desired_outcome"),
            ("success_metrics", "success_metric"),
            ("non_goals", "non_goal"),
            ("assumptions", "assumption"),
        ]:
            value = getattr(args, arg_name)
            if value:
                fields[list_key] = value
        if args.purpose is not None:
            fields["purpose"] = args.purpose
        if args.alignment_json:
            fields["alignment"] = json.loads(args.alignment_json)
        extra = parse_json_arg(args.fields_json, args.fields_file, {})
        fields.update(extra)
        updated = merge_fields(nodes[args.id], fields)
        for value in args.append_requirement:
            updated.setdefault("requirements", []).append(value)
        for value in args.append_acceptance:
            updated.setdefault("acceptance_criteria", []).append(value)
        for value in args.append_desired_outcome:
            updated.setdefault("desired_outcomes", []).append(value)
        for value in args.append_success_metric:
            updated.setdefault("success_metrics", []).append(value)
        for value in args.append_non_goal:
            updated.setdefault("non_goals", []).append(value)
        for value in args.append_assumption:
            updated.setdefault("assumptions", []).append(value)
        for value in args.append_tag:
            if value not in updated.setdefault("context_tags", []):
                updated["context_tags"].append(value)
        for value in args.append_hint:
            updated.setdefault("execution_hints", []).append(value)
        for value in args.append_evidence:
            updated.setdefault("evidence", []).append(value)
        nodes[args.id] = normalize_node(updated, args.id)
        errors, _ = validate_state(nodes, edges)
        if errors:
            raise ValueError("; ".join(errors))
        after = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        event = store.record_event("update_node", args.actor, {"node_id": args.id, "fields": sorted(fields)}, before, after)
        store.write_snapshot(config, nodes, edges, "update_node", event["event_id"])
        store.save(config, nodes, edges)
        store.rebuild_generated()
    print(f"已更新节点：{args.id}")
    return 0


def cmd_add_edge(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    with store.lock(args.lock_timeout):
        config, nodes, edges = store.load(assume_locked=True)
        before = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        edge_id = add_edge(
            config,
            nodes,
            edges,
            args.from_id,
            args.to_id,
            args.type,
            {"reason": args.reason or "", "confidence": args.confidence, "created_from_session": args.session_id},
        )
        after = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        event = store.record_event("add_edge", args.actor, {"edge_id": edge_id}, before, after)
        store.write_snapshot(config, nodes, edges, "add_edge", event["event_id"])
        store.save(config, nodes, edges)
        store.rebuild_generated()
    print(f"已新增边：{edge_id}")
    return 0


def cmd_remove_edge(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    if not args.id and not (args.from_id and args.to_id and args.type):
        raise ValueError("删除边时必须提供 --id，或同时提供 --from、--to、--type")
    with store.lock(args.lock_timeout):
        config, nodes, edges = store.load(assume_locked=True)
        before = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        removed: list[str] = []
        if args.id:
            if args.id in edges:
                removed.append(args.id)
                edges.pop(args.id)
        else:
            for edge_id, edge in list(edges.items()):
                if edge["from"] == args.from_id and edge["to"] == args.to_id and edge["type"] == args.type:
                    removed.append(edge_id)
                    edges.pop(edge_id)
        errors, _ = validate_state(nodes, edges)
        if errors:
            raise ValueError("; ".join(errors))
        after = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        event = store.record_event("remove_edge", args.actor, {"removed": removed}, before, after)
        store.write_snapshot(config, nodes, edges, "remove_edge", event["event_id"])
        store.save(config, nodes, edges)
        store.rebuild_generated()
    print(f"已删除边：{', '.join(removed) if removed else '无匹配边'}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    with store.lock(args.lock_timeout):
        config, nodes, edges = store.load(assume_locked=True)
    graph = build_export(config, nodes, edges, "list", None)["graph"]
    items = list(graph["nodes"].values())
    if args.status:
        items = [item for item in items if item.get("status") == args.status]
    if args.kind:
        items = [item for item in items if item.get("kind") == args.kind]
    if args.tag:
        items = [item for item in items if args.tag in item.get("context_tags", [])]
    items.sort(key=lambda item: (item.get("primary_parent") or "", item["id"]))
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not items:
        print("没有匹配节点。")
        return 0
    for item in items[: args.limit]:
        print_human_node(item)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    with store.lock(args.lock_timeout):
        config, nodes, edges = store.load(assume_locked=True)
    graph = build_export(config, nodes, edges, "show", None)["graph"]
    node = graph["nodes"].get(args.id)
    if not node:
        raise ValueError(f"节点不存在：{args.id}")
    if args.json:
        print(json.dumps(node, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human_node(node)
        related = [edge for edge in graph["edges"].values() if edge["from"] == args.id or edge["to"] == args.id]
        for edge in related:
            print(f"  边：{edge['id']} {edge['from']} -[{edge['type']}]-> {edge['to']}")
    return 0


def cmd_todo(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    with store.lock(args.lock_timeout):
        config, nodes, edges = store.load(assume_locked=True)
    todos = build_export(config, nodes, edges, "todo", None)["todos"]
    if args.ready:
        todos = [item for item in todos if item["ready"]]
    if args.json:
        print(json.dumps(todos, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not todos:
        print("当前没有未完成任务。")
        return 0
    for item in todos[: args.limit]:
        estimate = "未知"
        if item["remaining_minutes_min"] is not None:
            estimate = f"{item['remaining_minutes_min']}-{item['remaining_minutes_max']} 分钟"
        ready = "ready" if item["ready"] else "blocked"
        print(f"{item['id']} | {ready} | P{item['priority']} | {item['progress']}% | {estimate} | {item['title']}")
        print(f"  下一步：{item['next_action']}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    with store.lock(args.lock_timeout):
        store.init()
        store.rebuild_generated()
    update_global_registry(workspace, "export")
    print(f"已导出：{store.root / 'exports' / 'task-forest.html'}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    with store.lock(args.lock_timeout):
        _, nodes, edges = store.load(assume_locked=True)
    errors, warnings = validate_state(nodes, edges)
    for warning in warnings:
        print(f"警告：{warning}")
    for error in errors:
        print(f"错误：{error}")
    if errors:
        update_global_registry(workspace, "validate", error="; ".join(errors))
        return 1
    update_global_registry(workspace, "validate")
    print("校验通过。")
    return 0


def cmd_proposal_save(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    with store.lock(args.lock_timeout):
        config, nodes, edges = store.load(assume_locked=True)
        proposal = parse_json_arg(args.proposal_json, args.proposal_file, {})
        if not isinstance(proposal, dict):
            raise ValueError("proposal 必须是 JSON object")
        proposal_id = proposal.get("proposal_id") or f"TFP-{uuid.uuid4().hex[:10]}"
        proposal["proposal_id"] = proposal_id
        proposal.setdefault("session_id", args.session_id)
        proposal.setdefault("status", "proposed")
        proposal.setdefault("created_at", now_iso())
        proposal.setdefault("changes", [])
        proposal.setdefault("base_graph_hash", graph_hash(nodes, edges))
        proposal.setdefault(
            "base_summary",
            {"node_count": len(nodes), "edge_count": len(edges), "workspace_path": str(workspace)},
        )
        dry_config, dry_nodes, dry_edges = copy.deepcopy(config), copy.deepcopy(nodes), copy.deepcopy(edges)
        apply_changes(dry_config, dry_nodes, dry_edges, list(proposal["changes"]))
        proposal_path = store.root / "proposals" / f"{proposal_id}.json"
        if proposal_path.exists() and not args.overwrite:
            raise ValueError(f"proposal 已存在：{proposal_id}；如确需替换请传入 --overwrite")
        write_json_atomic(proposal_path, proposal)
    update_global_registry(workspace, "proposal-save")
    print(f"已保存变更提案：{proposal_id}")
    return 0


def load_proposal(store: Store, value: str) -> tuple[Path, dict[str, Any]]:
    raw_path = Path(value).expanduser()
    path = raw_path if raw_path.exists() else store.root / "proposals" / f"{value}.json"
    if not path.exists():
        raise ValueError(f"proposal 不存在：{value}")
    return path, read_json(path, {})


def cmd_proposal_apply(args: argparse.Namespace) -> int:
    if not args.yes:
        raise ValueError("应用 proposal 必须显式传入 --yes")
    workspace = resolve_workspace(args.workspace)
    store = Store(workspace, state_root(workspace, args.root))
    with store.lock(args.lock_timeout):
        config, nodes, edges = store.load(assume_locked=True)
        proposal_path, proposal = load_proposal(store, args.proposal)
        if proposal.get("status") == "applied" and not args.allow_reapply:
            raise ValueError(f"proposal 已经应用过：{proposal.get('proposal_id')}")
        base_hash = proposal.get("base_graph_hash")
        current_hash = graph_hash(nodes, edges)
        if base_hash and base_hash != current_hash and not args.allow_stale:
            raise ValueError(
                "proposal 基于旧任务图，当前任务图已被其他 session 修改；"
                "请重新生成 proposal，或人工确认无冲突后传入 --allow-stale"
            )
        changes = list(proposal.get("changes") or [])
        before = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        apply_changes(config, nodes, edges, changes)
        after = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        event = store.record_event(
            "proposal_applied",
            args.actor,
            {"proposal_id": proposal.get("proposal_id"), "session_id": proposal.get("session_id"), "change_count": len(changes)},
            before,
            after,
        )
        for change in changes:
            if change.get("action") == "record_deviation":
                append_jsonl(store.deviations_path, change["deviation"])
            if change.get("action") == "record_alignment":
                append_jsonl(store.alignments_path, change["alignment"])
        proposal["status"] = "applied"
        proposal["applied_at"] = now_iso()
        write_json_atomic(proposal_path, proposal)
        store.write_snapshot(config, nodes, edges, "proposal_applied", event["event_id"])
        store.save(config, nodes, edges)
        store.rebuild_generated()
    update_global_registry(workspace, "proposal-apply")
    print(f"已应用变更提案：{proposal.get('proposal_id')}")
    return 0


def html_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def render_html(graph: dict[str, Any], snapshots: list[dict[str, Any]], todos: list[dict[str, Any]]) -> str:
    title = f"任务森林 - {Path(str(graph.get('workspace_path') or '')).name or 'workspace'}"
    replacements = {
        "__TITLE__": html.escape(title),
        "__GRAPH_DATA__": html_json(graph),
        "__SNAPSHOTS_DATA__": html_json(snapshots),
        "__TODOS_DATA__": html_json(todos),
    }
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root {
      --bg: #f7f8fb;
      --panel: #ffffff;
      --panel-2: #fafbfc;
      --text: #182133;
      --muted: #6b7484;
      --line: #d8dee8;
      --soft-line: #edf1f6;
      --blue: #2f6fe4;
      --green: #12845a;
      --amber: #b7791f;
      --red: #c2413b;
      --purple: #6d5bd0;
      --gray: #64748b;
      --shadow: 0 1px 2px rgba(16, 24, 40, 0.05), 0 12px 32px rgba(16, 24, 40, 0.07);
      --radius: 8px;
      --sticky-rail-top: 96px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      --left-col: minmax(290px, 330px);
      --right-col: minmax(330px, 420px);
    }
    body.left-collapsed { --left-col: 48px; }
    body.right-collapsed { --right-col: 48px; }
    button, input, select { font: inherit; }
    button { border: 1px solid var(--line); background: #fff; color: var(--text); border-radius: var(--radius); padding: 6px 10px; cursor: pointer; }
    button:hover { border-color: #a9b4c2; background: #f8fafc; }
    button.active, button[aria-pressed="true"] { border-color: var(--blue); color: #1e56bd; background: #eef5ff; }
    button:disabled { opacity: 0.48; cursor: not-allowed; }
    header { padding: 18px 24px; border-bottom: 1px solid var(--line); background: var(--panel); position: sticky; top: 0; z-index: 5; }
    h1 { margin: 0 0 10px; font-size: 22px; letter-spacing: 0; }
    .meta { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; color: var(--muted); font-size: 13px; }
    .summary-chip { display: inline-flex; gap: 5px; align-items: center; border-radius: 999px; padding: 5px 10px; border: 1px solid var(--line); background: #fff; color: var(--muted); font-weight: 650; }
    button.summary-chip { cursor: pointer; }
    button.summary-chip:hover { border-color: var(--blue); background: #f8fbff; }
    .summary-chip strong { color: inherit; font-weight: 780; }
    .summary-chip.is-filtered { border-color: var(--blue); background: #eef5ff; color: #1e56bd; }
    .layout { display: grid; grid-template-columns: var(--left-col) minmax(420px, 1fr) var(--right-col); gap: 16px; padding: 16px; align-items: stretch; transition: grid-template-columns 160ms ease; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); min-height: 80px; overflow: hidden; box-shadow: 0 1px 2px rgba(16, 24, 40, 0.03); }
    .panel h2 { margin: 0; padding: 13px 16px; font-size: 15px; border-bottom: 1px solid var(--line); }
    .panel-body { padding: 14px 16px; }
    .side-panel { max-height: calc(100vh - 136px); display: flex; flex-direction: column; min-width: 0; }
    .side-panel-content { overflow: auto; min-height: 0; }
    .panel-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--line); background: #fff; }
    .panel-title h2 { margin: 0; padding: 0; border: 0; font-size: 15px; }
    .panel-title button { width: 28px; height: 28px; padding: 0; display: inline-flex; align-items: center; justify-content: center; color: var(--muted); }
    body.left-collapsed .left-panel .side-panel-content,
    body.right-collapsed .right-panel .side-panel-content { display: none; }
    body.left-collapsed .left-panel,
    body.right-collapsed .right-panel {
      position: sticky;
      top: var(--sticky-rail-top);
      align-self: start;
      z-index: 4;
      min-height: min(520px, calc(100vh - var(--sticky-rail-top) - 16px));
      height: min(520px, calc(100vh - var(--sticky-rail-top) - 16px));
      max-height: calc(100vh - var(--sticky-rail-top) - 16px);
    }
    body.left-collapsed .left-panel .panel-title,
    body.right-collapsed .right-panel .panel-title { height: 100%; flex-direction: column; justify-content: flex-start; padding: 8px 5px; }
    body.left-collapsed .left-panel .panel-title h2,
    body.right-collapsed .right-panel .panel-title h2 { writing-mode: vertical-rl; text-orientation: mixed; font-size: 13px; line-height: 1.2; margin-top: 6px; }
    body.left-collapsed .left-panel .panel-title button,
    body.right-collapsed .right-panel .panel-title button { order: -1; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 12px; border-bottom: 1px solid var(--line); background: #fff; position: static; z-index: 1; }
    .toolbar-group { display: inline-flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .toolbar-spacer { flex: 1 1 28px; }
    .toolbar input[type="search"] { min-width: min(280px, 100%); flex: 1 1 320px; border: 1px solid var(--line); border-radius: 7px; padding: 7px 9px; }
    .zoom-controls { display: inline-flex; gap: 6px; align-items: center; margin-left: auto; }
    .zoom-controls button { min-width: 34px; }
    .zoom-label { min-width: 46px; text-align: center; color: var(--muted); font-size: 12px; }
    .active-filter { color: var(--muted); font-size: 12px; padding: 8px 12px; border-bottom: 1px solid var(--soft-line); background: #fbfcfe; }
    .timeline input[type="range"] { width: 100%; }
    .timeline-controls { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; }
    .timeline-controls select { border: 1px solid var(--line); border-radius: 7px; padding: 6px 8px; background: #fff; }
    .toggle-line { display: inline-flex; gap: 5px; align-items: center; color: var(--muted); font-size: 12px; }
    .snapshot-label { margin-top: 8px; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .snapshot-diff { margin-top: 10px; padding: 9px 10px; border: 1px solid var(--soft-line); background: var(--panel-2); border-radius: 7px; font-size: 12px; line-height: 1.45; color: var(--muted); }
    .queue-block { margin-bottom: 14px; }
    .queue-title { display: flex; justify-content: space-between; color: var(--muted); font-size: 12px; font-weight: 750; margin-bottom: 7px; }
    .todo, .queue-item { padding: 9px 0; border-bottom: 1px solid #eef1f5; cursor: pointer; }
    .todo:hover, .queue-item:hover { background: #fafcff; }
    .todo:last-child, .queue-item:last-child { border-bottom: 0; }
    .todo-title, .queue-title-line { font-weight: 700; font-size: 13px; line-height: 1.35; }
    .todo-meta, .queue-meta { margin-top: 5px; color: var(--muted); font-size: 12px; line-height: 1.4; }
    .legend { display: grid; gap: 6px; }
    details.legend-details { border-top: 1px solid var(--line); }
    details.legend-details summary { padding: 12px 16px; cursor: pointer; font-size: 13px; font-weight: 750; color: var(--text); }
    .legend-row { display: grid; grid-template-columns: 92px 1fr; gap: 8px; font-size: 12px; line-height: 1.35; color: var(--muted); }
    .forest { overflow: hidden; display: flex; flex-direction: column; min-width: 0; }
    .canvas { padding: 24px 16px 28px; overflow: hidden; min-height: 680px; position: relative; cursor: grab; background-color: #fbfcfe; background-image: radial-gradient(#e8edf4 0.7px, transparent 0.7px); background-size: 20px 20px; }
    .canvas.dragging { cursor: grabbing; user-select: none; }
    .tree-viewport { display: inline-block; min-width: max-content; transform-origin: 0 0; will-change: transform; }
    .tree-list, .tree-list ul { list-style: none; margin: 0; padding: 0; }
    .tree-list { display: flex; justify-content: center; align-items: flex-start; min-width: max-content; }
    .tree-list li { position: relative; display: flex; flex-direction: column; align-items: center; padding: 0 8px; }
    .tree-list > li { padding-top: 0; }
    .tree-list ul { display: flex; justify-content: center; align-items: flex-start; gap: 15px; position: relative; padding-top: 30px; margin-top: 12px; min-width: max-content; }
    .tree-list ul::before { content: ""; position: absolute; top: 0; left: 50%; height: 16px; border-left: 2px solid var(--line); }
    .tree-list ul > li::before { content: ""; position: absolute; top: -16px; left: 50%; height: 16px; border-left: 2px solid var(--line); }
    .tree-list ul > li::after { content: ""; position: absolute; top: -16px; left: 0; right: 0; border-top: 2px solid var(--line); }
    .tree-list ul > li:first-child::after { left: 50%; }
    .tree-list ul > li:last-child::after { right: 50%; }
    .tree-list ul > li:only-child::after { display: none; }
    .node { width: clamp(132px, 11vw, 168px); min-height: 58px; border: 1px solid var(--line); border-left: 4px solid var(--gray); border-radius: var(--radius); padding: 8px 9px; background: #fff; cursor: pointer; box-shadow: 0 1px 2px rgba(16, 24, 40, 0.035); overflow: hidden; }
    .node:hover { border-color: #9aa7b7; }
    .node.active { outline: 2px solid rgba(37, 99, 235, 0.28); box-shadow: var(--shadow); }
    .node.context-only { opacity: 0.62; }
    .node.done { border-left-color: var(--green); }
    .node.in_progress, .node.ready, .node.proposed { border-left-color: var(--blue); }
    .node.blocked { border-left-color: var(--amber); }
    .node.review_needed { border-left-color: var(--red); }
    .node.deprecated, .node.archived { opacity: 0.58; }
    .node-head { display: grid; grid-template-columns: auto 1fr; gap: 6px; align-items: start; min-width: 0; }
    .node-toggle { width: 18px; height: 18px; padding: 0; line-height: 1; border-radius: 6px; color: var(--muted); font-size: 11px; }
    .node-toggle.empty { visibility: hidden; }
    .node-title { min-width: 0; font-size: 12px; font-weight: 760; line-height: 1.32; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow-wrap: anywhere; }
    .bar { height: 5px; border-radius: 999px; background: #e4e8ef; overflow: hidden; margin-top: 8px; }
    .bar span { display: block; height: 100%; background: #2f6fe4; }
    .node.done .bar span { background: var(--green); }
    .node.review_needed .bar span { background: #cc514a; }
    .node.blocked .bar span { background: var(--amber); }
    .edge-chip, .badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 7px; border-radius: 999px; background: #eef2ff; color: #3730a3; font-size: 11px; margin: 3px 4px 0 0; border: 0; }
    .edge-chip { cursor: pointer; border: 1px solid #dbe4ff; }
    .edge-chip:hover { background: #e0e7ff; }
    .edge-chip.depends_on { background: #fff7ed; color: #9a3412; border-color: #fed7aa; }
    .edge-chip.contributes_to { background: #f5f3ff; color: #5b21b6; border-color: #ddd6fe; }
    .edge-chip.child_of { background: #ecfdf5; color: #166534; border-color: #bbf7d0; }
    .edge-chip.related_to { background: #f8fafc; color: #475569; border-color: #e2e8f0; }
    .edge-chip.duplicates { background: #fff1f2; color: #9f1239; border-color: #fecdd3; }
    .edge-chip.supersedes { background: #ecfeff; color: #0e7490; border-color: #a5f3fc; }
    .edge-chip.clarifies { background: #eef2ff; color: #3730a3; border-color: #c7d2fe; }
    .edge-chip.derived_from { background: #f0fdf4; color: #166534; border-color: #bbf7d0; }
    .edge-panel { border-top: 1px solid var(--line); padding: 14px 16px 16px; background: #fbfcfe; }
    .edge-panel h3 { margin: 0 0 10px; font-size: 14px; }
    .edge-list { display: grid; gap: 8px; }
    .edge-card { border: 1px solid var(--line); border-left: 4px solid var(--gray); border-radius: var(--radius); padding: 9px 10px; background: #fff; cursor: pointer; }
    .edge-card:hover, .edge-card.active { border-color: var(--blue); background: #eff6ff; }
    .edge-card.depends_on, .edge-row.depends_on { border-left-color: var(--amber); }
    .edge-card.contributes_to, .edge-row.contributes_to { border-left-color: var(--purple); }
    .edge-card.child_of, .edge-row.child_of { border-left-color: var(--green); }
    .edge-card.clarifies, .edge-row.clarifies { border-left-color: var(--blue); }
    .edge-card.duplicates, .edge-row.duplicates { border-left-color: var(--red); }
    .edge-card.supersedes, .edge-row.supersedes { border-left-color: #0891b2; }
    .edge-card.related_to, .edge-row.related_to { border-left-color: #64748b; }
    .edge-card.derived_from, .edge-row.derived_from { border-left-color: #15803d; }
    .edge-card-title { font-size: 12px; font-weight: 750; }
    .edge-card-meta { color: var(--muted); font-size: 12px; line-height: 1.4; margin-top: 4px; }
    .dag-graph { position: relative; min-width: max-content; min-height: max-content; }
    .dag-svg { position: absolute; inset: 0; overflow: visible; pointer-events: auto; }
    .dag-edge { pointer-events: stroke; fill: none; stroke-width: 2.4; stroke-linecap: round; cursor: pointer; opacity: 0.86; }
    .dag-edge:hover, .dag-edge.active { stroke-width: 4; opacity: 1; }
    .dag-edge.child_of { stroke: var(--green); }
    .dag-edge.depends_on { stroke: var(--amber); }
    .dag-edge.contributes_to { stroke: var(--purple); }
    .dag-edge.clarifies { stroke: var(--blue); }
    .dag-edge.duplicates { stroke: var(--red); stroke-dasharray: 7 5; }
    .dag-edge.supersedes { stroke: #0891b2; }
    .dag-edge.related_to { stroke: #64748b; stroke-dasharray: 4 5; }
    .dag-edge.derived_from { stroke: #15803d; stroke-dasharray: 8 4; }
    .dag-arrow.child_of { fill: var(--green); }
    .dag-arrow.depends_on { fill: var(--amber); }
    .dag-arrow.contributes_to { fill: var(--purple); }
    .dag-arrow.clarifies { fill: var(--blue); }
    .dag-arrow.duplicates { fill: var(--red); }
    .dag-arrow.supersedes { fill: #0891b2; }
    .dag-arrow.related_to { fill: #64748b; }
    .dag-arrow.derived_from { fill: #15803d; }
    .dag-edge-hit { pointer-events: stroke; fill: none; stroke: transparent; stroke-width: 14; cursor: pointer; }
    .dag-node { position: absolute; width: 154px; min-height: 58px; border: 1px solid var(--line); border-left: 4px solid var(--gray); border-radius: var(--radius); padding: 8px 9px; background: #fff; box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04); cursor: grab; touch-action: none; user-select: none; }
    .dag-node:hover { border-color: #a9b4c2; }
    .dag-node.active { outline: 2px solid rgba(37, 99, 235, 0.28); box-shadow: var(--shadow); }
    .dag-node.dragging { cursor: grabbing; z-index: 4; box-shadow: var(--shadow); }
    .dag-node.done { border-left-color: var(--green); }
    .dag-node.in_progress, .dag-node.ready, .dag-node.proposed { border-left-color: var(--blue); }
    .dag-node.blocked { border-left-color: var(--amber); }
    .dag-node.review_needed { border-left-color: var(--red); }
    .dag-node-title { font-size: 12px; font-weight: 760; line-height: 1.32; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow-wrap: anywhere; }
    .dag-node-meta { margin-top: 4px; color: var(--muted); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .dag-edge-label { position: absolute; transform: translate(-50%, -50%); padding: 2px 7px; border-radius: 999px; border: 1px solid var(--line); background: rgba(255,255,255,0.94); color: var(--muted); font-size: 11px; pointer-events: auto; cursor: pointer; box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04); }
    .dag-edge-label:hover, .dag-edge-label.active { border-color: var(--blue); color: #1e56bd; background: #eef5ff; }
    .dag-legend { position: absolute; left: 0; top: 0; display: flex; gap: 6px; flex-wrap: wrap; align-items: center; max-width: 760px; padding: 8px 10px; border: 1px solid var(--line); border-left: 4px solid var(--blue); border-radius: var(--radius); background: rgba(255,255,255,0.95); color: var(--muted); font-size: 12px; }
    .dag-legend-item { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
    .dag-legend-swatch { width: 18px; height: 2px; border-radius: 999px; background: var(--gray); }
    .dag-legend-swatch.child_of { background: var(--green); }
    .dag-legend-swatch.depends_on { background: var(--amber); }
    .dag-legend-swatch.contributes_to { background: var(--purple); }
    .dag-legend-swatch.clarifies { background: var(--blue); }
    .dag-legend-swatch.duplicates { background: var(--red); }
    .dag-legend-swatch.supersedes { background: #0891b2; }
    .dag-legend-swatch.related_to { background: #64748b; }
    .dag-legend-swatch.derived_from { background: #15803d; }
    .detail-title { font-size: 18px; font-weight: 780; line-height: 1.3; margin-bottom: 8px; overflow-wrap: anywhere; }
    .detail-section { margin-top: 14px; }
    .detail-section h3 { margin: 0 0 6px; font-size: 13px; color: var(--muted); }
    .detail-section ul { margin: 0; padding-left: 18px; }
    .detail-section li { margin: 4px 0; font-size: 13px; line-height: 1.45; }
    .review-guide { margin-top: 10px; padding: 12px; border: 1px solid #f5b7b1; background: #fff8f7; border-radius: var(--radius); font-size: 13px; line-height: 1.48; }
    .review-guide strong { color: #991b1b; }
    .review-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
    .edge-table { display: grid; gap: 7px; }
    .edge-row { border: 1px solid var(--soft-line); border-left: 4px solid var(--gray); border-radius: var(--radius); padding: 9px 10px; background: #fff; cursor: pointer; }
    .edge-row:hover { border-color: var(--blue); }
    .detail-toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .empty { color: var(--muted); font-size: 13px; }
    .muted { color: var(--muted); }
    .hidden { display: none !important; }
    @media (max-width: 1200px) {
      body { --left-col: 1fr; --right-col: 1fr; }
      body.left-collapsed, body.right-collapsed { --left-col: 1fr; --right-col: 1fr; }
      .layout { grid-template-columns: 1fr; }
      .canvas { min-height: 520px; }
      .node { width: 210px; }
      body.left-collapsed .left-panel .side-panel-content,
      body.right-collapsed .right-panel .side-panel-content { display: block; }
      body.left-collapsed .left-panel,
      body.right-collapsed .right-panel { position: static; height: auto; max-height: none; min-height: 80px; }
      body.left-collapsed .left-panel .panel-title,
      body.right-collapsed .right-panel .panel-title { height: auto; flex-direction: row; padding: 12px 14px; }
      body.left-collapsed .left-panel .panel-title h2,
      body.right-collapsed .right-panel .panel-title h2 { writing-mode: horizontal-tb; margin-top: 0; }
    }
  </style>
</head>
<body>
  <header>
    <h1>__TITLE__</h1>
    <div class="meta" id="summary"></div>
  </header>
  <main class="layout">
    <section class="panel side-panel left-panel" id="leftPanel">
      <div class="panel-title">
        <h2>历史与队列</h2>
        <button type="button" id="toggleLeftPanel" data-collapse-panel="left" aria-expanded="true" title="收起左侧面板">‹</button>
      </div>
      <div class="side-panel-content">
      <h2>历史变化</h2>
      <div class="panel-body timeline">
        <div class="timeline-controls">
          <button id="prevSnapshot" type="button">上一步</button>
          <button id="playSnapshot" type="button" aria-pressed="false">播放</button>
          <button id="nextSnapshot" type="button">下一步</button>
          <select id="playSpeed" aria-label="播放速度">
            <option value="1800">慢</option>
            <option value="1100" selected>中</option>
            <option value="650">快</option>
          </select>
          <label class="toggle-line"><input id="loopPlayback" type="checkbox">循环</label>
        </div>
        <input id="snapshot" type="range" min="0" max="0" value="0">
        <div class="snapshot-label" id="snapshotLabel"></div>
        <div class="snapshot-diff" id="snapshotDiff"></div>
      </div>
      <h2>状态队列</h2>
      <div class="panel-body" id="statusQueues"></div>
      <h2>未完成事项</h2>
      <div class="panel-body" id="todoList"></div>
      <details class="legend-details" open>
        <summary>状态和边说明</summary>
        <div class="panel-body legend" id="legend"></div>
      </details>
      </div>
    </section>
    <section class="panel forest">
      <div class="toolbar">
        <div class="toolbar-group">
        <button type="button" data-view="tree">树视图</button>
        <button type="button" data-view="dag" title="DAG 视图会用图结构展示所有任务节点和不同类型的关系边">DAG 视图</button>
        <button type="button" data-view="all">全部</button>
        </div>
        <input id="search" type="search" placeholder="搜索 id、标题、状态、类型或标签">
        <div class="toolbar-group">
          <button type="button" id="expandAll">全部展开</button>
          <button type="button" id="collapseAll">全部折叠</button>
          <button type="button" id="clearFilter">清除筛选</button>
          <button type="button" id="resetDagLayout" title="重置 DAG 视图中手动拖动过的节点位置">重置布局</button>
        </div>
        <div class="toolbar-spacer"></div>
        <div class="zoom-controls" aria-label="树图缩放和平移">
          <button type="button" id="zoomOut" title="缩小">-</button>
          <button type="button" id="zoomReset" title="重置缩放和平移">100%</button>
          <button type="button" id="zoomIn" title="放大">+</button>
          <button type="button" id="zoomFit" title="适配当前画布">适配</button>
          <span class="zoom-label" id="zoomLabel">100%</span>
        </div>
      </div>
      <div class="active-filter" id="activeFilter"></div>
      <div class="canvas" id="canvas" title="拖拽空白区域可平移；按住 Ctrl/⌘/Alt 并滚轮可缩放">
        <div class="tree-viewport" id="treeViewport">
          <div class="tree" id="tree"></div>
        </div>
      </div>
      <div class="edge-panel" id="edgePanel"></div>
    </section>
    <section class="panel side-panel right-panel" id="rightPanel">
      <div class="panel-title">
        <h2 id="detailHeading">节点详情</h2>
        <button type="button" id="toggleRightPanel" data-collapse-panel="right" aria-expanded="true" title="收起右侧面板">›</button>
      </div>
      <div class="side-panel-content">
        <div class="panel-body" id="detail"></div>
      </div>
    </section>
  </main>
  <script>
    const CURRENT_GRAPH = __GRAPH_DATA__;
    const SNAPSHOTS = __SNAPSHOTS_DATA__;
    const CURRENT_TODOS = __TODOS_DATA__;
    const OPEN_STATUSES = new Set(["proposed", "ready", "in_progress", "blocked", "review_needed"]);
    const VIEW_LABELS = {tree: "树视图", dag: "DAG 视图", all: "全部"};
    const STATUS_LABELS = {
      proposed: "待确认",
      ready: "可执行",
      in_progress: "进行中",
      blocked: "阻塞",
      review_needed: "待复核",
      done: "已完成",
      deprecated: "已废止",
      archived: "已归档"
    };
    const STATUS_DESCRIPTIONS = {
      proposed: "已提出但尚未确认或排期",
      ready: "可开始执行，当前没有未满足依赖",
      in_progress: "正在推进或作为长期目标持续演进",
      blocked: "被依赖、信息或外部条件阻塞",
      review_needed: "产物或判断已到可检查阶段，但需要复核验收标准、证据、不足风险和实际结果后，才能标为已完成。",
      done: "已完成并通过验收",
      deprecated: "已废止但保留历史",
      archived: "已归档，通常不参与当前待办"
    };
    const KIND_LABELS = {
      global_task: "全局任务",
      task: "任务",
      subtask: "子任务",
      follow_up: "后续事项",
      risk: "风险",
      requirement: "要求",
      decision: "决策",
      alignment: "目标对齐",
      deviation: "偏差"
    };
    const EDGE_LABELS = {
      child_of: "子任务",
      depends_on: "依赖",
      contributes_to: "贡献",
      related_to: "相关",
      duplicates: "重复",
      supersedes: "替代",
      clarifies: "澄清",
      derived_from: "派生"
    };
    const EDGE_DESCRIPTIONS = {
      child_of: "子任务关系：起点任务是目标任务的子任务，构成默认树/森林",
      depends_on: "执行依赖边，起点任务必须等待目标任务完成",
      contributes_to: "多目标贡献边，不改变主父节点",
      related_to: "弱相关边，不影响可执行状态或进度判断",
      duplicates: "重复语义边，通常应合并或废止其中一个节点",
      supersedes: "替代边，起点任务替代目标任务",
      clarifies: "澄清边，起点任务澄清目标任务的要求或问题",
      derived_from: "来源边，起点任务从目标任务拆解或派生"
    };
    let graph = CURRENT_GRAPH;
    let selectedId = (CURRENT_GRAPH.status_queues?.review_needed?.[0] || CURRENT_GRAPH.roots?.[0] || null);
    let selectedEdgeId = null;
    let detailHistory = [];
    let activeFilter = "all";
    let query = "";
    let viewMode = "tree";
    let collapsed = new Set();
    let snapshotIndex = SNAPSHOTS.length ? SNAPSHOTS.length - 1 : 0;
    let playTimer = null;
    let graphScale = 1;
    let panX = 0;
    let panY = 0;
    let isPanning = false;
    let panStart = {x: 0, y: 0, panX: 0, panY: 0};
    let initialFitDone = false;
    let dagPositionOverrides = {};
    let currentDagLayout = null;
    let dagDrag = null;
    let suppressNextDagNodeClick = false;

    const HTML_ESCAPE = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    };
    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => HTML_ESCAPE[ch]);
    }
    function nodesObj(g = graph) { return g.nodes || {}; }
    function edgesObj(g = graph) { return g.edges || {}; }
    function nodeById(id) { return nodesObj()[id]; }
    function edgeById(id) { return edgesObj()[id]; }
    function statusLegend(status) { return STATUS_DESCRIPTIONS[status] || graph.status_legend?.[status] || CURRENT_GRAPH.status_legend?.[status] || status; }
    function edgeTypeLegend(type) { return EDGE_DESCRIPTIONS[type] || graph.edge_type_legend?.[type] || CURRENT_GRAPH.edge_type_legend?.[type] || type; }
    function statusLabel(status) { return STATUS_LABELS[status] || status; }
    function kindLabel(kind) { return KIND_LABELS[kind] || kind; }
    function edgeTypeLabel(type) { return EDGE_LABELS[type] || type; }
    function compactTitle(node) {
      const raw = String(node?.short_title || node?.display_title || node?.title || node?.id || "").trim();
      const rules = [
        [/build a personal ai workbench/i, "AI workbench"],
        [/set up the task-forest skill/i, "Task forest setup"],
        [/prepare a public-safe task-forest package/i, "Public package"],
        [/downstream planning tools/i, "Downstream tools"],
        [/evergreen/i, "Evergreen goal"],
        [/html.*dag|dag.*html/i, "HTML DAG view"]
      ];
      for (const [pattern, replacement] of rules) {
        if (pattern.test(raw)) return replacement;
      }
      const cleaned = raw
        .replace(/^TF-\\d+\\s*[·:：-]\\s*/i, "")
        .replace(/^(实现|安装|支持|构建|发布|重建|重构|修正|优化|添加|连接|prepare|build|set up|add|connect)\\s*/i, "")
        .replace(/\\s+/g, " ")
        .trim();
      if ([...cleaned].length <= 12) return cleaned || raw || "未命名任务";
      return [...cleaned].slice(0, 12).join("") + "…";
    }
    function reviewPrompt(node, passed) {
      if (passed) {
        return `请用 $task-forest 为当前 workspace 生成 proposal：我已经复核 ${node.id}《${node.title}》，验收标准、证据、实际产物、关系边和不足风险都已确认通过。请把该节点状态从 review_needed 更新为 done，并保留复核记录。先给 proposal，不要直接 apply。`;
      }
      return `请用 $task-forest 为当前 workspace 生成 proposal：我复核 ${node.id}《${node.title}》后发现还不能标为 done。请把缺口整理为新的 follow_up、requirement 或 risk，并说明它与原节点的关系。先给 proposal，不要直接 apply。缺口如下：`;
    }
    async function copyText(text) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (_) {
        const area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.left = "-9999px";
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(area);
        return ok;
      }
    }
    function getChildren(id, g = graph) {
      const node = (g.nodes || {})[id];
      if (Array.isArray(node?.children)) return node.children;
      return Object.values(g.edges || {}).filter(edge => edge.type === "child_of" && edge.to === id).map(edge => edge.from).sort();
    }
    function rootsFor(g = graph) {
      if (Array.isArray(g.roots) && g.roots.length) return g.roots;
      const childIds = new Set(Object.values(g.edges || {}).filter(edge => edge.type === "child_of").map(edge => edge.from));
      return Object.keys(g.nodes || {}).filter(id => !childIds.has(id)).sort();
    }
    function edgeIndexFor(id) {
      const cached = graph.edge_index?.[id];
      if (cached) return cached;
      const incoming = [], outgoing = [], blocking_edges = [], cross_edges = [], tree_child_edges = [];
      let tree_parent_edge = null;
      Object.entries(edgesObj()).forEach(([edgeId, edge]) => {
        if (edge.from === id) {
          outgoing.push(edgeId);
          if (edge.blocking) blocking_edges.push(edgeId);
          if (edge.type === "child_of") tree_parent_edge = edgeId;
          else cross_edges.push(edgeId);
        }
        if (edge.to === id) {
          incoming.push(edgeId);
          if (edge.type === "child_of") tree_child_edges.push(edgeId);
          else cross_edges.push(edgeId);
        }
      });
      return {incoming, outgoing, blocking_edges, cross_edges, tree_parent_edge, tree_child_edges};
    }
    function relatedEdgesFor(id) {
      const idx = edgeIndexFor(id);
      return [...new Set([...(idx.incoming || []), ...(idx.outgoing || [])])].filter(edgeId => edgeById(edgeId));
    }
    function statusQueue(status) {
      const cached = graph.status_queues?.by_status?.[status] || graph.status_queues?.[status];
      if (Array.isArray(cached)) return cached;
      return Object.values(nodesObj()).filter(node => node.status === status).map(node => node.id).sort();
    }
    function nodeMatches(id) {
      const node = nodeById(id);
      if (!node) return false;
      const statusMatch = activeFilter === "all" || (activeFilter === "open" ? OPEN_STATUSES.has(node.status) : node.status === activeFilter);
      const haystack = [node.id, node.title, node.kind, node.status, node.summary, ...(node.context_tags || [])].join(" ").toLowerCase();
      const queryMatch = !query || haystack.includes(query.toLowerCase());
      return statusMatch && queryMatch;
    }
    function subtreeMatches(id) {
      return nodeMatches(id) || getChildren(id).some(child => subtreeMatches(child));
    }
    function nodeProgress(node) { return Number(node?.derived_progress ?? node?.progress ?? 0); }
    function edgeTitle(edge) { return `${edge.id || ""} · ${edge.from} -[${edgeTypeLabel(edge.type)}]-> ${edge.to}`; }
    function filterLabel() {
      const status = activeFilter === "all" ? "全部状态" : activeFilter === "open" ? "未完成/开放" : `${statusLabel(activeFilter)} · ${statusLegend(activeFilter)}`;
      const q = query ? ` · 搜索: ${query}` : "";
      return `${VIEW_LABELS[viewMode] || viewMode} · ${status}${q}`;
    }
    function clampScale(value) {
      return Math.max(0.35, Math.min(1.8, Number(value) || 1));
    }
    function applyTreeTransform() {
      const viewport = document.getElementById("treeViewport");
      if (!viewport) return;
      viewport.style.transform = `translate(${panX}px, ${panY}px) scale(${graphScale})`;
      const label = document.getElementById("zoomLabel");
      if (label) label.textContent = `${Math.round(graphScale * 100)}%`;
    }
    function setZoom(nextScale, anchor = null) {
      const canvas = document.getElementById("canvas");
      const oldScale = graphScale;
      const newScale = clampScale(nextScale);
      if (!canvas || oldScale === newScale) {
        graphScale = newScale;
        applyTreeTransform();
        return;
      }
      const rect = canvas.getBoundingClientRect();
      const point = anchor || {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
      const localX = (point.x - rect.left - panX) / oldScale;
      const localY = (point.y - rect.top - panY) / oldScale;
      graphScale = newScale;
      panX = point.x - rect.left - localX * newScale;
      panY = point.y - rect.top - localY * newScale;
      applyTreeTransform();
    }
    function resetViewport() {
      graphScale = 1;
      panX = 0;
      panY = 0;
      applyTreeTransform();
    }
    function fitTreeToViewport() {
      const canvas = document.getElementById("canvas");
      const tree = document.getElementById("tree");
      if (!canvas || !tree) return;
      const treeWidth = Math.max(1, tree.scrollWidth);
      const treeHeight = Math.max(1, tree.scrollHeight);
      const availableWidth = Math.max(1, canvas.clientWidth - 48);
      const availableHeight = Math.max(1, canvas.clientHeight - 48);
      graphScale = clampScale(Math.min(1, availableWidth / treeWidth, availableHeight / treeHeight));
      panX = Math.max(18, (canvas.clientWidth - treeWidth * graphScale) / 2);
      panY = Math.max(18, (canvas.clientHeight - treeHeight * graphScale) / 2);
      applyTreeTransform();
    }
    function centerNodeInCanvas(id) {
      const canvas = document.getElementById("canvas");
      const node = document.querySelector(`#tree [data-node="${CSS.escape(id)}"]`);
      if (!canvas || !node || viewMode === "dag") return;
      const canvasRect = canvas.getBoundingClientRect();
      const nodeRect = node.getBoundingClientRect();
      panX += canvasRect.left + canvasRect.width / 2 - (nodeRect.left + nodeRect.width / 2);
      panY += canvasRect.top + canvasRect.height / 2 - (nodeRect.top + nodeRect.height / 2);
      applyTreeTransform();
    }
    function setPanelCollapsed(side, collapsedState) {
      const className = side === "left" ? "left-collapsed" : "right-collapsed";
      const button = document.getElementById(side === "left" ? "toggleLeftPanel" : "toggleRightPanel");
      const wasCollapsed = document.body.classList.contains(className);
      document.body.classList.toggle(className, collapsedState);
      if (button) {
        button.setAttribute("aria-expanded", String(!collapsedState));
        button.textContent = collapsedState ? (side === "left" ? "›" : "‹") : (side === "left" ? "‹" : "›");
        button.title = collapsedState ? (side === "left" ? "展开左侧面板" : "展开右侧面板") : (side === "left" ? "收起左侧面板" : "收起右侧面板");
      }
      if (wasCollapsed === collapsedState) return;
      requestAnimationFrame(() => {
        fitTreeToViewport();
      });
    }
    function syncStickyOffsets() {
      const header = document.querySelector("header");
      const height = header ? header.getBoundingClientRect().height : 80;
      document.documentElement.style.setProperty("--sticky-rail-top", `${Math.ceil(height + 16)}px`);
    }

    function renderSummary() {
      const s = graph.summary || {};
      const chips = [
        {label: "节点", value: s.node_count ?? Object.keys(nodesObj()).length},
        {label: "边", value: s.edge_count ?? Object.keys(edgesObj()).length, view: "dag"},
        {label: "未完成", value: s.open_count ?? Object.values(nodesObj()).filter(n => OPEN_STATUSES.has(n.status)).length, filter: "open"},
        {label: "阻塞", value: s.blocked_count ?? statusQueue("blocked").length, filter: "blocked"},
        {label: "待复核", value: s.review_needed_count ?? statusQueue("review_needed").length, filter: "review_needed"},
        {label: "生成于", value: graph.generated_at || ""},
      ];
      document.getElementById("summary").innerHTML = chips.map(chip => {
        const active = chip.filter && activeFilter === chip.filter;
        const clickable = chip.filter || chip.view;
        const attrs = chip.filter ? `data-filter="${esc(chip.filter)}"` : chip.view ? `data-view="${esc(chip.view)}"` : "";
        const title = chip.filter === "review_needed" ? "点击查看所有待复核节点；再次点击取消筛选" : chip.filter ? `点击筛选 ${chip.label}；再次点击取消筛选` : chip.view ? "点击打开 DAG 视图" : "";
        return clickable ? `<button type="button" class="summary-chip ${active ? "is-filtered" : ""}" ${attrs} title="${esc(title)}"><span>${esc(chip.label)}</span><strong>${esc(chip.value)}</strong></button>` : `<span class="summary-chip"><span>${esc(chip.label)}</span><strong>${esc(chip.value)}</strong></span>`;
      }).join("");
    }

    function nodeHtml(id, level = 0) {
      const node = nodeById(id);
      if (!node || !subtreeMatches(id)) return "";
      const children = getChildren(id).filter(child => subtreeMatches(child));
      const isCollapsed = collapsed.has(id);
      const progress = nodeProgress(node);
      const direct = nodeMatches(id);
      const childHtml = children.length && !isCollapsed ? `<ul>${children.map(child => `<li>${nodeHtml(child, level + 1)}</li>`).join("")}</ul>` : "";
      const toggle = children.length ? `<button type="button" class="node-toggle" data-toggle="${esc(id)}" aria-expanded="${String(!isCollapsed)}">${isCollapsed ? "+" : "-"}</button>` : `<button type="button" class="node-toggle empty" tabindex="-1">-</button>`;
      return `<div class="node ${esc(node.status)} ${selectedId === id ? "active" : ""} ${direct ? "" : "context-only"}" data-node="${esc(id)}" style="--level:${level}">
        <div class="node-head">
          ${toggle}
          <div class="node-title" title="${esc(node.id)} · ${esc(node.title)}">${esc(compactTitle(node))}</div>
        </div>
        <div class="bar"><span style="width:${Math.max(0, Math.min(100, progress))}%"></span></div>
      </div>${childHtml}`;
    }

    function visibleNodeIdsForGraph() {
      return Object.keys(nodesObj()).filter(id => nodeMatches(id) || activeFilter === "all" || relatedEdgesFor(id).some(edgeId => {
        const edge = edgeById(edgeId);
        const other = edge?.from === id ? edge.to : edge?.from;
        return other && nodeMatches(other);
      })).sort();
    }

    function visibleEdgeIdsForGraph(nodeIds) {
      const visible = new Set(nodeIds);
      return Object.keys(edgesObj()).filter(edgeId => {
        const edge = edgeById(edgeId);
        return edge && visible.has(edge.from) && visible.has(edge.to);
      }).sort();
    }

    function dagDepths(nodeIds) {
      const visible = new Set(nodeIds);
      const parents = new Map(nodeIds.map(id => [id, []]));
      Object.values(edgesObj()).forEach(edge => {
        if (edge.type === "child_of" && visible.has(edge.from) && visible.has(edge.to)) {
          parents.get(edge.from).push(edge.to);
        }
      });
      const memo = new Map();
      const visiting = new Set();
      function depth(id) {
        if (memo.has(id)) return memo.get(id);
        if (visiting.has(id)) return 0;
        visiting.add(id);
        const value = Math.max(0, ...parents.get(id).map(parent => depth(parent) + 1));
        visiting.delete(id);
        memo.set(id, value);
        return value;
      }
      nodeIds.forEach(depth);
      return memo;
    }

    function buildDagLayout() {
      const nodeIds = visibleNodeIdsForGraph();
      const edgeIds = visibleEdgeIdsForGraph(nodeIds);
      const depthById = dagDepths(nodeIds);
      const columns = new Map();
      nodeIds.forEach(id => {
        const depth = depthById.get(id) || 0;
        if (!columns.has(depth)) columns.set(depth, []);
        columns.get(depth).push(id);
      });
      const nodeW = 154, nodeH = 72, xGap = 116, yGap = 34, topPad = 72, leftPad = 36;
      const sortedDepths = [...columns.keys()].sort((a, b) => a - b);
      const maxRows = Math.max(1, ...[...columns.values()].map(ids => ids.length));
      const positions = {};
      sortedDepths.forEach((depth, colIndex) => {
        const ids = columns.get(depth).sort((a, b) => String(a).localeCompare(String(b)));
        const offset = (maxRows - ids.length) * (nodeH + yGap) / 2;
        ids.forEach((id, rowIndex) => {
          positions[id] = {
            x: leftPad + colIndex * (nodeW + xGap),
            y: topPad + offset + rowIndex * (nodeH + yGap),
            w: nodeW,
            h: nodeH
          };
        });
      });
      const width = leftPad * 2 + Math.max(1, sortedDepths.length) * nodeW + Math.max(0, sortedDepths.length - 1) * xGap;
      const height = topPad + Math.max(1, maxRows) * nodeH + Math.max(0, maxRows - 1) * yGap + 42;
      Object.entries(dagPositionOverrides).forEach(([id, override]) => {
        if (!positions[id]) return;
        const x = Number(override?.x);
        const y = Number(override?.y);
        if (Number.isFinite(x)) positions[id].x = Math.max(0, x);
        if (Number.isFinite(y)) positions[id].y = Math.max(42, y);
      });
      const maxRight = Math.max(width, ...Object.values(positions).map(pos => pos.x + pos.w + 80));
      const maxBottom = Math.max(height, ...Object.values(positions).map(pos => pos.y + pos.h + 80));
      return {nodeIds, edgeIds, positions, width: maxRight, height: maxBottom, baseWidth: width, baseHeight: height, nodeW, nodeH};
    }

    function cubicPoint(p0, p1, p2, p3, t) {
      const mt = 1 - t;
      return {
        x: mt * mt * mt * p0.x + 3 * mt * mt * t * p1.x + 3 * mt * t * t * p2.x + t * t * t * p3.x,
        y: mt * mt * mt * p0.y + 3 * mt * mt * t * p1.y + 3 * mt * t * t * p2.y + t * t * t * p3.y
      };
    }

    function edgeGeometry(edge, positions, index = 0) {
      const from = positions[edge.from];
      const to = positions[edge.to];
      if (!from || !to) return {d: "", label: {x: 0, y: 0}};
      const start = {x: from.x + from.w, y: from.y + from.h / 2};
      const end = {x: to.x, y: to.y + to.h / 2};
      const sameOrBack = end.x <= start.x;
      const lane = (index % 5 - 2) * 9;
      let control1, control2;
      if (sameOrBack) {
        const midX = Math.max(start.x, end.x) + 52 + Math.abs(index % 4) * 14;
        control1 = {x: midX, y: start.y + lane};
        control2 = {x: midX, y: end.y - lane};
      } else {
        const delta = Math.max(48, (end.x - start.x) * 0.5);
        control1 = {x: start.x + delta, y: start.y + lane};
        control2 = {x: end.x - delta, y: end.y - lane};
      }
      return {
        d: `M ${start.x} ${start.y} C ${control1.x} ${control1.y}, ${control2.x} ${control2.y}, ${end.x} ${end.y}`,
        label: cubicPoint(start, control1, control2, end, 0.5)
      };
    }

    function edgePath(edge, positions, index = 0) {
      return edgeGeometry(edge, positions, index).d;
    }

    function edgeLabelPosition(edge, positions, index = 0) {
      return edgeGeometry(edge, positions, index).label;
    }

    function renderDagGraph() {
      const layout = buildDagLayout();
      currentDagLayout = layout;
      if (!layout.nodeIds.length) {
        currentDagLayout = null;
        return `<div class="empty">没有匹配当前筛选的节点。</div>`;
      }
      const legendTypes = [...new Set(layout.edgeIds.map(edgeId => edgeById(edgeId)?.type).filter(Boolean))];
      const markers = legendTypes.map(type => `<marker id="arrow-${esc(type)}" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" class="dag-arrow ${esc(type)}"></path></marker>`).join("");
      const edgePaths = layout.edgeIds.map((edgeId, index) => {
        const edge = edgeById(edgeId);
        const d = edgePath(edge, layout.positions, index);
        return `<g class="dag-edge-group" data-edge="${esc(edgeId)}"><path class="dag-edge-hit" data-edge="${esc(edgeId)}" d="${esc(d)}"></path><path class="dag-edge ${esc(edge.type)} ${selectedEdgeId === edgeId ? "active" : ""}" data-edge="${esc(edgeId)}" d="${esc(d)}" marker-end="url(#arrow-${esc(edge.type)})"></path></g>`;
      }).join("");
      const labels = layout.edgeIds.map((edgeId, index) => {
        const edge = edgeById(edgeId);
        const pos = edgeLabelPosition(edge, layout.positions, index);
        return `<div class="dag-edge-label ${selectedEdgeId === edgeId ? "active" : ""}" data-edge="${esc(edgeId)}" style="left:${pos.x}px;top:${pos.y}px" title="${esc(edgeTitle(edge))}">${esc(edgeTypeLabel(edge.type))}</div>`;
      }).join("");
      const nodes = layout.nodeIds.map(id => {
        const node = nodeById(id);
        const pos = layout.positions[id];
        return `<div class="dag-node ${esc(node.status)} ${selectedId === id && !selectedEdgeId ? "active" : ""}" data-node="${esc(id)}" style="left:${pos.x}px;top:${pos.y}px" title="${esc(id)} · ${esc(node.title)}"><div class="dag-node-title">${esc(compactTitle(node))}</div><div class="dag-node-meta">${esc(statusLabel(node.status))} · ${esc(nodeProgress(node))}%</div><div class="bar"><span style="width:${Math.max(0, Math.min(100, nodeProgress(node)))}%"></span></div></div>`;
      }).join("");
      const legend = legendTypes.length ? `<div class="dag-legend">${legendTypes.map(type => `<span class="dag-legend-item"><span class="dag-legend-swatch ${esc(type)}"></span>${esc(edgeTypeLabel(type))}</span>`).join("")}</div>` : "";
      return `<div class="dag-graph" style="width:${layout.width}px;height:${layout.height}px">${legend}<svg class="dag-svg" width="${layout.width}" height="${layout.height}" viewBox="0 0 ${layout.width} ${layout.height}" aria-label="DAG 任务关系图"><defs>${markers}</defs>${edgePaths}</svg>${labels}${nodes}</div>`;
    }

    function updateDagGeometry() {
      if (!currentDagLayout || viewMode !== "dag") return;
      const graphEl = document.querySelector("#tree .dag-graph");
      const svg = document.querySelector("#tree svg.dag-svg");
      const positions = currentDagLayout.positions || {};
      const maxRight = Math.max(currentDagLayout.baseWidth || currentDagLayout.width || 1, ...Object.values(positions).map(pos => pos.x + pos.w + 80));
      const maxBottom = Math.max(currentDagLayout.baseHeight || currentDagLayout.height || 1, ...Object.values(positions).map(pos => pos.y + pos.h + 80));
      currentDagLayout.width = maxRight;
      currentDagLayout.height = maxBottom;
      if (graphEl) {
        graphEl.style.width = `${maxRight}px`;
        graphEl.style.height = `${maxBottom}px`;
      }
      if (svg) {
        svg.setAttribute("width", String(maxRight));
        svg.setAttribute("height", String(maxBottom));
        svg.setAttribute("viewBox", `0 0 ${maxRight} ${maxBottom}`);
      }
      currentDagLayout.edgeIds.forEach((edgeId, index) => {
        const edge = edgeById(edgeId);
        if (!edge) return;
        const d = edgePath(edge, positions, index);
        document.querySelectorAll(`#tree [data-edge="${CSS.escape(edgeId)}"].dag-edge, #tree [data-edge="${CSS.escape(edgeId)}"].dag-edge-hit`).forEach(path => {
          path.setAttribute("d", d);
        });
        const label = document.querySelector(`#tree .dag-edge-label[data-edge="${CSS.escape(edgeId)}"]`);
        if (label) {
          const pos = edgeLabelPosition(edge, positions, index);
          label.style.left = `${pos.x}px`;
          label.style.top = `${pos.y}px`;
        }
      });
    }

    function startDagNodeDrag(event) {
      if (viewMode !== "dag" || event.button !== 0) return;
      const nodeEl = event.target.closest(".dag-node[data-node]");
      if (!nodeEl || !currentDagLayout) return;
      const id = nodeEl.dataset.node;
      const pos = currentDagLayout.positions?.[id];
      if (!pos) return;
      dagDrag = {
        id,
        el: nodeEl,
        startClientX: event.clientX,
        startClientY: event.clientY,
        startX: pos.x,
        startY: pos.y,
        moved: false
      };
      nodeEl.classList.add("dragging");
      try { nodeEl.setPointerCapture(event.pointerId); } catch (_) {}
      event.preventDefault();
      event.stopPropagation();
    }

    function moveDagNode(event) {
      if (!dagDrag || !currentDagLayout) return;
      const pos = currentDagLayout.positions?.[dagDrag.id];
      if (!pos) return;
      const dx = (event.clientX - dagDrag.startClientX) / Math.max(0.1, graphScale);
      const dy = (event.clientY - dagDrag.startClientY) / Math.max(0.1, graphScale);
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) dagDrag.moved = true;
      const nextX = Math.max(0, dagDrag.startX + dx);
      const nextY = Math.max(42, dagDrag.startY + dy);
      pos.x = nextX;
      pos.y = nextY;
      dagPositionOverrides[dagDrag.id] = {x: nextX, y: nextY};
      dagDrag.el.style.left = `${nextX}px`;
      dagDrag.el.style.top = `${nextY}px`;
      updateDagGeometry();
      event.preventDefault();
    }

    function endDagNodeDrag(event) {
      if (!dagDrag) return;
      const nodeEl = dagDrag.el;
      const moved = dagDrag.moved;
      nodeEl.classList.remove("dragging");
      try { nodeEl.releasePointerCapture(event.pointerId); } catch (_) {}
      dagDrag = null;
      if (moved) suppressNextDagNodeClick = true;
    }

    function renderTree() {
      const tree = document.getElementById("tree");
      if (viewMode === "dag") {
        tree.innerHTML = renderDagGraph();
        return;
      }
      const roots = rootsFor().filter(root => subtreeMatches(root));
      tree.innerHTML = roots.length ? `<ul class="tree-list">${roots.map(root => `<li>${nodeHtml(root, 0)}</li>`).join("")}</ul>` : `<div class="empty">没有匹配当前筛选的节点。</div>`;
    }

    function edgeCard(edgeId) {
      const edge = edgeById(edgeId);
      if (!edge) return "";
      const from = nodeById(edge.from);
      const to = nodeById(edge.to);
      return `<div class="edge-card ${esc(edge.type)} ${selectedEdgeId === edgeId ? "active" : ""}" data-edge="${esc(edgeId)}">
        <div class="edge-card-title">${esc(edge.id)} · ${esc(edgeTypeLabel(edge.type))}${edge.blocking ? " · 阻塞" : ""}</div>
        <div class="edge-card-meta">${esc(edge.from)} ${from ? "· " + esc(compactTitle(from)) : ""}<br>→ ${esc(edge.to)} ${to ? "· " + esc(compactTitle(to)) : ""}<br>${esc(edge.reason || edgeTypeLegend(edge.type))}</div>
      </div>`;
    }

    function renderEdgePanel() {
      const panel = document.getElementById("edgePanel");
      const allIds = Object.keys(edgesObj()).sort();
      const crossIds = allIds.filter(edgeId => edgeById(edgeId)?.type !== "child_of");
      const ids = viewMode === "tree" ? crossIds : allIds;
      const heading = viewMode === "tree" ? "跨层级关系" : "全部关系边";
      panel.innerHTML = `<h3>${heading}</h3>${ids.length ? `<div class="edge-list">${ids.map(edgeCard).join("")}</div>` : `<div class="empty">当前没有需要单独展示的跨边。</div>`}`;
    }

    function renderQueues() {
      const blocks = [
        {label: "待复核", status: "review_needed"},
        {label: "阻塞", status: "blocked"},
        {label: "可执行", status: "ready"},
        {label: "持续目标", custom: graph.status_queues?.evergreen_open_goals || []},
      ];
      document.getElementById("statusQueues").innerHTML = blocks.map(block => {
        const ids = block.custom || statusQueue(block.status);
        const body = ids.length ? ids.map(id => {
          const node = nodeById(id);
          if (!node) return "";
          const reviewHint = node.status === "review_needed" ? "<br>点击查看复核清单" : "";
          return `<div class="queue-item" data-node="${esc(id)}"><div class="queue-title-line">${esc(id)} · ${esc(node.title)}</div><div class="queue-meta">${esc(statusLabel(node.status))} · ${nodeProgress(node)}%<br>${esc(statusLegend(node.status))}${reviewHint}</div></div>`;
        }).join("") : `<div class="empty">无</div>`;
        return `<div class="queue-block"><div class="queue-title"><span>${esc(block.label)}</span><span>${ids.length}</span></div>${body}</div>`;
      }).join("");
    }

    function buildTodoItems() {
      const currentMap = new Map(CURRENT_TODOS.map(item => [item.id, item]));
      return Object.values(nodesObj())
        .filter(node => OPEN_STATUSES.has(node.status))
        .map(node => currentMap.get(node.id) || {id: node.id, title: node.title, progress: nodeProgress(node), status: node.status, kind: node.kind, next_action: "查看节点详情", priority: node.priority})
        .sort((a, b) => (b.priority || 0) - (a.priority || 0) || String(a.id).localeCompare(String(b.id)));
    }

    function renderTodos() {
      const todos = buildTodoItems();
      const actionable = todos.filter(item => !(item.kind === "global_task" && item.status === "in_progress" && item.remaining_minutes_min == null));
      const evergreen = todos.filter(item => item.kind === "global_task" && item.status === "in_progress" && item.remaining_minutes_min == null);
      const renderItems = items => items.length ? items.map(item => `<div class="todo" data-node="${esc(item.id)}"><div class="todo-title">${esc(item.id)} · ${esc(item.title)}</div><div class="todo-meta">${esc(statusLabel(item.status))} · ${esc(item.progress)}%<br>${esc(item.next_action || "查看节点详情")}</div></div>`).join("") : `<div class="empty">无</div>`;
      document.getElementById("todoList").innerHTML = `<div class="queue-block"><div class="queue-title"><span>可行动项</span><span>${actionable.length}</span></div>${renderItems(actionable)}</div><div class="queue-block"><div class="queue-title"><span>持续开放目标</span><span>${evergreen.length}</span></div>${renderItems(evergreen)}</div>`;
    }

    function listItems(items) {
      if (!items || !items.length) return `<div class="empty">无</div>`;
      return `<ul>${items.map(item => `<li>${esc(typeof item === "object" ? (item.text || item.title || JSON.stringify(item)) : item)}</li>`).join("")}</ul>`;
    }

    function renderNodeDetail(node) {
      const alignment = node.alignment || {};
      const related = relatedEdgesFor(node.id);
      return `
        <div class="detail-title">${esc(node.id)} · ${esc(node.title)}</div>
        <div>${esc(node.summary || "无摘要")}</div>
        <div class="detail-section"><h3>状态</h3>
          <span class="badge">${esc(kindLabel(node.kind))}</span><span class="badge">${esc(statusLabel(node.status))}</span><span class="badge">进度 ${esc(nodeProgress(node))}%</span><span class="badge">优先级 P${esc(node.priority)}</span>
          <div class="muted">${esc(statusLegend(node.status))}</div>
          ${node.status === "review_needed" ? `<div class="review-guide"><strong>待复核要看什么</strong><br>为什么待复核：${esc(statusLegend(node.status))}<br>复核对象：验收标准、证据、实际产物、关系边、以及“不足或风险”。<br>通过复核：让 $task-forest 生成 proposal 把 ${esc(node.id)} 改为 done。<br>不通过复核：指出缺口，把缺口写成新的后续事项、要求或风险。<div class="review-actions"><button type="button" data-review-copy="pass" data-node="${esc(node.id)}">复制通过复核指令</button><button type="button" data-review-copy="fail" data-node="${esc(node.id)}">复制记录缺口指令</button></div></div>` : ""}
        </div>
        <div class="detail-section"><h3>全局目的</h3><div>${esc(node.purpose || alignment.user_goal || "无")}</div></div>
        <div class="detail-section"><h3>为什么这个任务符合目的</h3><div>${esc(alignment.why_this_task || "无")}</div></div>
        <div class="detail-section"><h3>不足或风险</h3><div>${esc(alignment.why_not_enough || "无")}</div></div>
        <div class="detail-section"><h3>期望结果</h3>${listItems(node.desired_outcomes)}</div>
        <div class="detail-section"><h3>成功指标</h3>${listItems(node.success_metrics)}</div>
        <div class="detail-section"><h3>具体要求</h3>${listItems(node.requirements)}</div>
        <div class="detail-section"><h3>验收标准</h3>${listItems(node.acceptance_criteria)}</div>
        <div class="detail-section"><h3>非目标</h3>${listItems(node.non_goals)}</div>
        <div class="detail-section"><h3>关键假设</h3>${listItems(node.assumptions)}</div>
        <div class="detail-section"><h3>验证计划</h3>${listItems(alignment.validation_plan)}</div>
        <div class="detail-section"><h3>执行提示</h3>${listItems(node.execution_hints)}</div>
        <div class="detail-section"><h3>证据</h3>${listItems(node.evidence)}</div>
        <div class="detail-section"><h3>关系边</h3>${related.length ? `<div class="edge-table">${related.map(edgeId => edgeRow(edgeId)).join("")}</div>` : `<div class="empty">无</div>`}</div>
        <div class="detail-section"><h3>偏差记录</h3>${listItems(node.deviations)}</div>
      `;
    }

    function edgeRow(edgeId) {
      const edge = edgeById(edgeId);
      if (!edge) return "";
      return `<div class="edge-row ${esc(edge.type)}" data-edge="${esc(edgeId)}"><strong>${esc(edge.id)} · ${esc(edgeTypeLabel(edge.type))}</strong><br><span class="muted">${esc(edge.from)} → ${esc(edge.to)}${edge.blocking ? " · 阻塞" : ""}</span><br>${esc(edge.reason || edgeTypeLegend(edge.type))}</div>`;
    }

    function renderEdgeDetail(edge) {
      const from = nodeById(edge.from);
      const to = nodeById(edge.to);
      return `
        <div class="detail-toolbar"><button type="button" data-detail-back>返回上一项</button>${selectedId ? `<button type="button" data-node="${esc(selectedId)}">返回当前节点</button>` : ""}</div>
        <div class="detail-title">${esc(edge.id)} · ${esc(edgeTypeLabel(edge.type))}</div>
        <div class="muted">${esc(edgeTypeLegend(edge.type))}</div>
        <div class="detail-section"><h3>方向</h3><div><button type="button" data-node="${esc(edge.from)}">${esc(edge.from)}</button> → <button type="button" data-node="${esc(edge.to)}">${esc(edge.to)}</button></div></div>
        <div class="detail-section"><h3>起点任务</h3><div>${esc(from ? from.title : edge.from)}</div></div>
        <div class="detail-section"><h3>目标任务</h3><div>${esc(to ? to.title : edge.to)}</div></div>
        <div class="detail-section"><h3>边属性</h3><div>阻塞关系：${edge.blocking ? "是" : "否"}</div><div>置信度：${esc(edge.confidence ?? "未记录")}</div></div>
        <div class="detail-section"><h3>原因</h3><div>${esc(edge.reason || "无")}</div></div>
        <div class="detail-section"><h3>创建信息</h3><div class="muted">${esc(edge.created_at || "无")}<br>${esc(edge.created_from_session || "")}</div></div>
      `;
    }

    function renderDetail() {
      const detail = document.getElementById("detail");
      const edge = selectedEdgeId ? edgeById(selectedEdgeId) : null;
      const node = selectedId ? nodeById(selectedId) : null;
      if (edge) {
        document.getElementById("detailHeading").textContent = "边详情";
        detail.innerHTML = renderEdgeDetail(edge);
        return;
      }
      document.getElementById("detailHeading").textContent = "节点详情";
      detail.innerHTML = node ? renderNodeDetail(node) : `<div class="empty">选择一个节点查看完整说明、要求、进度、偏差和关系。</div>`;
    }

    function snapshotDiff(index) {
      if (!SNAPSHOTS.length) return ["暂无历史快照；当前展示最新任务图。"];
      const curr = SNAPSHOTS[index]?.graph || CURRENT_GRAPH;
      const prev = index > 0 ? (SNAPSHOTS[index - 1]?.graph || {nodes:{}, edges:{}}) : {nodes:{}, edges:{}};
      const currNodes = curr.nodes || {}, prevNodes = prev.nodes || {};
      const currEdges = curr.edges || {}, prevEdges = prev.edges || {};
      const addedNodes = Object.keys(currNodes).filter(id => !prevNodes[id]);
      const removedNodes = Object.keys(prevNodes).filter(id => !currNodes[id]);
      const addedEdges = Object.keys(currEdges).filter(id => !prevEdges[id]);
      const statusChanges = Object.keys(currNodes).filter(id => prevNodes[id] && prevNodes[id].status !== currNodes[id].status);
      const progressChanges = Object.keys(currNodes).filter(id => prevNodes[id] && Number(prevNodes[id].derived_progress ?? prevNodes[id].progress ?? 0) !== Number(currNodes[id].derived_progress ?? currNodes[id].progress ?? 0));
      const lines = [];
      if (addedNodes.length) lines.push(`新增节点 ${addedNodes.length}: ${addedNodes.join("、")}`);
      if (removedNodes.length) lines.push(`移除节点 ${removedNodes.length}: ${removedNodes.join("、")}`);
      if (addedEdges.length) lines.push(`新增边 ${addedEdges.length}: ${addedEdges.join("、")}`);
      if (statusChanges.length) lines.push(`状态变化 ${statusChanges.length}: ${statusChanges.map(id => `${id} ${prevNodes[id].status}->${currNodes[id].status}`).join("、")}`);
      if (progressChanges.length) lines.push(`进度变化 ${progressChanges.length}: ${progressChanges.map(id => `${id} ${Number(prevNodes[id].derived_progress ?? prevNodes[id].progress ?? 0)}%->${Number(currNodes[id].derived_progress ?? currNodes[id].progress ?? 0)}%`).join("、")}`);
      return lines.length ? lines : ["该快照相对前一快照没有结构性变化。"];
    }

    function renderTimeline() {
      const slider = document.getElementById("snapshot");
      const label = document.getElementById("snapshotLabel");
      const diff = document.getElementById("snapshotDiff");
      const has = SNAPSHOTS.length > 0;
      slider.max = Math.max(0, SNAPSHOTS.length - 1);
      slider.disabled = !has;
      document.getElementById("prevSnapshot").disabled = !has || snapshotIndex <= 0;
      document.getElementById("nextSnapshot").disabled = !has || snapshotIndex >= SNAPSHOTS.length - 1;
      if (!has) {
        label.textContent = "暂无历史快照；当前展示最新任务图。";
        diff.textContent = "";
        return;
      }
      slider.value = String(snapshotIndex);
      const snap = SNAPSHOTS[snapshotIndex];
      label.textContent = `${snap.snapshot_id || ""} · ${snap.created_at || ""} · ${snap.graph?.reason || ""}`;
      diff.innerHTML = snapshotDiff(snapshotIndex).map(line => `<div>${esc(line)}</div>`).join("");
    }

    function renderLegend() {
      const statuses = ["proposed", "ready", "in_progress", "blocked", "review_needed", "done", "deprecated", "archived"];
      const edgeTypes = ["child_of", "depends_on", "contributes_to", "related_to", "duplicates", "supersedes", "clarifies", "derived_from"];
      document.getElementById("legend").innerHTML = `<div><strong>状态</strong></div>${statuses.map(s => `<div class="legend-row"><span>${esc(statusLabel(s))}</span><span>${esc(statusLegend(s))}</span></div>`).join("")}<div style="margin-top:10px"><strong>边</strong></div>${edgeTypes.map(t => `<div class="legend-row"><span>${esc(edgeTypeLabel(t))}</span><span>${esc(edgeTypeLegend(t))}</span></div>`).join("")}`;
    }

    function setView(mode) {
      viewMode = mode;
      render();
      requestAnimationFrame(() => {
        fitTreeToViewport();
      });
    }
    function firstNodeForFilter(filter) {
      const ids = filter === "open"
        ? Object.values(nodesObj()).filter(node => OPEN_STATUSES.has(node.status)).map(node => node.id)
        : filter === "all"
          ? rootsFor()
          : statusQueue(filter);
      return ids.find(id => nodeById(id)) || null;
    }
    function setFilter(filter) {
      activeFilter = activeFilter === filter ? "all" : filter;
      selectedEdgeId = null;
      const first = firstNodeForFilter(activeFilter);
      if (first) selectedId = first;
      render();
      if (first) requestAnimationFrame(() => centerNodeInCanvas(first));
    }
    function selectNode(id, scroll = true) {
      if (!nodeById(id)) return;
      selectedId = id;
      selectedEdgeId = null;
      setPanelCollapsed("right", false);
      render();
      if (scroll) requestAnimationFrame(() => centerNodeInCanvas(id));
    }
    function selectEdge(id) {
      if (!edgeById(id)) return;
      if (selectedEdgeId !== id) {
        detailHistory.push({selectedId, selectedEdgeId});
        if (detailHistory.length > 30) detailHistory.shift();
      }
      selectedEdgeId = id;
      const edge = edgeById(id);
      selectedId = edge.from;
      viewMode = viewMode === "tree" ? "all" : viewMode;
      setPanelCollapsed("right", false);
      render();
    }
    function goBackDetail() {
      const previous = detailHistory.pop();
      if (!previous) {
        selectedEdgeId = null;
        render();
        return;
      }
      selectedId = previous.selectedId;
      selectedEdgeId = previous.selectedEdgeId;
      render();
    }
    function useSnapshot(index) {
      if (!SNAPSHOTS.length) return;
      snapshotIndex = Math.max(0, Math.min(SNAPSHOTS.length - 1, index));
      graph = SNAPSHOTS[snapshotIndex]?.graph || CURRENT_GRAPH;
      dagPositionOverrides = {};
      currentDagLayout = null;
      if (selectedId && !nodeById(selectedId)) selectedId = rootsFor()[0] || null;
      if (selectedEdgeId && !edgeById(selectedEdgeId)) selectedEdgeId = null;
      render();
    }
    function stopPlayback() {
      if (playTimer) clearInterval(playTimer);
      playTimer = null;
      document.getElementById("playSnapshot").textContent = "播放";
      document.getElementById("playSnapshot").setAttribute("aria-pressed", "false");
    }
    function startPlayback() {
      if (!SNAPSHOTS.length) return;
      stopPlayback();
      document.getElementById("playSnapshot").textContent = "暂停";
      document.getElementById("playSnapshot").setAttribute("aria-pressed", "true");
      const delay = Number(document.getElementById("playSpeed").value || 1100);
      playTimer = setInterval(() => {
        const next = snapshotIndex + 1;
        if (next < SNAPSHOTS.length) useSnapshot(next);
        else if (document.getElementById("loopPlayback").checked) useSnapshot(0);
        else stopPlayback();
      }, delay);
    }

    function render() {
      renderSummary();
      renderTree();
      renderEdgePanel();
      renderQueues();
      renderTodos();
      renderDetail();
      renderTimeline();
      renderLegend();
      document.getElementById("activeFilter").textContent = filterLabel();
      document.querySelectorAll("[data-view]").forEach(btn => btn.classList.toggle("active", btn.dataset.view === viewMode));
      document.querySelectorAll("[data-filter]").forEach(btn => btn.classList.toggle("active", btn.dataset.filter === activeFilter));
      const search = document.getElementById("search");
      if (search.value !== query) search.value = query;
      requestAnimationFrame(() => {
        applyTreeTransform();
        if (!initialFitDone && viewMode !== "dag") {
          initialFitDone = true;
          fitTreeToViewport();
        }
      });
    }

    document.addEventListener("click", event => {
      const toggle = event.target.closest("[data-toggle]");
      if (toggle) {
        const id = toggle.dataset.toggle;
        collapsed.has(id) ? collapsed.delete(id) : collapsed.add(id);
        render();
        event.stopPropagation();
        return;
      }
      const view = event.target.closest("[data-view]");
      if (view) { setView(view.dataset.view); return; }
      const filter = event.target.closest("[data-filter]");
      if (filter) { setFilter(filter.dataset.filter); return; }
      const back = event.target.closest("[data-detail-back]");
      if (back) { goBackDetail(); return; }
      const reviewCopy = event.target.closest("[data-review-copy]");
      if (reviewCopy) {
        const node = nodeById(reviewCopy.dataset.node);
        if (!node) return;
        copyText(reviewPrompt(node, reviewCopy.dataset.reviewCopy === "pass")).then(ok => {
          reviewCopy.textContent = ok ? "已复制指令" : "复制失败，请手动复制";
          setTimeout(() => {
            reviewCopy.textContent = reviewCopy.dataset.reviewCopy === "pass" ? "复制通过复核指令" : "复制记录缺口指令";
          }, 1400);
        });
        return;
      }
      const edge = event.target.closest("[data-edge]");
      if (edge) { selectEdge(edge.dataset.edge); return; }
      const node = event.target.closest("[data-node]");
      if (node) {
        if (suppressNextDagNodeClick && node.classList.contains("dag-node")) {
          suppressNextDagNodeClick = false;
          return;
        }
        selectNode(node.dataset.node, false);
        return;
      }
    });
    document.getElementById("search").addEventListener("input", event => { query = event.target.value.trim(); render(); });
    document.getElementById("clearFilter").addEventListener("click", () => { activeFilter = "all"; query = ""; selectedEdgeId = null; render(); });
    document.getElementById("resetDagLayout").addEventListener("click", () => {
      dagPositionOverrides = {};
      currentDagLayout = null;
      render();
      requestAnimationFrame(fitTreeToViewport);
    });
    document.getElementById("expandAll").addEventListener("click", () => { collapsed.clear(); render(); });
    document.getElementById("collapseAll").addEventListener("click", () => { Object.keys(nodesObj()).forEach(id => { if (getChildren(id).length) collapsed.add(id); }); render(); });
    document.getElementById("snapshot").addEventListener("input", event => { stopPlayback(); useSnapshot(Number(event.target.value)); });
    document.getElementById("prevSnapshot").addEventListener("click", () => { stopPlayback(); useSnapshot(snapshotIndex - 1); });
    document.getElementById("nextSnapshot").addEventListener("click", () => { stopPlayback(); useSnapshot(snapshotIndex + 1); });
    document.getElementById("playSnapshot").addEventListener("click", () => { playTimer ? stopPlayback() : startPlayback(); });
    document.getElementById("playSpeed").addEventListener("change", () => { if (playTimer) startPlayback(); });
    document.querySelectorAll("[data-collapse-panel]").forEach(button => {
      button.addEventListener("click", () => {
        const side = button.dataset.collapsePanel;
        const className = side === "left" ? "left-collapsed" : "right-collapsed";
        setPanelCollapsed(side, !document.body.classList.contains(className));
      });
    });
    document.getElementById("zoomOut").addEventListener("click", () => setZoom(graphScale - 0.12));
    document.getElementById("zoomIn").addEventListener("click", () => setZoom(graphScale + 0.12));
    document.getElementById("zoomReset").addEventListener("click", resetViewport);
    document.getElementById("zoomFit").addEventListener("click", fitTreeToViewport);
    document.addEventListener("pointerdown", startDagNodeDrag);
    document.addEventListener("pointermove", moveDagNode);
    document.addEventListener("pointerup", endDagNodeDrag);
    document.addEventListener("pointercancel", endDagNodeDrag);
    const canvas = document.getElementById("canvas");
    canvas.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      if (event.target.closest("button, input, select, .node, .dag-node, .edge-card, .edge-chip, .dag-edge-label, .dag-edge, .dag-edge-hit, .dag-edge-group")) return;
      isPanning = true;
      panStart = {x: event.clientX, y: event.clientY, panX, panY};
      canvas.classList.add("dragging");
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", event => {
      if (!isPanning) return;
      panX = panStart.panX + event.clientX - panStart.x;
      panY = panStart.panY + event.clientY - panStart.y;
      applyTreeTransform();
    });
    function endPan(event) {
      if (!isPanning) return;
      isPanning = false;
      canvas.classList.remove("dragging");
      try { canvas.releasePointerCapture(event.pointerId); } catch (_) {}
    }
    canvas.addEventListener("pointerup", endPan);
    canvas.addEventListener("pointercancel", endPan);
    canvas.addEventListener("wheel", event => {
      if (!(event.ctrlKey || event.metaKey || event.altKey)) return;
      event.preventDefault();
      const direction = event.deltaY > 0 ? -1 : 1;
      setZoom(graphScale + direction * 0.08, {x: event.clientX, y: event.clientY});
    }, {passive: false});
    window.addEventListener("resize", () => {
      syncStickyOffsets();
      requestAnimationFrame(fitTreeToViewport);
    });
    syncStickyOffsets();
    if (SNAPSHOTS.length) useSnapshot(snapshotIndex);
    else render();
  </script>
</body>
</html>
"""
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", help="任务目录；默认当前工作目录")
    parser.add_argument("--root", help="task-forest 数据目录；默认 <workspace>/.agent-workbench/task-forest")
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=float(os.environ.get("TASK_FOREST_LOCK_TIMEOUT", DEFAULT_LOCK_TIMEOUT_SECONDS)),
        help="等待 task-forest 写锁的秒数；默认 30 秒，可用 TASK_FOREST_LOCK_TIMEOUT 覆盖",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="维护 repo-local 任务森林/DAG、历史快照和 HTML 可视化。")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="初始化当前任务目录的 task-forest")
    add_common(p)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("add-node", help="新增任务节点")
    add_common(p)
    p.add_argument("--title", required=True)
    p.add_argument("--kind", default="task", choices=sorted(NODE_KINDS))
    p.add_argument("--status", default="proposed", choices=sorted(NODE_STATUSES))
    p.add_argument("--summary")
    p.add_argument("--purpose", help="该任务在全局目标中的意义或用户目的")
    p.add_argument("--desired-outcome", action="append", default=[], help="用户期望该任务带来的具体结果")
    p.add_argument("--requirement", action="append", default=[])
    p.add_argument("--acceptance", action="append", default=[])
    p.add_argument("--success-metric", action="append", default=[], help="判断目的是否达成的指标或证据")
    p.add_argument("--non-goal", action="append", default=[], help="明确不希望该任务承担的目标")
    p.add_argument("--assumption", action="append", default=[], help="生成或执行该任务时依赖的假设")
    p.add_argument("--alignment-json", help="任务与用户真实目标的结构化对齐摘要 JSON")
    p.add_argument("--progress", type=float, default=0.0)
    p.add_argument("--priority", type=int, default=3)
    p.add_argument("--difficulty", default="unknown", choices=sorted(DIFFICULTIES))
    p.add_argument("--estimate", type=int)
    p.add_argument("--remaining-min", type=int)
    p.add_argument("--remaining-max", type=int)
    p.add_argument("--confidence", type=float, default=0.6)
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--hint", action="append", default=[])
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--parent", action="append", default=[])
    p.add_argument("--depends-on", action="append", default=[])
    p.add_argument("--contributes-to", action="append", default=[])
    p.add_argument("--session-id")
    p.add_argument("--actor", default="codex")
    p.add_argument("--fields-json")
    p.add_argument("--fields-file")
    p.set_defaults(func=cmd_add_node)

    p = sub.add_parser("update-node", help="更新任务节点")
    add_common(p)
    p.add_argument("id")
    p.add_argument("--title")
    p.add_argument("--kind", choices=sorted(NODE_KINDS))
    p.add_argument("--status", choices=sorted(NODE_STATUSES))
    p.add_argument("--summary")
    p.add_argument("--purpose")
    p.add_argument("--alignment-json")
    p.add_argument("--progress", type=float)
    p.add_argument("--priority", type=int)
    p.add_argument("--difficulty", choices=sorted(DIFFICULTIES))
    p.add_argument("--estimate", type=int)
    p.add_argument("--remaining-min", type=int)
    p.add_argument("--remaining-max", type=int)
    p.add_argument("--confidence", type=float)
    p.add_argument("--append-requirement", action="append", default=[])
    p.add_argument("--append-acceptance", action="append", default=[])
    p.add_argument("--append-desired-outcome", action="append", default=[])
    p.add_argument("--append-success-metric", action="append", default=[])
    p.add_argument("--append-non-goal", action="append", default=[])
    p.add_argument("--append-assumption", action="append", default=[])
    p.add_argument("--append-tag", action="append", default=[])
    p.add_argument("--append-hint", action="append", default=[])
    p.add_argument("--append-evidence", action="append", default=[])
    p.add_argument("--actor", default="codex")
    p.add_argument("--fields-json")
    p.add_argument("--fields-file")
    p.set_defaults(func=cmd_update_node)

    p = sub.add_parser("add-edge", help="新增任务关系边")
    add_common(p)
    p.add_argument("--from", dest="from_id", required=True)
    p.add_argument("--to", dest="to_id", required=True)
    p.add_argument("--type", required=True, choices=sorted(EDGE_TYPES))
    p.add_argument("--reason")
    p.add_argument("--confidence", type=float, default=0.6)
    p.add_argument("--session-id")
    p.add_argument("--actor", default="codex")
    p.set_defaults(func=cmd_add_edge)

    p = sub.add_parser("remove-edge", help="删除任务关系边")
    add_common(p)
    p.add_argument("--id")
    p.add_argument("--from", dest="from_id")
    p.add_argument("--to", dest="to_id")
    p.add_argument("--type", choices=sorted(EDGE_TYPES))
    p.add_argument("--actor", default="codex")
    p.set_defaults(func=cmd_remove_edge)

    p = sub.add_parser("list", help="列出节点")
    add_common(p)
    p.add_argument("--status", choices=sorted(NODE_STATUSES))
    p.add_argument("--kind", choices=sorted(NODE_KINDS))
    p.add_argument("--tag")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="查看节点详情")
    add_common(p)
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("todo", help="列出未完成任务")
    add_common(p)
    p.add_argument("--ready", action="store_true")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_todo)

    p = sub.add_parser("export", help="导出 graph/todo/timeline JSON 和 HTML")
    add_common(p)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("validate", help="校验节点、边、DAG 和状态")
    add_common(p)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("proposal-save", help="保存并预校验 session 变更提案")
    add_common(p)
    p.add_argument("--proposal-json")
    p.add_argument("--proposal-file")
    p.add_argument("--session-id")
    p.add_argument("--overwrite", action="store_true", help="允许覆盖同名未应用 proposal")
    p.set_defaults(func=cmd_proposal_save)

    p = sub.add_parser("proposal-apply", help="应用已确认的变更提案")
    add_common(p)
    p.add_argument("proposal")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--allow-stale", action="store_true", help="允许应用基于旧 graph hash 的 proposal；仅在人工确认无冲突后使用")
    p.add_argument("--allow-reapply", action="store_true", help="允许重复应用已标记 applied 的 proposal")
    p.add_argument("--actor", default="codex")
    p.set_defaults(func=cmd_proposal_apply)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001 - CLI should report concise user-facing errors.
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
