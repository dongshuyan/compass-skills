#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from task_forest_html import render_overview_html
from task_forest_ordering import sibling_order_errors, sort_sibling_ids

SCHEMA_VERSION = 1
DEFAULT_LOCK_TIMEOUT_SECONDS = 30.0
DEFAULT_STALE_LOCK_SECONDS = 6 * 60 * 60
DEAD_PID_GRACE_SECONDS = 2.0
DEFAULT_AGENT_WORKBENCH_DB = (
    Path.home() / ".agent-workbench" / "agent-workbench.sqlite3"
)
WINDOWS_ERROR_ACCESS_DENIED = 5
WINDOWS_ERROR_INVALID_PARAMETER = 87
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102

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


def default_actor() -> str:
    return (
        os.environ.get("COMPASS_AGENT_NAME") or os.environ.get("AGENT_NAME") or "agent"
    ).strip() or "agent"


def _classify_posix_kill_outcome(exc: BaseException | None) -> bool | None:
    if exc is None:
        return True
    if isinstance(exc, ProcessLookupError):
        return False
    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, OSError):
        return None
    raise TypeError(f"Unsupported kill outcome: {exc!r}")


def _classify_windows_probe(
    open_error: int | None, wait_result: int | None
) -> bool | None:
    if open_error is not None:
        if open_error == WINDOWS_ERROR_INVALID_PARAMETER:
            return False
        if open_error == WINDOWS_ERROR_ACCESS_DENIED:
            return True
        return None
    if wait_result == WAIT_OBJECT_0:
        return False
    if wait_result == WAIT_TIMEOUT:
        return True
    return None


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


