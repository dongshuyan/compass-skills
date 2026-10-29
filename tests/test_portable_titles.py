"""Portable title state uses temporary homes and FakeRPC, never live chats."""
import hashlib
from contextlib import nullcontext
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1] / 'plugins/clarity-session-titles'
sys.path.insert(0, str(PLUGIN / 'scripts'))
import title_guard
import title_runtime
from test_titles import FakeRPC


class PortableTitlesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.first_home = self.base / 'original home'
        self.second_home = self.base / 'Harbor home'
        for home in (self.first_home, self.second_home):
            home.mkdir()
        self.root = self.first_home / 'agent-clarity'
        self.root.mkdir()
        self.cwd = self.base / 'ordinary folder'
        self.cwd.mkdir()
        self.package = self.base / 'installed plugin'
        shutil.copytree(PLUGIN, self.package,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc',
                                                     'global-installation.json'))
        self.binding = self.package / 'global-installation.json'
        environment = patch.dict(os.environ, {'CODEX_HOME': str(self.first_home)})
        environment.start()
        self.addCleanup(environment.stop)
        binding = patch.object(title_runtime, 'GLOBAL_BINDING', self.binding, create=True)
        binding.start()
        self.addCleanup(binding.stop)

    def bind(self):
        self.binding.write_text(json.dumps({'version': 1, 'root': str(self.root)}))

    def activate(self):
        title_runtime.activate(self.root, now=100, global_mode=True)
        self.bind()

    def manager(self, rpc):
        return title_runtime.TitleManager(title_runtime.global_root(), rpc,
                                          caller_thread_id=rpc.thread['id'])

    def state(self, rpc):
        return json.loads((self.root / '.local/titles' / (rpc.thread['id'] + '.json')).read_text())

    def test_unbound_plugin_remains_home_scoped(self):
        title_runtime.activate(self.root, now=100, global_mode=True)
        self.assertEqual(title_runtime.resolve_scope(self.cwd), self.root)
        with patch.dict(os.environ, {'CODEX_HOME': str(self.second_home)}):
            self.assertEqual(title_runtime.global_root(), self.second_home / 'agent-clarity')
            self.assertIsNone(title_runtime.resolve_scope(self.cwd))

    def test_invalid_binding_is_rejected_instead_of_using_home_fallback(self):
        alias = self.base / 'linked state'
        alias.symlink_to(self.root, target_is_directory=True)
        invalid = {
            'broken JSON': '{',
            'non-object': '[]',
            'wrong version': json.dumps({'version': 2, 'root': str(self.root)}),
            'relative root': json.dumps({'version': 1, 'root': 'agent-clarity'}),
            'symlink root': json.dumps({'version': 1, 'root': str(alias)}),
        }
        for description, content in invalid.items():
            with self.subTest(binding=description):
                self.binding.write_text(content)
                with self.assertRaises(title_runtime.TitleError):
                    title_runtime.global_root()

    def test_binding_does_not_enable_missing_or_disabled_shared_activation(self):
        local_root = self.second_home / 'agent-clarity'
        local_root.mkdir()
        with patch.dict(os.environ, {'CODEX_HOME': str(self.second_home)}):
            title_runtime.activate(local_root, now=100, global_mode=True)
        self.bind()
        rpc = FakeRPC(self.cwd)
        for enabled in (None, False):
            with self.subTest(shared_activation=enabled):
                if enabled is False:
                    title_runtime.activate(self.root, now=100, global_mode=True)
                    activation_path = self.root / '.local/title-installation.json'
                    activation = json.loads(activation_path.read_text())
                    activation['enabled'] = False
                    activation_path.write_text(json.dumps(activation))
                with patch.dict(os.environ, {'CODEX_HOME': str(self.second_home)}):
                    self.assertEqual(title_runtime.global_root(), self.root)
                    self.assertIsNone(title_runtime.resolve_scope(self.cwd))
                    result = self.manager(rpc).set('test-thread', '原始需求', '实现中',
                                                   self.cwd, progress='处理任务')
                    self.assertEqual(result['result'], 'disabled')
                    payload = {'cwd': str(self.cwd), 'session_id': 'test-thread',
                               'turn_id': 'turn-1', 'hook_event_name': 'UserPromptSubmit'}
                    self.assertEqual(title_guard.guard(self.root, payload, rpc), {})
        self.assertEqual(rpc.writes, [])

    def test_old_and_new_threads_share_records_across_home_changes(self):
        self.activate()
        for thread_id, created_at in (('old-thread', 1), ('new-thread', 300)):
            with self.subTest(thread_id=thread_id):
                rpc = FakeRPC(self.cwd)
                rpc.thread.update(id=thread_id, createdAt=created_at)
                first = self.manager(rpc).set(thread_id, '原始需求', '讨论中', self.cwd,
                                               progress='明确任务')
                self.assertEqual(first['result'], 'updated')
                with patch.dict(os.environ, {'CODEX_HOME': str(self.second_home)}):
                    self.assertEqual(title_runtime.resolve_scope(self.cwd), self.root)
                    moved = self.manager(rpc).set(thread_id, '后续提法', '实现中', self.cwd,
                                                  progress='完成实现')
                    self.assertEqual(moved['title'], '实现中｜原始需求｜完成实现')
                returned = self.manager(rpc).set(thread_id, '再次提法', '已完成', self.cwd,
                                                  progress='完成验证')
                self.assertEqual(returned['title'], '已完成｜原始需求｜完成验证')
                state = self.state(rpc)
                self.assertFalse(state['paused'])
                self.assertEqual(state['locked_segments'], ['initial_request'])
                self.assertEqual(state['last_applied'], returned['title'])
                self.assertEqual(len(rpc.writes), 3)
        self.assertFalse((self.second_home / 'agent-clarity').exists())

    def test_manual_title_and_segment_protection_survive_home_changes(self):
        self.activate()
        for thread_id, manual_title in (
                ('manual-title', '我的收藏'),
                ('manual-progress', '讨论中｜原始需求｜我手写的进展')):
            with self.subTest(thread_id=thread_id):
                rpc = FakeRPC(self.cwd)
                rpc.thread['id'] = thread_id
                self.manager(rpc).set(thread_id, '原始需求', '讨论中', self.cwd,
                                      progress='明确任务')
                rpc.thread['name'] = manual_title
                with patch.dict(os.environ, {'CODEX_HOME': str(self.second_home)}):
                    self.assertEqual(title_runtime.global_root(), self.root)
                    result = self.manager(rpc).set(thread_id, '后续提法', '实现中', self.cwd,
                                                   progress='自动更新进展')
                state = self.state(rpc)
                if thread_id == 'manual-title':
                    self.assertEqual(result['result'], 'paused')
                    self.assertEqual(rpc.thread['name'], manual_title)
                    self.assertTrue(state['paused'])
                    self.assertEqual(len(rpc.writes), 1)
                else:
                    self.assertEqual(result['title'], '实现中｜原始需求｜我手写的进展')
                    self.assertEqual(state['locked_segments'], ['initial_request', 'progress'])
                    resumed = self.manager(rpc).set(thread_id, '另一个提法', '已完成', self.cwd,
                                                    progress='另一条自动进展')
                    self.assertEqual(resumed['title'], '已完成｜原始需求｜我手写的进展')

    def test_prompt_and_stop_require_a_check_each_turn_after_home_change(self):
        self.activate()
        rpc = FakeRPC(self.cwd)
        rpc.thread['createdAt'] = 1
        for index, home in enumerate((self.first_home, self.second_home), start=1):
            with self.subTest(turn=index), patch.dict(os.environ, {'CODEX_HOME': str(home)}):
                root = title_runtime.resolve_scope(self.cwd)
                self.assertEqual(root, self.root)
                payload = {'cwd': str(self.cwd), 'session_id': 'test-thread',
                           'turn_id': f'turn-{index}', 'hook_event_name': 'UserPromptSubmit'}
                with patch('time.time_ns', return_value=index * 1_000):
                    prompt = title_guard.guard(root, payload, rpc)
                self.assertIn('--global', prompt['hookSpecificOutput']['additionalContext'])
                payload['hook_event_name'] = 'Stop'
                self.assertEqual(title_guard.guard(root, payload, rpc).get('decision'), 'block')
                self.assertEqual(title_guard.guard(root, payload, rpc), {})
                self.assertEqual(len(rpc.writes), min(index - 1, 1))
                with patch('time.time_ns', return_value=index * 1_000 + 100):
                    checked = self.manager(rpc).set('test-thread', '原始需求', '已完成',
                                                    self.cwd, progress='解释完成')
                self.assertEqual(checked['result'], 'updated' if index == 1 else 'unchanged')
                self.assertEqual(self.state(rpc)['checked_turn_id'], f'turn-{index}')
                self.assertEqual(title_guard.guard(root, payload, rpc), {})
        self.assertEqual(len(rpc.writes), 1)

    def test_hook_ownership_accepts_identical_copy_and_rejects_changed_files(self):
        self.activate()
        receipt = self.root / '.local/agent-clarity/plugin.json'
        receipt.parent.mkdir()
        files = {f'plugins/clarity-session-titles/{path.relative_to(self.package)}':
                 hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in self.package.rglob('*') if path.is_file()}
        receipt.write_text(json.dumps({'scope': 'global', 'enabled': True, 'files': files,
            'skill_path': str(self.package / 'skills/manage-title/SKILL.md')}))
        copied = self.second_home / 'plugins/cache/clarity-session-titles'
        shutil.copytree(self.package, copied)
        self.assertTrue(hasattr(title_guard, 'owns_global_hook'),
                        'Global hook ownership must support a verified copied package')
        self.assertTrue(title_guard.owns_global_hook(self.root, copied))
        rpc = FakeRPC(self.cwd)
        payload = {'cwd': str(self.cwd), 'session_id': 'test-thread',
                   'turn_id': 'copied-package-turn', 'hook_event_name': 'UserPromptSubmit'}
        with patch.dict(os.environ, {'CODEX_HOME': str(self.second_home)}), \
                patch.object(title_runtime, 'GLOBAL_BINDING', copied / self.binding.name), \
                patch.object(title_guard, '__file__', str(copied / 'scripts/title_guard.py')), \
                patch.object(title_guard, 'CodexRPC', return_value=nullcontext(rpc)), \
                patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                patch('sys.stdout', io.StringIO()) as output:
            self.assertEqual(title_guard.main(), 0)
        context = json.loads(output.getvalue())['hookSpecificOutput']['additionalContext']
        self.assertIn('--global', context)
        self.assertEqual(rpc.writes, [])
        for relative in ('scripts/title_guard.py', 'global-installation.json'):
            with self.subTest(changed=relative):
                path = copied / relative
                original = path.read_bytes()
                path.write_bytes(original + b'\n')
                self.assertFalse(title_guard.owns_global_hook(self.root, copied))
                path.write_bytes(original)

    def test_invalid_hook_receipt_fails_open_without_starting_rpc(self):
        self.activate()
        receipt = self.root / '.local/agent-clarity/plugin.json'
        receipt.parent.mkdir()
        payload = {'cwd': str(self.cwd), 'session_id': 'test-thread',
                   'turn_id': 'turn-1', 'hook_event_name': 'UserPromptSubmit'}
        invalid = (
            ('files list', {'files': []}, True),
            ('non-string digest', {'files': {
                'plugins/clarity-session-titles/global-installation.json': 123}}, True),
            ('short legacy skill path', {'skill_path': 'relative'}, False),
        )
        for description, fields, bound in invalid:
            with self.subTest(receipt=description):
                if bound:
                    self.bind()
                else:
                    self.binding.unlink()
                receipt.write_text(json.dumps({'scope': 'global', 'enabled': True, **fields}))
                with patch.object(title_guard, '__file__', str(self.package / 'scripts/title_guard.py')), \
                        patch.object(title_guard, 'CodexRPC',
                                     side_effect=AssertionError('Invalid receipts must not start RPC')), \
                        patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                        patch('sys.stdout', io.StringIO()) as output:
                    self.assertEqual(title_guard.main(), 0)
                self.assertEqual(json.loads(output.getvalue()), {})


if __name__ == '__main__':
    unittest.main()
