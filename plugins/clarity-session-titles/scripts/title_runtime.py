#!/usr/bin/env python3
"""Scoped status｜initial request｜progress titles, using the Codex app-server API."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata

from clarity_rpc import CodexRPC, RPCError
from title_segments import parse_three_part_title, merge_protected_title, TITLE_SEGMENTS

STATUSES = ('讨论中', '调研中', '方案中', '实现中', '验证中', '待确认', '待验证', '已完成', '已暂停', '受阻')
ID = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')
GLOBAL_BINDING = Path(__file__).resolve().parents[1] / 'global-installation.json'


class TitleError(RuntimeError):
    pass


_scope_nesting = threading.local()


def codex_home():
    return Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).resolve()


def global_root():
    if GLOBAL_BINDING.is_symlink():
        raise TitleError('共享安装绑定不能是符号链接')
    if GLOBAL_BINDING.exists():
        try:
            value = json.loads(GLOBAL_BINDING.read_text())
            root = value.get('root') if isinstance(value, dict) else None
            if (not isinstance(root, str) or not root or value.get('version') != 1
                    or not Path(root).is_absolute() or Path(root).resolve() != Path(root)):
                raise ValueError('invalid portable binding')
            return Path(root)
        except (ValueError, TypeError) as error:
            raise TitleError('共享安装绑定无效；未回退到其他账户状态') from error
    return codex_home() / 'agent-clarity'


def is_global(root):
    return Path(root).resolve() == global_root()


def superseded(root):
    if is_global(root):
        return False
    active = installation(global_root())
    return bool(active and active['enabled'])


def resolve_scope(cwd):
    """Global configuration takes priority; project configuration remains usable alone."""
    active = installation(global_root())
    if active and active['enabled']:
        return global_root()
    try:
        root = Path(subprocess.check_output(['git', '-C', str(cwd), 'rev-parse', '--show-toplevel'],
                    text=True, stderr=subprocess.DEVNULL, timeout=3).strip()).resolve()
        active = installation(root)
        return root if active and active['enabled'] and in_scope(root, cwd) else None
    except subprocess.SubprocessError:
        return None


def normalize_title(topic, status, progress, *, topic_limit=28):
    for label, value in [('初始需求', topic), ('当前进展', progress)]:
        limit = topic_limit if label == '初始需求' else 28
        if (not isinstance(value, str) or not value.strip() or len(value.strip()) > limit
                or any(c in value for c in '|｜')
                or any(unicodedata.category(c).startswith('C') for c in value)):
            raise TitleError(f'{label}须为 1 到 {limit} 个字符，且不含分隔符或控制字符')
    if not isinstance(status, str) or status not in STATUSES:
        raise TitleError('状态须从以下选取：' + '、'.join(STATUSES))
    return f'{status}｜{topic.strip()}｜{progress.strip()}'


def in_scope(root, cwd):
    if not isinstance(cwd, (str, Path)) or not str(cwd):
        return False
    root, cwd = root.resolve(), Path(cwd).resolve()
    if is_global(root):
        return cwd.is_dir()
    try:
        relative = cwd.relative_to(root)
        if relative.parts and relative.parts[0] in {'reference', '.local', '.git'}:
            return False
        git_root = subprocess.check_output(['git', '-C', str(cwd), 'rev-parse', '--show-toplevel'],
                                           stderr=subprocess.DEVNULL, text=True, timeout=3).strip()
        return Path(git_root).resolve() == root
    except (ValueError, OSError, subprocess.SubprocessError):
        return False


def write_json(path, value):
    if path.is_symlink():
        raise TitleError('状态文件不能是符号链接')
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, encoding='utf-8',
                                     prefix='.title-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


@contextmanager
def locked(path):
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        deadline = time.monotonic() + 3
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TitleError('这个会话的标题正在更新，请稍后重试')
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)


@contextmanager
def scope_locked():
    """One account lock serializes scope changes and title writes; nested calls share it."""
    root = global_root()
    if root.is_symlink():
        raise TitleError('账户标题状态目录不能是符号链接')
    root.mkdir(parents=True, exist_ok=True)
    depths = getattr(_scope_nesting, 'depths', {})
    _scope_nesting.depths = depths
    key = str(root)
    if depths.get(key):
        depths[key] += 1
        try:
            yield
        finally:
            depths[key] -= 1
        return
    with locked(root / '.scope.lock'):
        depths[key] = 1
        try:
            yield
        finally:
            depths.pop(key)


def save_title_state(path, state):
    state['revision'] = state.get('revision', 0) + 1
    write_json(path, state)


def read_title_state(path):
    if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink():
        raise TitleError('标题保护记录不能是符号链接')
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text())
    except ValueError as error:
        raise TitleError('标题保护记录损坏') from error
    if (not isinstance(state, dict) or type(state.get('revision', 0)) is not int
            or state.get('revision', 0) < 0):
        raise TitleError('标题保护记录损坏')
    return state


def peer_state_path(root, cwd, thread_id):
    if not is_global(root):
        peer = global_root()
    else:
        try:
            peer = Path(subprocess.check_output(['git', '-C', str(cwd), 'rev-parse', '--show-toplevel'],
                    text=True, stderr=subprocess.DEVNULL, timeout=3).strip()).resolve()
        except subprocess.SubprocessError:
            return None
    if peer == Path(root).resolve() or not installation(peer):
        return None
    return peer / '.local/titles' / f'{thread_id}.json'


def state_directory(root):
    directory = Path(root) / '.local'
    if directory.is_symlink():
        raise TitleError('本地状态目录不能是符号链接')
    directory.mkdir(exist_ok=True)
    return directory


def installation(root):
    path = Path(root) / '.local/title-installation.json'
    if (Path(root) / '.local').is_symlink() or path.is_symlink():
        raise TitleError('安装记录不能是符号链接')
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text())
        if (value.get('version') != 1 or value.get('root') != str(Path(root).resolve())
                or type(value.get('created_after')) is not int
                or type(value.get('enabled')) is not bool
                or value.get('scope', 'project') != ('global' if is_global(root) else 'project')):
            raise ValueError('invalid installation')
        return value
    except (ValueError, AttributeError) as error:
        raise TitleError('安装记录损坏或项目已移动，请检查 .local/title-installation.json') from error


def current_turn_id(root, thread_id):
    """Capture the prompt generation before a title operation waits for any lock."""
    if not isinstance(thread_id, str) or not ID.fullmatch(thread_id):
        raise TitleError('缺少有效的 CODEX_THREAD_ID')
    directory = Path(root) / '.local/title-turns'
    path = directory / f'{thread_id}.json'
    if (Path(root) / '.local').is_symlink() or directory.is_symlink() or path.is_symlink():
        raise TitleError('标题回合记录不能是符号链接')
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    turn_id = value.get('turn_id') if isinstance(value, dict) else None
    if not isinstance(turn_id, str) or not ID.fullmatch(turn_id):
        raise TitleError('标题回合记录损坏')
    return turn_id


def activate(root, *, now=None, global_mode=False):
    root = Path(root).resolve()
    if global_mode != is_global(root):
        raise TitleError('全局模式只能安装在当前 CODEX_HOME 的 agent-clarity 目录')
    directory = state_directory(root)
    with scope_locked(), locked(directory / 'title-installation.lock'):
        value = installation(root) or {'version': 1, 'root': str(root),
                                      'created_after': math.ceil(time.time() if now is None else now)}
        if value.get('enabled') is False:
            value['created_after'] = math.ceil(time.time() if now is None else now)
        value['enabled'] = True
        if global_mode:
            value.update(scope='global', created_after=0)
        write_json(directory / 'title-installation.json', value)
    if now is None and not global_mode:
        # Thread.createdAt has second precision. Finish activation at the boundary
        # so an immediately launched new chat is included without admitting old ones.
        time.sleep(min(1, max(0, value['created_after'] - time.time())))
    return value


class TitleManager:
    def __init__(self, root, rpc, *, caller_thread_id):
        self.root, self.rpc = Path(root).resolve(), rpc
        self.caller_thread_id = caller_thread_id

    def _read_thread(self, thread_id):
        result = self.rpc.request('thread/read', {'threadId': thread_id, 'includeTurns': False})
        if not isinstance(result, dict) or not isinstance(result.get('thread'), dict):
            raise TitleError('Codex 返回了无效的会话元数据')
        thread = result['thread']
        if thread.get('id') != thread_id or not in_scope(self.root, thread.get('cwd')):
            raise TitleError('目标会话不属于这个测试项目，未改名')
        source = thread.get('source')
        if (not is_global(self.root) and (thread.get('forkedFromId') or thread.get('parentThreadId'))
                or thread.get('sessionId', thread_id) != thread_id
                or isinstance(source, dict) and 'subAgent' in source):
            raise TitleError('项目模式只管理根会话；所有模式均不接管内部子代理')
        if thread.get('name') is not None and not isinstance(thread['name'], str):
            raise TitleError('Codex 返回了无效标题')
        return thread

    def set(self, thread_id, topic, status, cwd, *, progress):
        # An operation queued in an earlier turn must never certify a later one.
        turn_id = current_turn_id(self.root, thread_id)
        with scope_locked():
            if superseded(self.root):
                return {'result': 'disabled', 'reason': '当前账户已由全局标题安装接管'}
            if (self.root / '.local/title-installation.json').exists():
                if (self.root / '.local').is_symlink():
                    raise TitleError('本地状态目录不能是符号链接')
                with locked(self.root / '.local/title-installation.lock'):
                    return self._set(thread_id, topic, status, cwd, progress=progress, turn_id=turn_id)
            return self._set(thread_id, topic, status, cwd, progress=progress, turn_id=turn_id)

    def _set(self, thread_id, topic, status, cwd, *, progress, turn_id):
        if not ID.fullmatch(thread_id or ''):
            raise TitleError('缺少有效的 CODEX_THREAD_ID')
        if thread_id != self.caller_thread_id:
            raise TitleError('只能更新调用者自己的会话，不能指定其他会话')
        normalize_title(topic, status, progress)
        if not in_scope(self.root, cwd):
            raise TitleError('只能从本测试项目内更新标题')
        config = installation(self.root)
        if not config or not config['enabled']:
            return {'result': 'disabled', 'reason': '本项目尚未启用标题适配'}
        directory = self.root / '.local' / 'titles'
        if (self.root / '.local').is_symlink() or directory.is_symlink():
            raise TitleError('本地状态目录不能是符号链接')
        directory.mkdir(parents=True, exist_ok=True)
        state_path = directory / f'{thread_id}.json'
        with locked(directory / f'{thread_id}.lock'):
            thread = self._read_thread(thread_id)
            if is_global(self.root) and Path(thread['cwd']).resolve() != Path(cwd).resolve():
                raise TitleError('调用目录与当前会话目录不一致，未改名')
            created = thread.get('createdAt')
            if type(created) not in (int, float) or created < config['created_after']:
                return {'result': 'out_of_scope', 'reason': '只管理安装后新建的根会话'}
            current = thread.get('name') or ''
            state = {'version': 2, 'topic': topic.strip(), 'last_applied': None, 'paused': False,
                     'segment_protection_active': False, 'locked_segments': ['initial_request']}
            existing = parse_three_part_title(current) if is_global(self.root) else None
            if existing:
                state['topic'] = existing[2][1]
            own = read_title_state(state_path)
            if own is not None:
                state = own
            peer_path = peer_state_path(self.root, cwd, thread_id)
            if peer_path is not None:
                with locked(peer_path.parent.parent / 'title-installation.lock'):
                    peer = read_title_state(peer_path)
                if peer is not None and (own is None or peer.get('revision', 0) > state.get('revision', 0)):
                    state = peer
            if own is not None or peer_path is not None:
                try:
                    if (not isinstance(state, dict) or type(state.get('version')) is not int
                            or state['version'] not in (1, 2) or not isinstance(state['topic'], str)
                            or not isinstance(state['paused'], bool)
                            or state['last_applied'] is not None
                            and not isinstance(state['last_applied'], str)):
                        raise ValueError('invalid state fields')
                except (ValueError, KeyError) as error:
                    raise TitleError('状态文件损坏，停止自动改名') from error
            if state['version'] == 1:
                state.update(version=2, segment_protection_active=False, locked_segments=['initial_request'])
            if (type(state.get('segment_protection_active')) is not bool
                    or not isinstance(state.get('locked_segments'), list)
                    or any(v not in TITLE_SEGMENTS for v in state['locked_segments'])):
                raise TitleError('标题分段保护记录损坏')
            pending = state.get('pending')
            if 'pending' in state:
                if (not isinstance(pending, dict) or set(pending) != {'expected', 'desired'}
                        or not all(isinstance(value, str) for value in pending.values())):
                    raise TitleError('待确认的改名记录损坏')
                if current == pending['desired']:
                    state['last_applied'] = current
                    state.pop('pending')
                    save_title_state(state_path, state)
                elif current != pending['expected']:
                    state['paused'] = True
                else:
                    return {'result': 'pending', 'title': current,
                            'reason': '上次请求是否生效尚不确定，暂不提交新改名请求'}
            elif state['last_applied'] is not None and current != state['last_applied']:
                expected = parse_three_part_title(state['last_applied'])
                observed = parse_three_part_title(current)
                if (state['segment_protection_active'] and expected and observed
                        and expected[0] == observed[0]):
                    # Adapted from upstream reconcile_visible_title: lock only edited segments.
                    locked_parts = set(state['locked_segments'])
                    for field, old, new in zip(TITLE_SEGMENTS, expected[2], observed[2]):
                        if old != new:
                            locked_parts.add(field)
                    state['locked_segments'] = [f for f in TITLE_SEGMENTS if f in locked_parts]
                    state['last_applied'] = current
                    state['paused'] = False
                else:
                    state['paused'] = True
            if state['paused']:
                save_title_state(state_path, state)
                return {'result': 'paused', 'title': current}
            # Preserve valid initial requests from the v1 format (up to 48 chars).
            desired = normalize_title(state['topic'], status, progress, topic_limit=48)
            desired = merge_protected_title(state, current, desired)
            if not desired:
                raise TitleError('无法安全合并标题分段')
            if desired == current:
                state['last_applied'] = desired
                state['segment_protection_active'] = True
                state['checked_at_ns'] = time.time_ns()
                state['checked_turn_id'] = turn_id
                state.pop('pending', None)
                save_title_state(state_path, state)
                return {'result': 'unchanged', 'title': desired}
            state['pending'] = {'expected': current, 'desired': desired}
            save_title_state(state_path, state)
            self.rpc.request('thread/name/set', {'threadId': thread_id, 'name': desired})
            if self._read_thread(thread_id).get('name') != desired:
                raise TitleError('改名请求已提交，但回读未匹配；保留待确认记录')
            state['last_applied'] = desired
            state['segment_protection_active'] = True
            state['checked_at_ns'] = time.time_ns()
            state['checked_turn_id'] = turn_id
            state.pop('pending')
            save_title_state(state_path, state)
            return {'result': 'updated', 'title': desired}


def hook_output(root, payload):
    if not isinstance(payload, dict) or not in_scope(root, payload.get('cwd')):
        return {}
    event = payload.get('hook_event_name')
    if event not in {'SessionStart', 'UserPromptSubmit'}:
        return {}
    if event == 'SessionStart' and payload.get('source') not in {'startup', 'resume', 'compact'}:
        return {}
    command = f'python3 {shlex.quote(str(root / "scripts/session_title.py"))} set'
    context = (
        '本测试项目采用“状态｜初始需求｜当前进展”。仅当前新建根会话在开始处理任务、'
        '任务状态确实改变时调用：' + command + ' --topic "初始需求" --status "状态" --progress "当前进展"。'
        '脚本从 CODEX_THREAD_ID 读取当前会话。状态可用：' + '、'.join(STATUSES) + '。'
        '只接管项目启用后新建的根会话，可替换其初始默认标题；后续主题保持稳定。回合结束不代表任务已完成。'
        '若返回 paused、disabled、out_of_scope、pending 或调用失败，保留标题并继续用户任务，不反复重试或修改全局配置。'
    )
    return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': context}}


def build_hooks(root):
    command = f'{shlex.quote(sys.executable)} {shlex.quote(str(root.resolve() / "scripts/session_title.py"))} hook'
    handler = {'hooks': [{'type': 'command', 'command': command, 'timeout': 5}]}
    return {'description': 'Agent Clarity: generated project-only reminders',
            'hooks': {'SessionStart': [{'matcher': '^(startup|resume|compact)$', **handler}],
                      'UserPromptSubmit': [handler]}}


def main(default_root=None):
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--project', type=Path, help='明确启用的项目根目录')
    scope.add_argument('--global', dest='global_mode', action='store_true', help='当前 Codex 账户所有目录')
    sub = parser.add_subparsers(dest='command', required=True)
    update = sub.add_parser('set')
    update.add_argument('--topic', required=True)
    update.add_argument('--status', choices=STATUSES, required=True)
    update.add_argument('--progress', required=True)
    sub.add_parser('hook')
    sub.add_parser('setup-hooks')
    sub.add_parser('activate')
    sub.add_parser('deactivate')
    args = parser.parse_args()
    try:
        ROOT = global_root() if args.global_mode else (args.project or default_root or resolve_scope(Path.cwd()))
        if ROOT is None:
            print(json.dumps({'result': 'disabled'}))
            return 0
        ROOT = Path(ROOT).resolve()
        if not in_scope(ROOT, Path.cwd()):
            raise TitleError('调用目录不属于指定项目')
        if args.command == 'activate':
            print(json.dumps({'result': 'activated', **activate(ROOT, global_mode=args.global_mode)}, ensure_ascii=False))
        elif args.command == 'deactivate':
            directory = state_directory(ROOT)
            with scope_locked(), locked(directory / 'title-installation.lock'):
                value = installation(ROOT)
                if value:
                    value['enabled'] = False
                    write_json(directory / 'title-installation.json', value)
            print(json.dumps({'result': 'deactivated'}, ensure_ascii=False))
        elif args.command == 'setup-hooks':
            destination = ROOT / '.codex/hooks.json'
            if destination.parent.is_symlink() or destination.is_symlink():
                raise TitleError('钩子配置不能通过符号链接写入')
            config = build_hooks(ROOT)
            if destination.exists() and json.loads(destination.read_text()) != config:
                raise TitleError('已有不同的钩子配置，未覆盖；请先检查 .codex/hooks.json')
            destination.parent.mkdir(exist_ok=True)
            write_json(destination, config)
            print(json.dumps({'result': 'configured', 'path': str(destination),
                              'trust': '仍须通过 Codex /hooks 审查'}, ensure_ascii=False))
        elif args.command == 'hook':
            print(json.dumps(hook_output(ROOT, json.load(sys.stdin)), ensure_ascii=False))
        else:
            if not in_scope(ROOT, Path.cwd()):
                raise TitleError('调用目录不属于本项目')
            config = installation(ROOT)
            if not config or not config['enabled']:
                print(json.dumps({'result': 'disabled'}))
                return 0
            thread_id = os.environ.get('CODEX_THREAD_ID')
            if not ID.fullmatch(thread_id or ''):
                raise TitleError('缺少有效的 CODEX_THREAD_ID')
            with CodexRPC(cwd=Path.cwd(), local_only=True) as rpc:
                result = TitleManager(ROOT, rpc, caller_thread_id=thread_id).set(
                    thread_id, args.topic, args.status, Path.cwd(), progress=args.progress)
                result['transport'] = rpc.transport
                print(json.dumps(result, ensure_ascii=False))
        return 0
    except (TitleError, RPCError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({'result': 'error', 'message': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