def update_global_registry(
    workspace: Path, command: str, error: str | None = None
) -> None:
    if os.environ.get("TASK_FOREST_DISABLE_GLOBAL_REGISTRY") in {"1", "true", "yes"}:
        return
    db_path = Path(
        os.environ.get("AGENT_WORKBENCH_DB") or DEFAULT_AGENT_WORKBENCH_DB
    ).expanduser()
    root = workspace / ".agent-workbench" / "task-forest"
    exports = root / "exports"
    graph_path = exports / "task-forest.graph.json"
    todos_path = exports / "task-forest.todos.json"
    timeline_path = exports / "task-forest.timeline.json"
    html_path = exports / "task-forest.html"
    graph_hash = sha256_path(graph_path)
    status = (
        "ok" if graph_path.exists() and todos_path.exists() and not error else "missing"
    )
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
        existing = [
            path
            for path in [graph_path, todos_path, timeline_path, html_path]
            if path.exists()
        ]
        if existing:
            last_export_at = datetime.fromtimestamp(
                max(path.stat().st_mtime for path in existing), timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
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
            return {
                "pid": pid,
                "started_at": parts[1] if len(parts) > 1 else None,
                "legacy": True,
            }

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
        if os.name == "nt":
            return self._pid_alive_windows(pid)
        return self._pid_alive_posix(pid)

    def _pid_alive_posix(self, pid: int) -> bool | None:
        try:
            os.kill(pid, 0)
            exc: BaseException | None = None
        except OSError as error:
            exc = error
        return _classify_posix_kill_outcome(exc)

    def _pid_alive_windows(self, pid: int) -> bool | None:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        wait_for_single_object = kernel32.WaitForSingleObject
        wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        wait_for_single_object.restype = wintypes.DWORD
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        process_access = 0x1000 | 0x00100000
        handle = open_process(process_access, False, pid)
        if not handle:
            return _classify_windows_probe(ctypes.get_last_error(), None)
        try:
            wait_result = wait_for_single_object(handle, 0)
            return _classify_windows_probe(None, int(wait_result))
        finally:
            close_handle(handle)

    def _break_stale_lock_if_safe(self) -> None:
        metadata = self._read_metadata()
        if not metadata:
            return
        age = self._lock_age(metadata)
        pid_alive = self._pid_alive(metadata.get("pid"))
        if pid_alive is True:
            return
        dead_pid_stale = (
            pid_alive is False and age is not None and age >= DEAD_PID_GRACE_SECONDS
        )
        unknown_stale = (
            pid_alive is None and age is not None and age >= self.stale_seconds
        )
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
            stale_seconds=float(
                os.environ.get(
                    "TASK_FOREST_STALE_LOCK_SECONDS", DEFAULT_STALE_LOCK_SECONDS
                )
            ),
        )

    def is_initialized(self) -> bool:
        return (
            self.config_path.exists()
            and self.nodes_path.exists()
            and self.edges_path.exists()
        )

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

    def load(
        self, assume_locked: bool = False
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
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

    def save(
        self, config: dict[str, Any], nodes: dict[str, Any], edges: dict[str, Any]
    ) -> None:
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
        config, nodes, edges = (
            read_json(self.config_path, {}),
            read_json(self.nodes_path, {}),
            read_json(self.edges_path, {}),
        )
        if not config:
            return
        for error in current_ordering_errors(nodes, edges):
            print(f"警告：{error}；HTML 已使用安全回退顺序。", file=sys.stderr)
        export = build_export(config, nodes, edges, reason="rebuild", event_id=None)
        write_json_atomic(self.forest_path, export["graph"])
        write_json_atomic(self.todos_path, export["todos"])
        write_json_atomic(
            self.root / "exports" / "task-forest.graph.json", export["graph"]
        )
        write_json_atomic(
            self.root / "exports" / "task-forest.todos.json", export["todos"]
        )
        snapshots = load_snapshots(self.root)
        write_json_atomic(
            self.root / "exports" / "task-forest.timeline.json", snapshots
        )
        html_text = render_overview_html(export["graph"], snapshots)
        (self.root / "exports").mkdir(parents=True, exist_ok=True)
        write_text_atomic(self.root / "exports" / "task-forest.html", html_text)
        (self.root / "exports" / "task-forest.audit.html").unlink(missing_ok=True)
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


def normalize_node(
    raw: dict[str, Any], node_id: str, title: str | None = None
) -> dict[str, Any]:
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
    base["alignment"]["validation_plan"] = normalize_list(
        base["alignment"].get("validation_plan")
    )
    try:
        base["alignment"]["fit_confidence"] = float(
            base["alignment"].get("fit_confidence") or 0.0
        )
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


def edge_defaults(
    edge_id: str, source: str, target: str, edge_type: str
) -> dict[str, Any]:
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


def normalize_edge(
    raw: dict[str, Any], edge_id: str, source: str, target: str, edge_type: str
) -> dict[str, Any]:
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


def validate_state(
    nodes: dict[str, Any], edges: dict[str, Any]
) -> tuple[list[str], list[str]]:
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
            warnings.append(
                f"节点 {node_id} 的 difficulty 未规范化：{node.get('difficulty')}"
            )
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
            errors.append(
                f"节点 {node_id} 有多个 child_of 父节点；请改用 contributes_to 表达多归属"
            )

    errors.extend(current_ordering_errors(nodes, edges))

    for edge_type in ("child_of", "depends_on"):
        cycle = detect_cycle(edges, edge_type)
        if cycle:
            errors.append(f"{edge_type} 出现环：{' -> '.join(cycle)}")

    return errors, warnings


def ordering_groups(
    nodes: dict[str, Any], edges: dict[str, Any]
) -> dict[str | None, list[str]]:
    groups: dict[str | None, list[str]] = {}
    parented: set[str] = set()
    for edge in edges.values():
        if edge.get("type") != "child_of":
            continue
        child = edge.get("from")
        parent = edge.get("to")
        if child in nodes and parent in nodes:
            groups.setdefault(str(parent), []).append(str(child))
            parented.add(str(child))
    groups[None] = [node_id for node_id in nodes if node_id not in parented]
    return groups


def current_ordering_errors(nodes: dict[str, Any], edges: dict[str, Any]) -> list[str]:
    return sibling_order_errors(nodes, ordering_groups(nodes, edges))


def build_children(
    edges: dict[str, Any], nodes: dict[str, Any]
) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {}
    for edge in edges.values():
        if (
            edge.get("type") == "child_of"
            and edge.get("from") in nodes
            and edge.get("to") in nodes
        ):
            children.setdefault(edge["to"], []).append(edge["from"])
    for parent_id, values in children.items():
        values[:] = sort_sibling_ids(values, nodes, parent_id)
    return children


def build_parents(edges: dict[str, Any]) -> dict[str, str]:
    parents: dict[str, str] = {}
    for edge in edges.values():
        if edge.get("type") == "child_of":
            parents[edge["from"]] = edge["to"]
    return parents


def criterion_done(item: Any) -> bool:
    if isinstance(item, dict):
        return str(item.get("status", "")).lower() in {
            "done",
            "passed",
            "complete",
            "completed",
        }
    return False


def derived_progress(
    node_id: str,
    nodes: dict[str, Any],
    children: dict[str, list[str]],
    memo: dict[str, float],
) -> float:
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
        value = sum(
            derived_progress(child, nodes, children, memo) for child in child_ids
        ) / len(child_ids)
    elif criteria and all(isinstance(item, dict) for item in criteria):
        value = (
            100.0
            * sum(1 for item in criteria if criterion_done(item))
            / max(1, len(criteria))
        )
    else:
        value = clamp_progress(node.get("progress"))
    memo[node_id] = round(value, 1)
    return memo[node_id]


def dependency_status(
    node_id: str, nodes: dict[str, Any], edges: dict[str, Any]
) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    for edge in edges.values():
        if edge.get("type") == "depends_on" and edge.get("from") == node_id:
            dep = edge.get("to")
            if dep in nodes and nodes[dep].get("status") != "done":
                blockers.append(dep)
    return len(blockers) == 0, blockers


def estimate_remaining(
    node: dict[str, Any], progress: float
) -> tuple[int | None, int | None]:
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
    edge_type_counts: dict[str, int] = {
        edge_type: 0 for edge_type in sorted(EDGE_TYPES)
    }
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


def build_status_queues(
    nodes: dict[str, Any], todos: list[dict[str, Any]]
) -> dict[str, Any]:
    by_status: dict[str, list[str]] = {status: [] for status in sorted(NODE_STATUSES)}
    for node_id, node in nodes.items():
        by_status.setdefault(str(node.get("status")), []).append(node_id)
    for values in by_status.values():
        values.sort()
    actionable = [
        item["id"]
        for item in todos
        if not (
            item.get("kind") == "global_task"
            and item.get("status") == "in_progress"
            and item.get("remaining_minutes_min") is None
        )
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
        "open": sorted(
            [
                node_id
                for node_id, node in nodes.items()
                if node.get("status") in OPEN_STATUSES
            ]
        ),
        "review_needed": by_status.get("review_needed", []),
        "blocked": by_status.get("blocked", []),
        "ready": by_status.get("ready", []),
        "actionable_todos": actionable,
        "evergreen_open_goals": sorted(evergreen),
    }


def build_todos(
    nodes: dict[str, Any], edges: dict[str, Any], progress_by_id: dict[str, float]
) -> list[dict[str, Any]]:
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
    todos.sort(
        key=lambda item: (
            not item["ready"],
            -int(item.get("priority") or 0),
            item["id"],
        )
    )
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
    children = build_children(edges, nodes)
    parents = build_parents(edges)
    progress_memo: dict[str, float] = {}
    progress_by_id = {
        node_id: derived_progress(node_id, nodes, children, progress_memo)
        for node_id in nodes
    }
    roots = sort_sibling_ids(
        [node_id for node_id in nodes if node_id not in parents], nodes, None
    )
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
            "open_count": sum(
                1 for node in nodes.values() if node.get("status") in OPEN_STATUSES
            ),
            "done_count": sum(
                1 for node in nodes.values() if node.get("status") == "done"
            ),
            "blocked_count": sum(
                1 for node in nodes.values() if node.get("status") == "blocked"
            ),
            "review_needed_count": sum(
                1 for node in nodes.values() if node.get("status") == "review_needed"
            ),
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
    actual_id = (
        node_id
        or fields.get("id")
        or f"TF-{int(config.get('next_node_number', 1)):04d}"
    )
    if actual_id in nodes:
        raise ValueError(f"节点已存在：{actual_id}")
    if (
        actual_id.startswith("TF-")
        and actual_id == f"TF-{int(config.get('next_node_number', 1)):04d}"
    ):
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
            nodes[node_id] = merge_fields(
                nodes[node_id], dict(change.get("fields") or {})
            )
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
                {
                    "status": "deprecated",
                    "deprecated_at": now_iso(),
                    "summary": change.get("reason", nodes[node_id].get("summary", "")),
                },
            )
        elif action == "add_edge":
            source = resolve(str(change.get("from")))
            target = resolve(str(change.get("to")))
            add_edge(
                config,
                nodes,
                edges,
                source,
                target,
                str(change.get("type")),
                dict(change.get("edge") or {}),
            )
        elif action == "remove_edge":
            edge_id = change.get("id")
            if edge_id:
                edges.pop(str(edge_id), None)
            else:
                source = resolve(str(change.get("from")))
                target = resolve(str(change.get("to")))
                edge_type = str(change.get("type"))
                to_remove = [
                    eid
                    for eid, edge in edges.items()
                    if edge["from"] == source
                    and edge["to"] == target
                    and edge["type"] == edge_type
                ]
                for eid in to_remove:
                    edges.pop(eid, None)
        elif action == "record_deviation":
            deviation = dict(change.get("deviation") or {})
            deviation.setdefault("id", f"TFD-{uuid.uuid4().hex[:10]}")
            deviation.setdefault("created_at", now_iso())
            related = [
                resolve(str(item))
                for item in normalize_list(deviation.get("related_task_ids"))
            ]
            deviation["related_task_ids"] = related
            for node_id in related:
                if node_id in nodes:
                    nodes[node_id].setdefault("deviations", []).append(deviation["id"])
            change["deviation"] = deviation
        elif action == "record_alignment":
            alignment = dict(change.get("alignment") or {})
            alignment.setdefault("id", f"TFA-{uuid.uuid4().hex[:10]}")
            alignment.setdefault("created_at", now_iso())
            related = [
                resolve(str(item))
                for item in normalize_list(alignment.get("related_task_ids"))
            ]
            alignment["related_task_ids"] = related
            for node_id in related:
                if node_id in nodes:
                    nodes[node_id].setdefault("alignment_records", []).append(
                        alignment["id"]
                    )
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
    print(
        f"{node['id']} | {node.get('status')} | {node.get('kind')} | {node.get('derived_progress', node.get('progress', 0))}% | {node.get('title')}"
    )
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
            add_edge(
                config,
                nodes,
                edges,
                node_id,
                parent,
                "child_of",
                {"reason": "CLI add-node --parent"},
            )
        for dep in args.depends_on:
            add_edge(
                config,
                nodes,
                edges,
                node_id,
                dep,
                "depends_on",
                {"reason": "CLI add-node --depends-on"},
            )
        for target in args.contributes_to:
            add_edge(
                config,
                nodes,
                edges,
                node_id,
                target,
                "contributes_to",
                {"reason": "CLI add-node --contributes-to"},
            )
        errors, _ = validate_state(nodes, edges)
        if errors:
            raise ValueError("; ".join(errors))
        after = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        event = store.record_event(
            "add_node",
            args.actor,
            {"node_id": node_id, "title": args.title},
            before,
            after,
        )
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
        for key in [
            "title",
            "kind",
            "status",
            "summary",
            "priority",
            "difficulty",
            "estimate",
            "remaining_min",
            "remaining_max",
            "confidence",
        ]:
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
        event = store.record_event(
            "update_node",
            args.actor,
            {"node_id": args.id, "fields": sorted(fields)},
            before,
            after,
        )
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
            {
                "reason": args.reason or "",
                "confidence": args.confidence,
                "created_from_session": args.session_id,
            },
        )
        after = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        event = store.record_event(
            "add_edge", args.actor, {"edge_id": edge_id}, before, after
        )
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
                if (
                    edge["from"] == args.from_id
                    and edge["to"] == args.to_id
                    and edge["type"] == args.type
                ):
                    removed.append(edge_id)
                    edges.pop(edge_id)
        errors, _ = validate_state(nodes, edges)
        if errors:
            raise ValueError("; ".join(errors))
        after = {"nodes": copy.deepcopy(nodes), "edges": copy.deepcopy(edges)}
        event = store.record_event(
            "remove_edge", args.actor, {"removed": removed}, before, after
        )
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
        related = [
            edge
            for edge in graph["edges"].values()
            if edge["from"] == args.id or edge["to"] == args.id
        ]
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
            estimate = (
                f"{item['remaining_minutes_min']}-{item['remaining_minutes_max']} 分钟"
            )
        ready = "ready" if item["ready"] else "blocked"
        print(
            f"{item['id']} | {ready} | P{item['priority']} | {item['progress']}% | {estimate} | {item['title']}"
        )
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
            {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "workspace_path": str(workspace),
            },
        )
        dry_config, dry_nodes, dry_edges = (
            copy.deepcopy(config),
            copy.deepcopy(nodes),
            copy.deepcopy(edges),
        )
        apply_changes(dry_config, dry_nodes, dry_edges, list(proposal["changes"]))
        proposal_path = store.root / "proposals" / f"{proposal_id}.json"
        if proposal_path.exists() and not args.overwrite:
            raise ValueError(
                f"proposal 已存在：{proposal_id}；如确需替换请传入 --overwrite"
            )
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
            {
                "proposal_id": proposal.get("proposal_id"),
                "session_id": proposal.get("session_id"),
                "change_count": len(changes),
            },
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
        store.write_snapshot(
            config, nodes, edges, "proposal_applied", event["event_id"]
        )
        store.save(config, nodes, edges)
        store.rebuild_generated()
    update_global_registry(workspace, "proposal-apply")
    print(f"已应用变更提案：{proposal.get('proposal_id')}")
    return 0


