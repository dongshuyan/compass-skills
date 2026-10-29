import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from session_title import TitleManager, TitleError, hook_output, normalize_title, build_hooks, activate


class FakeRPC:
    """In-memory API double; these tests do not establish desktop behavior."""

    def __init__(self, cwd):
        self.thread = {'id': 'test-thread', 'cwd': str(cwd), 'name': None, 'createdAt': 200}
        self.writes = []
        self.lose_ack = False
        self.fail_write = False

    def request(self, method, params):
        if method == 'thread/read':
            return {'thread': dict(self.thread)}
        if method == 'thread/name/set':
            if self.fail_write:
                raise TitleError('unavailable')
            self.thread['name'] = params['name']
            self.writes.append(params.copy())
            if self.lose_ack:
                self.lose_ack = False
                raise TitleError('lost acknowledgement')
            return {}
        raise AssertionError(method)


class TitleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        binding = patch('title_runtime.GLOBAL_BINDING', Path(self.temp.name) / 'unbound-source.json')
        binding.start()
        self.addCleanup(binding.stop)
        self.env = patch.dict(os.environ, {'CODEX_HOME': str(Path(self.temp.name) / 'codex-home')})
        self.env.start()
        self.root = Path(self.temp.name).resolve() / 'project with spaces'
        self.root.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        activate(self.root, now=100)
        self.rpc = FakeRPC(self.root)
        self.manager = TitleManager(self.root, self.rpc, caller_thread_id='test-thread')

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def set_title(self, topic='登录超时修复', status='验证中', progress='检查重试逻辑'):
        return self.manager.set('test-thread', topic, status, self.root, progress=progress)

    def test_three_parts_and_duplicate_update_is_noop(self):
        self.assertEqual(self.set_title()['result'], 'updated')
        self.assertEqual(self.rpc.thread['name'], '验证中｜登录超时修复｜检查重试逻辑')
        self.assertEqual(self.set_title()['result'], 'unchanged')
        self.assertEqual(len(self.rpc.writes), 1)

    def test_fresh_session_default_name_is_replaced(self):
        self.rpc.thread['name'] = 'Codex 自动生成的初始名称'
        self.assertEqual(self.set_title()['title'], '验证中｜登录超时修复｜检查重试逻辑')

    def test_sessions_from_before_installation_are_not_taken_over(self):
        self.rpc.thread.update(name='已有会话', createdAt=99)
        self.assertEqual(self.set_title()['result'], 'out_of_scope')
        self.assertEqual(self.rpc.writes, [])

    def test_activation_is_idempotent_and_does_not_exclude_ongoing_sessions(self):
        self.assertEqual(activate(self.root, now=300)['created_after'], 100)
        self.assertEqual(self.set_title()['result'], 'updated')

    def test_reactivation_excludes_sessions_from_disabled_period(self):
        path = self.root / '.local/title-installation.json'
        config = json.loads(path.read_text()); config['enabled'] = False
        path.write_text(json.dumps(config))
        self.assertEqual(activate(self.root, now=300)['created_after'], 300)
        self.assertEqual(self.set_title()['result'], 'out_of_scope')

    def test_session_started_immediately_after_activation_is_in_scope(self):
        (self.root / '.local/title-installation.json').unlink()
        clock = [200.2]
        def advance(seconds):
            clock[0] += seconds
        with patch('session_title.time.time', side_effect=lambda: clock[0]), \
                patch('session_title.time.sleep', side_effect=advance):
            activate(self.root)
            self.rpc.thread['createdAt'] = int(clock[0])
        self.assertEqual(self.set_title()['result'], 'updated')

    def test_missing_or_disabled_installation_does_not_rename(self):
        path = self.root / '.local/title-installation.json'
        path.write_text(json.dumps({'version': 1, 'root': str(self.root),
                                    'enabled': False, 'created_after': 100}))
        self.assertEqual(self.set_title()['result'], 'disabled')
        path.unlink()
        self.assertEqual(self.set_title()['result'], 'disabled')
        self.assertEqual(self.rpc.writes, [])

    def test_child_cannot_select_parent_as_target(self):
        manager = TitleManager(self.root, self.rpc, caller_thread_id='child-thread')
        with self.assertRaises(TitleError):
            manager.set('test-thread', '主题', '讨论中', self.root, progress='了解需求')
        self.assertEqual(self.rpc.writes, [])

    def test_hook_command_is_bound_to_installation_not_caller_git_root(self):
        config = build_hooks(self.root)
        command = config['hooks']['UserPromptSubmit'][0]['hooks'][0]['command']
        self.assertNotIn('git rev-parse', command)
        self.assertIn(str(self.root / 'scripts/session_title.py'), command)

    def test_topic_stays_stable_as_status_changes(self):
        self.set_title()
        result = self.set_title('另一个临时叫法', '待验证')
        self.assertEqual(result['title'], '待验证｜登录超时修复｜检查重试逻辑')

    def test_manual_rename_pauses_future_updates(self):
        self.set_title()
        self.rpc.thread['name'] = '我自己取的标题'
        self.assertEqual(self.set_title(status='已完成')['result'], 'paused')
        self.assertEqual(self.set_title()['result'], 'paused')
        self.assertEqual(self.rpc.thread['name'], '我自己取的标题')
        self.assertEqual(len(self.rpc.writes), 1)

    def test_lost_ack_is_reconciled_without_duplicate_write(self):
        self.rpc.lose_ack = True
        with self.assertRaises(TitleError):
            self.set_title()
        self.assertEqual(self.set_title()['result'], 'unchanged')
        self.assertEqual(len(self.rpc.writes), 1)

    def test_unknown_write_outcome_is_not_retried_even_if_name_is_unchanged(self):
        self.rpc.fail_write = True
        with self.assertRaises(TitleError):
            self.set_title()
        self.rpc.fail_write = False
        self.assertEqual(self.set_title()['result'], 'pending')
        self.assertEqual(self.rpc.writes, [])

    def test_outside_thread_is_never_modified(self):
        self.rpc.thread['cwd'] = self.temp.name
        with self.assertRaises(TitleError):
            self.set_title()
        self.assertEqual(self.rpc.writes, [])

    def test_caller_outside_project_is_rejected(self):
        with self.assertRaises(TitleError):
            self.manager.set('test-thread', '主题', '讨论中', Path(self.temp.name), progress='了解需求')
        self.assertEqual(self.rpc.writes, [])

    def test_nested_reference_repository_is_out_of_scope(self):
        nested = self.root / 'reference' / 'sample'
        nested.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(nested)], check=True)
        self.rpc.thread['cwd'] = str(nested)
        with self.assertRaises(TitleError):
            self.set_title()

    def test_forks_and_subagents_are_rejected(self):
        for extra in ({'forkedFromId': 'parent'}, {'sessionId': 'parent'}, {'parentThreadId': 'parent'},
                      {'source': {'subAgent': {'thread_spawn': {}}}}):
            with self.subTest(extra=extra):
                self.rpc.thread.update(extra)
                with self.assertRaises(TitleError):
                    self.set_title()
                for key in extra:
                    self.rpc.thread.pop(key)
        self.assertEqual(self.rpc.writes, [])

    def test_path_traversal_thread_id_is_rejected(self):
        with self.assertRaises(TitleError):
            self.manager.set('../other', '主题', '讨论中', self.root, progress='了解需求')
        self.assertEqual(self.rpc.writes, [])

    def test_corrupt_state_fails_closed(self):
        self.set_title()
        (self.root / '.local/titles/test-thread.json').write_text('{')
        with self.assertRaises(TitleError):
            self.set_title(status='已完成')
        self.assertEqual(len(self.rpc.writes), 1)

    def test_empty_pending_record_is_corrupt_not_permission_to_write(self):
        self.set_title()
        path = self.root / '.local/titles/test-thread.json'
        state = json.loads(path.read_text())
        state['pending'] = {}
        path.write_text(json.dumps(state))
        with self.assertRaises(TitleError):
            self.set_title(status='已完成')
        self.assertEqual(len(self.rpc.writes), 1)

    def test_state_symlink_cannot_escape_project(self):
        (self.root / '.local').rename(self.root / '.local-original')
        (self.root / '.local').symlink_to(Path(self.temp.name))
        with self.assertRaises(TitleError):
            self.set_title()
        self.assertEqual(self.rpc.writes, [])

    def test_hook_only_adds_context_inside_project(self):
        payload = {'cwd': str(self.root), 'hook_event_name': 'UserPromptSubmit',
                   'prompt': 'secret material must not be echoed'}
        result = hook_output(self.root, payload)
        self.assertIn('additionalContext', result['hookSpecificOutput'])
        self.assertNotIn(payload['prompt'], json.dumps(result))
        payload['cwd'] = self.temp.name
        self.assertEqual(hook_output(self.root, payload), {})

    def test_hook_does_not_claim_fork_or_stop_means_task_done(self):
        self.assertEqual(hook_output(self.root, {'cwd': str(self.root),
                         'hook_event_name': 'SessionStart', 'source': 'fork'}), {})
        self.assertEqual(hook_output(self.root, {'cwd': str(self.root),
                         'hook_event_name': 'Stop'}), {})

    def test_invalid_titles_and_statuses_are_rejected(self):
        for topic, status in [('', '讨论中'), ('一｜二', '讨论中'), ('a\nb', '讨论中'),
                              ('主题', 'maybe'), ('x' * 61, '讨论中')]:
            with self.subTest(topic=topic, status=status), self.assertRaises(TitleError):
                normalize_title(topic, status, '检查结果')


    def test_progress_changes_without_changing_initial_request(self):
        self.set_title()
        result = self.set_title('临时话题', '实现中', '修复重试逻辑')
        self.assertEqual(result['title'], '实现中｜登录超时修复｜修复重试逻辑')

    def test_manually_edited_segment_is_locked_but_others_update(self):
        self.set_title()
        self.rpc.thread['name'] = '稍后再看｜登录超时修复｜检查重试逻辑'
        result = self.set_title(status='已完成', progress='修复并验证')
        self.assertEqual(result['title'], '稍后再看｜登录超时修复｜修复并验证')

    def test_manually_edited_request_and_progress_are_preserved(self):
        self.set_title()
        self.rpc.thread['name'] = '验证中｜我的登录问题｜保留这段进展'
        result = self.set_title(status='已完成', progress='准备交付')
        self.assertEqual(result['title'], '已完成｜我的登录问题｜保留这段进展')

    def test_old_two_part_state_migrates_on_next_update(self):
        self.set_title()
        path = self.root / '.local/titles/test-thread.json'
        old = {'version': 1, 'topic': '登录超时修复', 'last_applied': '登录超时修复｜验证中', 'paused': False}
        path.write_text(json.dumps(old)); self.rpc.thread['name'] = old['last_applied']
        self.assertEqual(self.set_title()['title'], '验证中｜登录超时修复｜检查重试逻辑')

    def test_old_long_initial_request_is_preserved_during_migration(self):
        self.set_title()
        topic = '甲' * 48
        path = self.root / '.local/titles/test-thread.json'
        old = {'version': 1, 'topic': topic, 'last_applied': topic + '｜验证中', 'paused': False}
        path.write_text(json.dumps(old)); self.rpc.thread['name'] = old['last_applied']
        self.assertEqual(self.set_title()['title'], '验证中｜' + topic + '｜检查重试逻辑')

    def test_invalid_progress_does_not_write_title(self):
        for progress in ('', 'a｜b', 'a\nb', 'x' * 61):
            with self.subTest(progress=progress), self.assertRaises(TitleError):
                self.set_title(progress=progress)
        self.assertEqual(self.rpc.writes, [])


if __name__ == '__main__':
    unittest.main()
