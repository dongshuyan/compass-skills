#!/usr/bin/env python3
"""Publish or review a local, self-contained task plan. Python 3.9+."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import errno
from functools import partial
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

from events import apply_event, digest, initialize
from model import Conflict, Invalid, require, validate


SHELL = Path(__file__).resolve().parents[1] / "assets" / "report.html"
STATE = re.compile(r'<script id="task-planner-state" type="application/json" data-checksum="([0-9a-f]{64})">([^<]*)</script>')


def read_input(name):
    raw = sys.stdin.read() if name == "-" else Path(name).read_text(encoding="utf-8")
    return json.loads(raw)


def read_report(path):
    match = STATE.search(path.read_text(encoding="utf-8"))
    require(match is not None, "this HTML does not contain a task-planner record")
    state = json.loads(match.group(2))
    require(isinstance(state, dict) and state.get("format") == "task-planner/1", "unsupported plan format")
    require(match.group(1) == digest(state), "plan data changed outside the helper; restore a verified copy")
    validate(state)
    return state


def render(state):
    raw = json.dumps(state, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    data = raw.replace("&", r"\u0026").replace("<", r"\u003c").replace(">", r"\u003e")
    parts = {"__LANG__": html.escape(state["lang"], quote=True), "__TITLE__": html.escape(state["title"]),
             "__CHECKSUM__": digest(state), "__STATE__": data}
    return re.sub(r"__LANG__|__TITLE__|__CHECKSUM__|__STATE__",
                  lambda m: parts[m.group()], SHELL.read_text(encoding="utf-8"))


@contextmanager
def locked(path):
    # A stable inode keeps waiters synchronized across atomic HTML replacements.
    with path.with_name("." + path.name + ".lock").open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            acquire = partial(msvcrt.locking, handle.fileno(), msvcrt.LK_NBLCK, 1)
            release = partial(msvcrt.locking, handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            acquire = partial(fcntl.flock, handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            release = partial(fcntl.flock, handle.fileno(), fcntl.LOCK_UN)
        deadline = time.monotonic() + 10
        while True:
            try:
                acquire()
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    raise Conflict("another writer holds the file lock; retry shortly") from exc
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            release()


def publish(path, state):
    output = render(state)
    scratch = None
    try:
        with tempfile.NamedTemporaryFile("w", prefix="." + path.name + ".", suffix=".tmp",
                                         dir=path.parent, encoding="utf-8", delete=False) as handle:
            scratch = Path(handle.name)
            handle.write(output)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(scratch, path)
    finally:
        if scratch is not None:
            scratch.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("init", "write a new plan"), ("apply", "atomically record an event"),
                            ("status", "read the current plan")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("html", type=Path)
        if name == "status":
            command.add_argument("--full", action="store_true", help="include nodes and history")
        else:
            command.add_argument("input", help="JSON file, or - for standard input")
    args = parser.parse_args()
    path = args.html.expanduser().absolute()
    require(path.suffix.lower() in (".html", ".htm"), "choose a local HTML file")
    require(not path.is_symlink(), "use the actual report path, not a symbolic link")
    if args.command == "status":
        state = read_report(path)
        return state if args.full else validate(state).status()
    data = read_input(args.input)
    if args.command == "init":
        state = initialize(data)
        path.parent.mkdir(parents=True, exist_ok=True)
    with locked(path):
        if args.command == "init":
            require(not path.exists(), "file already exists; inspect it or choose a new report path")
            revision, changed = 1, True
        else:
            state = read_report(path)
            revision, changed = apply_event(state, data)
        if changed:
            publish(path, state)
    return {"html": str(path), "revision": state["revision"], "event_revision": revision, "applied": changed}


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False, allow_nan=False))
    except (Invalid, OSError, UnicodeError, ValueError) as exc:
        print(f"task-planner: {exc}", file=sys.stderr)
        sys.exit(3 if isinstance(exc, Conflict) else 2)