def html_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", help="任务目录；默认当前工作目录")
    parser.add_argument(
        "--root",
        help="task-forest 数据目录；默认 <workspace>/.agent-workbench/task-forest",
    )
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=float(
            os.environ.get("TASK_FOREST_LOCK_TIMEOUT", DEFAULT_LOCK_TIMEOUT_SECONDS)
        ),
        help="等待 task-forest 写锁的秒数；默认 30 秒，可用 TASK_FOREST_LOCK_TIMEOUT 覆盖",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="维护 repo-local 任务森林/DAG、历史快照和 HTML 可视化。"
    )
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
    p.add_argument(
        "--desired-outcome",
        action="append",
        default=[],
        help="用户期望该任务带来的具体结果",
    )
    p.add_argument("--requirement", action="append", default=[])
    p.add_argument("--acceptance", action="append", default=[])
    p.add_argument(
        "--success-metric",
        action="append",
        default=[],
        help="判断目的是否达成的指标或证据",
    )
    p.add_argument(
        "--non-goal", action="append", default=[], help="明确不希望该任务承担的目标"
    )
    p.add_argument(
        "--assumption", action="append", default=[], help="生成或执行该任务时依赖的假设"
    )
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
    p.add_argument("--actor", default=default_actor())
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
    p.add_argument("--actor", default=default_actor())
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
    p.add_argument("--actor", default=default_actor())
    p.set_defaults(func=cmd_add_edge)

    p = sub.add_parser("remove-edge", help="删除任务关系边")
    add_common(p)
    p.add_argument("--id")
    p.add_argument("--from", dest="from_id")
    p.add_argument("--to", dest="to_id")
    p.add_argument("--type", choices=sorted(EDGE_TYPES))
    p.add_argument("--actor", default=default_actor())
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
    p.add_argument(
        "--overwrite", action="store_true", help="允许覆盖同名未应用 proposal"
    )
    p.set_defaults(func=cmd_proposal_save)

    p = sub.add_parser("proposal-apply", help="应用已确认的变更提案")
    add_common(p)
    p.add_argument("proposal")
    p.add_argument("--yes", action="store_true")
    p.add_argument(
        "--allow-stale",
        action="store_true",
        help="允许应用基于旧 graph hash 的 proposal；仅在人工确认无冲突后使用",
    )
    p.add_argument(
        "--allow-reapply",
        action="store_true",
        help="允许重复应用已标记 applied 的 proposal",
    )
    p.add_argument("--actor", default=default_actor())
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
