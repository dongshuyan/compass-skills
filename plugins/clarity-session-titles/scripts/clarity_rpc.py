"""Small JSONL client for the installed Codex CLI; no database writes."""
from __future__ import annotations

import json
from collections import deque
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import time


class RPCError(RuntimeError):
    def __init__(self, message, detail=None):
        super().__init__(message)
        self.detail = detail


class CodexRPC:
    def __init__(self, *, command=None, cwd=None, timeout=12, local_only=False):
        self.command = command
        self.cwd = cwd
        self.timeout = timeout
        self.local_only = local_only
        self.process = None
        self.stderr = None
        self.buffer = b''
        self.sequence = 0
        self.transport = 'custom'
        self.events = deque()

    def __enter__(self):
        if self.command is not None:
            candidates = [('custom', self.command)]
        else:
            # Metadata-only calls work without model authentication. Harbor's
            # model wrapper can require a login even for app-server startup.
            native = shutil.which('codex')
            cli = (native if self.local_only else None) or os.environ.get('CODEX_CLI_PATH') or native
            if not cli:
                raise RPCError('找不到 codex 命令')
            home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
            sock = home / 'app-server-control/app-server-control.sock'
            candidates = []
            if sock.exists():
                candidates.append(('control-socket', [cli, 'app-server', 'proxy',
                                                       '--sock', str(sock.resolve())]))
            candidates.append(('stdio', [cli, 'app-server', '--stdio']))
        for transport, command in candidates:
            try:
                self.stderr = tempfile.TemporaryFile()
                self.process = subprocess.Popen(command, cwd=self.cwd, stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE, stderr=self.stderr)
                self.buffer = b''
                self.events.clear()
                self.transport = transport
                self.request('initialize', {'clientInfo': {'name': 'agent-clarity',
                                                           'version': '0.1.0'}})
                self._send({'method': 'initialized'})
                return self
            except (OSError, RPCError):
                self.close()
        raise RPCError('Codex app-server 初始化失败；没有执行改名')

    def _send(self, value):
        try:
            self.process.stdin.write((json.dumps(value, ensure_ascii=False) + '\n').encode())
            self.process.stdin.flush()
        except (OSError, ValueError) as error:
            raise RPCError('Codex 连接已关闭') from error

    def _line(self, deadline):
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                raise RPCError('Codex API 超时；写操作的结果需重新读取确认')
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise RPCError('Codex app-server 已退出')
            self.buffer += chunk
            if len(self.buffer) > 4 * 1024 * 1024:
                raise RPCError('Codex API 响应超过大小限制')
        line, self.buffer = self.buffer.split(b'\n', 1)
        return line

    def request(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        self._send({'id': request_id, 'method': method, 'params': params})
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                response = json.loads(self._line(deadline))
            except (ValueError, UnicodeError) as error:
                raise RPCError('Codex 返回了无效 JSON') from error
            if not isinstance(response, dict):
                raise RPCError('Codex 返回了无效消息')
            if response.get('id') != request_id or 'method' in response:
                if len(self.events) >= 2000:
                    raise RPCError('Codex 通知过多，停止以免丢失事件')
                self.events.append(response)
                continue
            if 'error' in response or 'result' not in response:
                raise RPCError(f'Codex API 拒绝 {method}', response.get('error'))
            return response['result']
        raise RPCError('Codex API 超时')

    def next_event(self, *, timeout=60):
        if self.events:
            return self.events.popleft()
        try:
            event = json.loads(self._line(time.monotonic() + timeout))
        except (ValueError, UnicodeError) as error:
            raise RPCError('Codex 返回了无效 JSON') from error
        if not isinstance(event, dict):
            raise RPCError('Codex 返回了无效消息')
        return event

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            for stream in (self.process.stdin, self.process.stdout):
                if stream:
                    stream.close()
            self.process = None
        if self.stderr is not None:
            self.stderr.close()
            self.stderr = None

    def __exit__(self, *_):
        self.close()
