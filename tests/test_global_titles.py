"""Global scope tests use temporary homes and a fake API, never the user's config."""
import json
import os
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import contextmanager
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from title_plugin import Installer, InstallError
from title_runtime import TitleManager, TitleError, activate, global_root, resolve_scope, installation
from title_guard import guard
from test_titles import FakeRPC


class GlobalTitlesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        binding = patch('title_runtime.GLOBAL_BINDING', self.base / 'unbound-source.json')
        binding.start()
        self.addCleanup(binding.stop)
        self.home = self.base / 'codex home'; self.home.mkdir()
        self.env = patch.dict(os.environ, {'CODEX_HOME': str(self.home)})
        self.env.start()
        self.root = global_root()
        self.cwd = self.base / 'plain folder'; self.cwd.mkdir()
        self.project = self.base / 'git project'; self.project.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        self.manager = Installer(global_mode=True)

    def tearDown(self):
        self.env.stop(); self.temp.cleanup()

    def configure(self):
        return self.manager.configure()

    def test_global_install_and_uninstall_preserve_other_settings_and_rules(self):
        config = self.home / 'config.toml'; config.write_text('model = "existing"\n')
        agents = self.home / 'AGENTS.md'; agents.write_text('Existing instructions.\n')
        record = self.configure()
        self.assertEqual(record['scope'], 'global')
        self.assertTrue(tomllib.loads(config.read_text())['plugins'][record['plugin_id']]['enabled'])
        self.assertIn('状态｜初始需求｜当前进展', agents.read_text())
        agents.write_text(agents.read_text() + 'Later user edit.\n')
        self.manager.uninstall()
        self.assertEqual(tomllib.loads(config.read_text()), {'model': 'existing'})
        self.assertIn('Existing instructions.', agents.read_text())
        self.assertIn('Later user edit.', agents.read_text())
        self.assertNotIn('agent-clarity-titles:start', agents.read_text())
        self.assertFalse(installation(self.root)['enabled'])
        self.assertFalse((self.cwd / '.local').exists())
        self.assertFalse((self.project / 'AGENTS.md').exists())

    def test_global_install_uses_existing_override_rules_file(self):
        override = self.home / 'AGENTS.override.md'; override.write_text('Override instructions.\n')
        self.manager = Installer(global_mode=True)
        self.configure()
        self.assertIn('agent-clarity-titles:start', override.read_text())
        self.assertFalse((self.home / 'AGENTS.md').exists())

    def test_global_symlink_config_is_rejected_before_any_overwrite(self):
        outside = self.base / 'outside'; outside.write_text('original')
        (self.home / 'config.toml').symlink_to(outside)
        with self.assertRaises(InstallError): self.configure()
        self.assertEqual(outside.read_text(), 'original')
        self.assertFalse((self.home / 'AGENTS.md').exists())

    def test_global_applies_to_non_git_and_nested_repositories(self):
        self.configure()
        nested = self.project / 'reference/nested'; nested.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(nested)], check=True)
        for index, cwd in enumerate((self.cwd, self.project, nested)):
            with self.subTest(cwd=cwd):
                self.assertEqual(resolve_scope(cwd), self.root)
                rpc = FakeRPC(cwd)
                thread_id = f'test-thread-{index}'
                rpc.thread['id'] = thread_id
                result = TitleManager(self.root, rpc, caller_thread_id=thread_id).set(
                    thread_id, '缓存解释', '已完成', cwd, progress='说明缓存机制')
                self.assertEqual(result['result'], 'updated')
                self.assertEqual(rpc.thread['name'], '已完成｜缓存解释｜说明缓存机制')
        self.assertFalse((self.cwd / '.local').exists())

    def test_older_chat_and_user_fork_are_eligible_in_global_mode(self):
        self.configure()
        rpc = FakeRPC(self.cwd)
        rpc.thread.update(createdAt=1, forkedFromId='parent')
        result = TitleManager(self.root, rpc, caller_thread_id='test-thread').set(
            'test-thread', '既有问题', '实现中', self.cwd, progress='继续处理原任务')
        self.assertEqual(result['result'], 'updated')

    def test_subagent_and_mismatched_caller_directory_still_rejected(self):
        self.configure(); rpc = FakeRPC(self.cwd)
        m = TitleManager(self.root, rpc, caller_thread_id='test-thread')
        rpc.thread['source'] = {'subAgent': {'thread_spawn': {}}}
        with self.assertRaises(TitleError):
            m.set('test-thread', '任务', '讨论中', self.cwd, progress='了解任务')
        rpc.thread.pop('source')
        with self.assertRaises(TitleError):
            m.set('test-thread', '任务', '讨论中', self.project, progress='了解任务')
        self.assertEqual(rpc.writes, [])

    def test_first_global_adoption_keeps_existing_three_part_topic(self):
        self.configure(); rpc = FakeRPC(self.cwd)
        rpc.thread['name'] = '讨论中｜原始需求｜旧进展'
        result = TitleManager(self.root, rpc, caller_thread_id='test-thread').set(
            'test-thread', '临时说法', '实现中', self.cwd, progress='正在完成修改')
        self.assertEqual(result['title'], '实现中｜原始需求｜正在完成修改')

    def test_global_hook_checks_and_repairs_non_git_chat_once(self):
        self.configure(); rpc = FakeRPC(self.cwd)
        payload = {'cwd': str(self.cwd), 'session_id': 'test-thread', 'turn_id': 'turn-1',
                   'hook_event_name': 'UserPromptSubmit'}
        result = guard(self.root, payload, rpc)
        self.assertIn('--global', result['hookSpecificOutput']['additionalContext'])
        payload['hook_event_name'] = 'Stop'
        self.assertEqual(guard(self.root, payload, rpc)['decision'], 'block')
        self.assertEqual(guard(self.root, payload, rpc), {})

    def test_project_writer_is_inactive_while_global_is_enabled(self):
        activate(self.project, now=100)
        self.configure(); rpc = FakeRPC(self.project)
        result = TitleManager(self.project, rpc, caller_thread_id='test-thread').set(
            'test-thread', '任务', '实现中', self.project, progress='完成修改')
        self.assertEqual(result['result'], 'disabled')
        payload = {'cwd': str(self.project), 'session_id': 'test-thread', 'turn_id': 'turn-1',
                   'hook_event_name': 'UserPromptSubmit'}
        self.assertEqual(guard(self.project, payload, rpc), {})
        self.manager.uninstall()
        self.assertEqual(resolve_scope(self.project), self.project.resolve())
        result = TitleManager(self.project, rpc, caller_thread_id='test-thread').set(
            'test-thread', '任务', '实现中', self.project, progress='完成修改')
        self.assertEqual(result['result'], 'updated')

    def test_project_cannot_forge_a_global_activation(self):
        with self.assertRaises(TitleError): activate(self.project, global_mode=True, now=100)
        self.assertFalse((self.project / '.local/title-installation.json').exists())

    def test_another_codex_home_does_not_share_global_activation(self):
        self.configure()
        other = self.base / 'other home'; other.mkdir()
        with patch.dict(os.environ, {'CODEX_HOME': str(other)}):
            self.assertIsNone(resolve_scope(self.cwd))

    def test_project_transition_keeps_manual_protection_and_removes_duplicate_install(self):
        local = Installer(self.project); local.configure()
        rpc = FakeRPC(self.project)
        rpc.thread['createdAt'] = int(time.time()) + 1
        m = TitleManager(self.project, rpc, caller_thread_id='test-thread')
        m.set('test-thread', '原需求', '讨论中', self.project, progress='澄清需求')
        rpc.thread['name'] = '我的手动收藏'
        self.assertEqual(m.set('test-thread', '原需求', '实现中', self.project,
                              progress='实现修改')['result'], 'paused')
        self.configure()
        result = self.manager.replace_project(self.project)
        self.assertEqual(result['migrated_states'], 1)
        self.assertFalse(installation(self.project)['enabled'])
        self.assertNotIn(local.plugin_id, (self.project / '.codex/config.toml').read_text())
        result = TitleManager(self.root, rpc, caller_thread_id='test-thread').set(
            'test-thread', '临时名', '已完成', self.project, progress='完成修改')
        self.assertEqual(result['result'], 'paused')
        self.assertEqual(rpc.thread['name'], '我的手动收藏')

    def test_transition_does_not_overwrite_different_global_protection(self):
        local = Installer(self.project); local.configure()
        self.configure()
        for root, topic in ((self.project, '项目记录'), (self.root, '全局记录')):
            folder = root / '.local/titles'; folder.mkdir()
            (folder / 'test-thread.json').write_text(json.dumps({'version': 2, 'topic': topic,
                'last_applied': None, 'paused': True, 'segment_protection_active': False,
                'locked_segments': ['initial_request']}))
        before = (self.root / '.local/titles/test-thread.json').read_bytes()
        with self.assertRaises(InstallError): self.manager.replace_project(self.project)
        self.assertEqual((self.root / '.local/titles/test-thread.json').read_bytes(), before)
        self.assertTrue(installation(self.project)['enabled'])

    def test_migration_rejects_title_state_symlinks(self):
        Installer(self.project).configure(); self.configure()
        outside = self.base / 'outside.json'; outside.write_text('{}')
        folder = self.project / '.local/titles'; folder.mkdir()
        (folder / 'test-thread.json').symlink_to(outside)
        with self.assertRaises(InstallError): self.manager.replace_project(self.project)
        self.assertEqual(outside.read_text(), '{}')
        self.assertTrue(installation(self.project)['enabled'])

    def test_default_global_adoption_inherits_project_manual_protection(self):
        activate(self.project, now=100); rpc = FakeRPC(self.project)
        local = TitleManager(self.project, rpc, caller_thread_id='test-thread')
        local.set('test-thread', '原需求', '讨论中', self.project, progress='澄清需求')
        rpc.thread['name'] = '我的收藏'
        local.set('test-thread', '原需求', '实现中', self.project, progress='准备实现')
        self.configure()
        result = TitleManager(self.root, rpc, caller_thread_id='test-thread').set(
            'test-thread', '新提议', '已完成', self.project, progress='完成修改')
        self.assertEqual(result['result'], 'paused')
        self.assertEqual(rpc.thread['name'], '我的收藏')

    def test_project_can_resume_after_global_uninstall_without_locking_automatic_changes(self):
        activate(self.project, now=100); rpc = FakeRPC(self.project)
        local = TitleManager(self.project, rpc, caller_thread_id='test-thread')
        local.set('test-thread', '原需求', '讨论中', self.project, progress='澄清需求')
        self.configure()
        TitleManager(self.root, rpc, caller_thread_id='test-thread').set(
            'test-thread', '原需求', '实现中', self.project, progress='实现功能')
        self.manager.uninstall()
        result = local.set('test-thread', '原需求', '已完成', self.project, progress='完成修改')
        self.assertEqual(result['title'], '已完成｜原需求｜完成修改')
        state = json.loads((self.project / '.local/titles/test-thread.json').read_text())
        self.assertEqual(state['locked_segments'], ['initial_request'])

    def test_global_enable_waits_for_inflight_project_write(self):
        activate(self.project, now=100); rpc = FakeRPC(self.project)
        reading, release, enabling = threading.Event(), threading.Event(), threading.Event()
        original = rpc.request
        errors = []
        def request(method, params):
            if method == 'thread/read' and not reading.is_set():
                reading.set()
                if not release.wait(5): raise AssertionError('test did not release old write')
            return original(method, params)
        rpc.request = request
        def write():
            try:
                TitleManager(self.project, rpc, caller_thread_id='test-thread').set(
                    'test-thread', '原需求', '实现中', self.project, progress='旧项目进展')
            except Exception as error: errors.append(error)
        def enable():
            try:
                self.configure(); enabling.set()
            except Exception as error: errors.append(error)
        writer = threading.Thread(target=write); writer.start()
        self.assertTrue(reading.wait(2))
        installer = threading.Thread(target=enable); installer.start()
        # Activation must not finish while an old writer can still submit a title.
        try: self.assertFalse(enabling.wait(0.2))
        finally: release.set(); writer.join(5); installer.join(5)
        self.assertEqual(errors, [])
        self.assertTrue(enabling.is_set())
        result = TitleManager(self.root, rpc, caller_thread_id='test-thread').set(
            'test-thread', '原需求', '已完成', self.project, progress='全局新进展')
        self.assertEqual(result['title'], '已完成｜原需求｜全局新进展')

    def test_global_uninstall_cleans_original_rules_after_override_appears(self):
        self.configure()
        original = self.home / 'AGENTS.md'
        override = self.home / 'AGENTS.override.md'; override.write_text('New override rules.\n')
        Installer(global_mode=True).uninstall()
        self.assertNotIn('agent-clarity-titles:start', original.read_text())
        self.assertEqual(override.read_text(), 'New override rules.\n')

    def test_transition_keeps_newer_global_protection_then_removes_project_package(self):
        Installer(self.project).configure(); rpc = FakeRPC(self.project)
        rpc.thread['createdAt'] = int(time.time()) + 1
        TitleManager(self.project, rpc, caller_thread_id='test-thread').set(
            'test-thread', '原需求', '讨论中', self.project, progress='澄清需求')
        self.configure()
        TitleManager(self.root, rpc, caller_thread_id='test-thread').set(
            'test-thread', '原需求', '已完成', self.project, progress='完成修改')
        path = self.root / '.local/titles/test-thread.json'; before = path.read_bytes()
        result = self.manager.replace_project(self.project)
        self.assertEqual(result['result'], 'uninstalled')
        self.assertEqual(result['kept_newer_global_states'], 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(installation(self.project)['enabled'])

    def test_transition_rechecks_global_activation_after_waiting_for_scope_lock(self):
        Installer(self.project).configure(); self.configure()
        original = installation
        once = [True]
        def uninstall_after_initial_read(root):
            active = original(root)
            if Path(root) == self.root and once[0]:
                once[0] = False
                self.manager.uninstall()
            return active
        with patch('title_plugin.installation', side_effect=uninstall_after_initial_read):
            with self.assertRaises(InstallError): self.manager.replace_project(self.project)
        self.assertTrue(installation(self.project)['enabled'])


if __name__ == '__main__': unittest.main()
