#!/usr/bin/env python3
"""Project-local prompt reminder and one-shot Stop check; never rename from a hook."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import shlex
import subprocess
import sys
import time

from title_runtime import (ID, STATUSES, TitleError, TitleManager, installation, in_scope,
                           is_global, superseded, resolve_scope, locked, write_json, scope_locked)
from clarity_rpc import CodexRPC, RPCError


def read_object(path):
    if path.is_symlink() or path.parent.is_symlink():
        raise TitleError('标题检查记录不能是符号链接')
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TitleError('标题检查记录损坏')
    return value


def owns_global_hook(root, plugin_root):
    """Accept exact inherited bundles; reject duplicate or locally altered code."""
    receipt = read_object(root / '.local/agent-clarity/plugin.json')
    plugin_root = Path(plugin_root)
    if not (plugin_root / 'global-installation.json').exists():
        skill = receipt.get('skill_path')
        return (isinstance(skill, str) and Path(skill).is_absolute()
                and len(Path(skill).parents) > 2 and Path(skill).parents[2] == plugin_root)
    prefix = 'plugins/clarity-session-titles/'
    files = receipt.get('files')
    if not isinstance(files, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                         for k, v in files.items()):
        return False
    expected = {name[len(prefix):]: value for name, value in files.items()
                if name.startswith(prefix)}
    if not expected or not receipt.get('enabled') or receipt.get('scope') != 'global':
        return False
    actual = {}
    for path in plugin_root.rglob('*'):
        if path.is_symlink():
            return False
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        if path.is_file():
            actual[str(path.relative_to(plugin_root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return actual == expected


def reminder(root):
    script = Path(__file__).resolve().with_name('title_runtime.py')
    selector = '--global' if is_global(root) else '--project ' + shlex.quote(str(root))
    command = f'python3 {shlex.quote(str(script))} {selector} set'
    return ('当前范围已启用三段式标题。即使是简短问答、无需其他工具，也须在最终回复前'
            '通过执行工具核对一次当前会话标题：' + command +
            ' --topic "初始需求" --status "真实状态" --progress "具体进展"。'
            '初始需求保持稳定，两段描述各不超过28字。状态可选：' + '、'.join(STATUSES) + '。'
            '回答结束不等于任务完成。脚本会保留用户手动改名；返回 paused、pending、'
            'disabled、out_of_scope 或错误时继续用户任务，不重复尝试。'
            '这是后台维护，不要把改名过程加入给用户的正文。')


def guard(root, payload, rpc):
    """Fail open on uncertain state; a hook failure must not trap the user's turn."""
    try:
        with scope_locked():
            return _guard(Path(root).resolve(), payload, rpc)
    except (TitleError, RPCError, OSError, ValueError, TypeError, KeyError):
        return {}


def _guard(root, payload, rpc):
    if not isinstance(payload, dict):
        return {}
    event = payload.get('hook_event_name')
    if event not in ('UserPromptSubmit', 'Stop'):
        return {}
    if event == 'Stop' and payload.get('stop_hook_active'):
        return {}
    if superseded(root):
        return {}
    thread_id, turn_id = payload.get('session_id'), payload.get('turn_id')
    if (not isinstance(thread_id, str) or not ID.fullmatch(thread_id)
            or not isinstance(turn_id, str) or not ID.fullmatch(turn_id)
            or not in_scope(root, payload.get('cwd'))):
        return {}
    active = installation(root)
    if not active or not active['enabled']:
        return {}
    # Serialize with deactivation/uninstall and re-read after acquiring the lock.
    # This also keeps a late hook from consuming the next turn's repair budget.
    with locked(root / '.local/title-installation.lock'):
        active = installation(root)
        if not active or not active['enabled']:
            return {}
        return _active_guard(root, event, thread_id, turn_id, active, rpc, payload['cwd'])


def _active_guard(root, event, thread_id, turn_id, active, rpc, cwd):
    thread = TitleManager(root, rpc, caller_thread_id=thread_id)._read_thread(thread_id)
    if is_global(root) and Path(thread['cwd']).resolve() != Path(cwd).resolve():
        return {}
    created = thread.get('createdAt')
    if type(created) not in (int, float) or created < active['created_after']:
        return {}
    directory = root / '.local/title-turns'
    if directory.is_symlink():
        raise TitleError('标题检查目录不能是符号链接')
    path = directory / f'{thread_id}.json'
    if event == 'Stop' and not path.exists():
        return {}
    directory.mkdir(exist_ok=True)
    with locked(directory / f'{thread_id}.lock'):
        turn = read_object(path)
        if event == 'UserPromptSubmit':
            if turn.get('turn_id') != turn_id:
                turn = {'turn_id': turn_id, 'started_at_ns': time.time_ns(), 'repair_requested': False}
                write_json(path, turn)
            return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': reminder(root)}}
        if (turn.get('turn_id') != turn_id or turn.get('repair_requested')
                or type(turn.get('started_at_ns')) is not int):
            return {}
        state = read_object(root / '.local/titles' / f'{thread_id}.json')
        if state.get('paused') or 'pending' in state:
            return {}
        # An external non-three-part title is deliberately left to the manager's
        # protection logic; a successful check must also match the current name.
        checked = state.get('checked_at_ns')
        if (state.get('checked_turn_id') == turn_id
                and type(checked) is int and checked >= turn['started_at_ns']
                and state.get('last_applied') == thread.get('name')):
            return {}
        turn['repair_requested'] = True
        write_json(path, turn)
        return {'decision': 'block', 'reason': (
            '本轮回复已生成，但还没有完成已启用的标题核对。只补做一次标题维护，'
            '不要重写刚才的回答；成功或失败后都结束本轮。' + reminder(root))}


def main():
    try:
        payload = json.load(sys.stdin)
        cwd = payload.get('cwd') if isinstance(payload, dict) else None
        if not isinstance(cwd, str):
            print('{}')
            return 0
        root = resolve_scope(cwd)
        if root is None:
            print('{}')
            return 0
        if is_global(root):
            # The project and global package may coexist. Only the global
            # installed copy may run the global hook, avoiding duplicate events.
            if not owns_global_hook(root, Path(__file__).resolve().parents[1]):
                print('{}')
                return 0
        active = installation(root)
        if not active or not active['enabled'] or not in_scope(root, cwd):
            print('{}')
            return 0
        with CodexRPC(cwd=cwd, timeout=6, local_only=True) as rpc:
            result = guard(root, payload, rpc)
        print(json.dumps(result, ensure_ascii=False))
    except (TitleError, RPCError, OSError, ValueError, subprocess.SubprocessError):
        print('{}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
