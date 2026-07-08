#!/usr/bin/env python3
"""Run local smoke tests for task-forest lock recovery behavior."""

from __future__ import annotations

import argparse
import importlib.util
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest import mock


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def age_file(path: Path, *, hours: float) -> None:
    timestamp = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
    os.utime(path, (timestamp, timestamp))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test task-forest lock recovery logic.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    skill_dir = Path(args.skill_dir).resolve()
    task_forest = import_module(skill_dir / "scripts" / "task_forest.py", "task_forest_locking")

    assert task_forest._classify_posix_kill_outcome(None) is True
    assert task_forest._classify_posix_kill_outcome(ProcessLookupError()) is False
    assert task_forest._classify_posix_kill_outcome(PermissionError()) is True
    assert task_forest._classify_posix_kill_outcome(OSError()) is None

    assert task_forest._classify_windows_probe(task_forest.WINDOWS_ERROR_INVALID_PARAMETER, None) is False
    assert task_forest._classify_windows_probe(task_forest.WINDOWS_ERROR_ACCESS_DENIED, None) is True
    assert task_forest._classify_windows_probe(1234, None) is None
    assert task_forest._classify_windows_probe(None, task_forest.WAIT_OBJECT_0) is False
    assert task_forest._classify_windows_probe(None, task_forest.WAIT_TIMEOUT) is True
    assert task_forest._classify_windows_probe(None, 0xFFFFFFFF) is None

    with tempfile.TemporaryDirectory(prefix="compass-task-forest-lock-") as tmp:
        root = Path(tmp)

        empty_lock = root / "empty.lock"
        empty_lock.write_text("", encoding="utf-8")
        age_file(empty_lock, hours=12)
        empty = task_forest.FileLock(empty_lock, timeout=0.1, stale_seconds=10)
        empty._break_stale_lock_if_safe()
        assert not empty_lock.exists(), "empty stale lock should be removed via mtime fallback"

        broken_lock = root / "broken.lock"
        broken_lock.write_text("[1, 2, 3]\n", encoding="utf-8")
        age_file(broken_lock, hours=12)
        broken = task_forest.FileLock(broken_lock, timeout=0.1, stale_seconds=10)
        broken._break_stale_lock_if_safe()
        assert not broken_lock.exists(), "non-dict JSON lock should be removed via mtime fallback"

        dead_pid_lock = root / "dead-pid.lock"
        dead_pid_lock.write_text('{"token":"other","pid":999,"started_at":"2026-01-01T00:00:00.000000Z"}\n', encoding="utf-8")
        dead_pid = task_forest.FileLock(dead_pid_lock, timeout=0.1, stale_seconds=60 * 60)
        with mock.patch.object(dead_pid, "_pid_alive", return_value=False), mock.patch.object(
            dead_pid, "_best_effort_unlink", return_value=True
        ) as cleanup:
            dead_pid._break_stale_lock_if_safe()
            cleanup.assert_called_once()

        lease_lock = root / "lease.lock"
        lease_lock.write_text('{"token":"other","pid":999,"started_at":"2026-01-01T00:00:00.000000Z"}\n', encoding="utf-8")
        age_file(lease_lock, hours=12)
        lease = task_forest.FileLock(lease_lock, timeout=0.1, stale_seconds=10)
        with mock.patch.object(lease, "_pid_alive", return_value=True), mock.patch.object(
            lease, "_best_effort_unlink", return_value=True
        ) as cleanup:
            lease._break_stale_lock_if_safe()
            cleanup.assert_called_once()

        owned_lock = root / "owned.lock"
        owned_lock.write_text('{"token":"mine","pid":1,"started_at":"2026-01-01T00:00:00.000000Z"}\n', encoding="utf-8")
        owned = task_forest.FileLock(owned_lock, timeout=0.1, stale_seconds=10)
        owned.token = "mine"
        with mock.patch.object(type(owned_lock), "unlink", side_effect=PermissionError("busy")):
            owned._unlink_if_owned()

        foreign_lock = root / "foreign.lock"
        foreign_lock.write_text("not-json", encoding="utf-8")
        foreign = task_forest.FileLock(foreign_lock, timeout=0.1, stale_seconds=10)
        foreign.token = "mine"
        foreign._unlink_if_owned()
        assert foreign_lock.exists(), "release should not delete unreadable non-owned lock"

        stale_lock = root / "stale.lock"
        stale_lock.write_text('{"token":"other","pid":999,"started_at":"2026-01-01T00:00:00.000000Z"}\n', encoding="utf-8")
        age_file(stale_lock, hours=12)
        stale = task_forest.FileLock(stale_lock, timeout=0.1, stale_seconds=10)
        with mock.patch.object(stale, "_pid_alive", return_value=True), mock.patch.object(
            type(stale_lock), "unlink", side_effect=PermissionError("busy")
        ):
            stale._break_stale_lock_if_safe()

    print("ok=task-forest locking smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
