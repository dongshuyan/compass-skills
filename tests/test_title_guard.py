"""Local regression tests; FakeRPC results do not establish desktop hook behavior."""
import fcntl
from contextlib import contextmanager
import importlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


PLUGIN_SCRIPTS = Path(__file__).resolve().parents[1] / 'plugins/clarity-session-titles/scripts'
sys.path.insert(0, str(PLUGIN_SCRIPTS))
from title_runtime import TitleError, TitleManager, activate
from clarity_rpc import RPCError


class FakeRPC:
    """Keep the real manager's read/rename/read flow entirely in memory."""

    def __init__(self, cwd):
        self.thread = {'id': 'test-thread', 'cwd': str(cwd), 'name': None, 'createdAt': 200}
        self.writes = []
        self.fail_read = False
        self.fail_write = False

    def request(self, method, params):
        if method == 'thread/read':
            if self.fail_read:
                raise RPCError('app-server unavailable')
            return {'thread': dict(self.thread)}
        if method == 'thread/name/set':
            if self.fail_write:
                raise TitleError('write outcome unknown')
            self.thread['name'] = params['name']
            self.writes.append(params.copy())
            return {}
        raise AssertionError(method)


class ProjectFixture(unittest.TestCase):
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

    def set_title(self):
        return self.manager.set('test-thread', '一句话问答', '已完成', self.root,
                                progress='解释词语含义')

    def title_state(self):
        return json.loads((self.root / '.local/titles/test-thread.json').read_text())


class TitleCheckTimestampTests(ProjectFixture):
    def test_successful_update_records_the_check_time(self):
        with patch('time.time_ns', return_value=2_000):
            result = self.set_title()
        self.assertEqual(result['result'], 'updated')
        self.assertEqual(self.title_state().get('checked_at_ns'), 2_000)

    def test_successful_unchanged_result_refreshes_the_check_time(self):
        with patch('time.time_ns', return_value=1_000):
            self.set_title()
        with patch('time.time_ns', return_value=2_000):
            result = self.set_title()
        self.assertEqual(result['result'], 'unchanged')
        self.assertEqual(self.title_state().get('checked_at_ns'), 2_000)
        self.assertEqual(len(self.rpc.writes), 1)

    def test_uncertain_write_does_not_record_a_successful_check(self):
        self.rpc.fail_write = True
        with patch('time.time_ns', return_value=2_000), self.assertRaises(TitleError):
            self.set_title()
        self.assertNotIn('checked_at_ns', self.title_state())


class TitleGuardTests(ProjectFixture):
    def hook(self, event='UserPromptSubmit', **overrides):
        payload = {'hook_event_name': event, 'session_id': 'test-thread',
                   'cwd': str(self.root), 'turn_id': 'turn-1'}
        payload.update(overrides)
        return importlib.import_module('title_guard').guard(self.root, payload, self.rpc)

    def begin_turn(self, **overrides):
        with patch('time.time_ns', return_value=1_000):
            return self.hook(**overrides)

    def assert_not_triggered(self):
        self.assertEqual(self.begin_turn(), {})
        self.assertEqual(self.hook('Stop'), {})
        self.assertEqual(self.rpc.writes, [])
        self.assertFalse((self.root / '.local/title-turns/test-thread.json').exists())

    def test_short_prompt_gets_explicit_runtime_context_without_echoing_user_text(self):
        secret_prompt = 'unique private user question'
        result = self.begin_turn(prompt=secret_prompt)
        output = result['hookSpecificOutput']
        self.assertEqual(output['hookEventName'], 'UserPromptSubmit')
        context = output['additionalContext']
        self.assertIn('title_runtime.py', context)
        self.assertTrue(any(word in context for word in ('短问答', '短回答', '简短')))
        self.assertNotIn(secret_prompt, json.dumps(result))
        self.assertTrue((self.root / '.local/title-turns/test-thread.json').is_file())
        self.assertEqual(self.rpc.writes, [])

    def test_answer_without_a_title_check_requests_one_repair(self):
        self.begin_turn()
        result = self.hook('Stop')
        self.assertEqual(result.get('decision'), 'block')
        self.assertIn('title_runtime.py', result.get('reason', ''))
        self.assertEqual(self.rpc.writes, [])

    def test_stop_hook_active_prevents_repeated_continuation(self):
        self.begin_turn()
        self.assertEqual(self.hook('Stop').get('decision'), 'block')
        self.assertEqual(self.hook('Stop', stop_hook_active=True), {})
        self.assertEqual(self.rpc.writes, [])

    def test_stop_without_a_turn_baseline_does_not_block(self):
        self.assertEqual(self.hook('Stop'), {})
        self.assertFalse((self.root / '.local/title-turns/test-thread.json').exists())

    def test_stop_from_another_turn_cannot_block_the_current_turn(self):
        self.begin_turn()
        self.assertEqual(self.hook('Stop', turn_id='old-turn'), {})
        self.assertEqual(self.hook('Stop').get('decision'), 'block')

    def test_duplicate_prompt_event_preserves_an_already_completed_check(self):
        self.begin_turn()
        with patch('time.time_ns', return_value=2_000):
            self.set_title()
        with patch('time.time_ns', return_value=3_000):
            self.hook('UserPromptSubmit')
        self.assertEqual(self.hook('Stop'), {})

    def test_duplicate_prompt_does_not_request_the_same_repair_again(self):
        self.begin_turn()
        self.assertEqual(self.hook('Stop').get('decision'), 'block')
        with patch('time.time_ns', return_value=2_000):
            self.hook('UserPromptSubmit')
        self.assertEqual(self.hook('Stop'), {})

    def test_updated_title_in_this_turn_allows_the_answer_to_finish(self):
        self.begin_turn()
        with patch('time.time_ns', return_value=2_000):
            self.assertEqual(self.set_title()['result'], 'updated')
        self.assertEqual(self.hook('Stop'), {})

    def test_unchanged_title_in_this_turn_counts_as_a_successful_check(self):
        with patch('time.time_ns', return_value=500):
            self.set_title()
        self.begin_turn()
        with patch('time.time_ns', return_value=2_000):
            self.assertEqual(self.set_title()['result'], 'unchanged')
        self.assertEqual(self.hook('Stop'), {})
        self.assertEqual(len(self.rpc.writes), 1)

    def test_a_previous_turns_success_does_not_satisfy_the_current_turn(self):
        self.begin_turn()
        with patch('time.time_ns', return_value=2_000):
            self.set_title()
        self.assertEqual(self.hook('Stop'), {})
        with patch('time.time_ns', return_value=3_000):
            self.hook('UserPromptSubmit', turn_id='turn-2')
        self.assertEqual(self.hook('Stop', turn_id='turn-2').get('decision'), 'block')

    def test_old_call_finishing_after_next_prompt_cannot_check_the_new_turn(self):
        runtime = importlib.import_module('title_runtime')
        original_locked = runtime.locked
        installation_lock = runtime.global_root() / '.scope.lock'
        waiting_for_lock = threading.Event()
        continue_old_call = threading.Event()
        outcome = {}

        @contextmanager
        def pause_old_call_before_lock(path):
            if threading.current_thread() is old_call and Path(path) == installation_lock:
                waiting_for_lock.set()
                if not continue_old_call.wait(5):
                    raise AssertionError('old title call was not released')
            with original_locked(path):
                yield

        def run_old_call():
            try:
                outcome['result'] = self.set_title()
            except BaseException as error:
                outcome['error'] = error

        old_call = threading.Thread(target=run_old_call, daemon=True)
        # Equal clock readings ensure turn identity, rather than a timestamp,
        # determines which prompt this call can satisfy.
        with patch('time.time_ns', return_value=1_000), \
                patch.object(runtime, 'locked', side_effect=pause_old_call_before_lock):
            self.begin_turn()
            old_call.start()
            try:
                self.assertTrue(waiting_for_lock.wait(5), 'old call did not reach the lock')
                next_prompt = self.hook('UserPromptSubmit', turn_id='turn-2')
                self.assertIn('hookSpecificOutput', next_prompt)
            finally:
                continue_old_call.set()
                old_call.join(5)
            self.assertFalse(old_call.is_alive(), 'old title call did not finish')
            self.assertNotIn('error', outcome)
            self.assertEqual(outcome['result']['result'], 'updated')
            self.assertEqual(len(self.rpc.writes), 1)
            self.assertEqual(self.hook('Stop', turn_id='turn-2').get('decision'), 'block')

    def test_legacy_state_without_a_check_timestamp_needs_one_check(self):
        self.set_title()
        state = self.title_state()
        state.pop('checked_at_ns', None)
        path = self.root / '.local/titles/test-thread.json'
        path.write_text(json.dumps(state))
        self.begin_turn()
        self.assertEqual(self.hook('Stop').get('decision'), 'block')

    def test_paused_title_does_not_request_renaming(self):
        with patch('time.time_ns', return_value=500):
            self.set_title()
            self.rpc.thread['name'] = '保留我手动取的名字'
            self.assertEqual(self.set_title()['result'], 'paused')
        writes = list(self.rpc.writes)
        self.begin_turn()
        self.assertEqual(self.hook('Stop'), {})
        self.assertEqual(self.rpc.thread['name'], '保留我手动取的名字')
        self.assertEqual(self.rpc.writes, writes)

    def test_pending_title_does_not_request_another_write(self):
        self.rpc.fail_write = True
        with self.assertRaises(TitleError):
            self.set_title()
        self.rpc.fail_write = False
        self.assertEqual(self.set_title()['result'], 'pending')
        self.begin_turn()
        self.assertEqual(self.hook('Stop'), {})
        self.assertEqual(self.rpc.writes, [])

    def test_disabled_installation_does_not_trigger(self):
        path = self.root / '.local/title-installation.json'
        state = json.loads(path.read_text())
        state['enabled'] = False
        path.write_text(json.dumps(state))
        self.assert_not_triggered()

    def test_stop_cannot_request_repair_after_deactivation_completes(self):
        self.begin_turn()
        guard_module = importlib.import_module('title_guard')
        runtime = importlib.import_module('title_runtime')
        original_installation = guard_module.installation
        saw_enabled_installation = threading.Event()
        continue_stop = threading.Event()
        deactivation_completed = threading.Event()
        outcome = {}
        installation_lock = self.root / '.local/title-installation.lock'

        def pause_after_initial_installation_read(root):
            value = original_installation(root)
            if threading.current_thread() is stop_call and not saw_enabled_installation.is_set():
                outcome['initially_enabled'] = value['enabled']
                saw_enabled_installation.set()
                if not continue_stop.wait(5):
                    raise AssertionError('Stop call was not released')
            return value

        def run_stop():
            try:
                outcome['result'] = self.hook('Stop')
                outcome['returned_after_deactivation'] = deactivation_completed.is_set()
            except BaseException as error:
                outcome['error'] = error

        def deactivate_while_locked():
            state = runtime.installation(self.root)
            state['enabled'] = False
            runtime.write_json(self.root / '.local/title-installation.json', state)
            deactivation_completed.set()

        stop_call = threading.Thread(target=run_stop, daemon=True)
        with patch.object(guard_module, 'installation', side_effect=pause_after_initial_installation_read):
            stop_call.start()
            try:
                self.assertTrue(saw_enabled_installation.wait(5), 'Stop did not inspect activation')
                self.assertTrue(outcome['initially_enabled'])
                with installation_lock.open('r+') as stream:
                    try:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        # A Stop already holding the installation lock must finish
                        # first; deactivation cannot overtake its decision.
                        continue_stop.set()
                        stop_call.join(5)
                        self.assertFalse(stop_call.is_alive(), 'Stop did not release the lock')
                        with runtime.locked(installation_lock):
                            deactivate_while_locked()
                    else:
                        # Deactivation wins this interleaving. A previously read
                        # enabled=True must not authorize a later repair block.
                        deactivate_while_locked()
                continue_stop.set()
            finally:
                continue_stop.set()
                stop_call.join(5)
        self.assertFalse(stop_call.is_alive(), 'Stop did not finish')
        self.assertNotIn('error', outcome)
        if outcome['returned_after_deactivation']:
            self.assertEqual(outcome['result'], {})
            turn = json.loads((self.root / '.local/title-turns/test-thread.json').read_text())
            self.assertFalse(turn['repair_requested'])
        self.assertEqual(self.hook('Stop'), {})
        self.assertEqual(self.rpc.writes, [])

    def test_missing_installation_does_not_trigger(self):
        (self.root / '.local/title-installation.json').unlink()
        self.assert_not_triggered()

    def test_session_created_before_activation_does_not_trigger(self):
        self.rpc.thread['createdAt'] = 99
        self.assert_not_triggered()

    def test_outside_caller_does_not_trigger(self):
        self.assertEqual(self.begin_turn(cwd=self.temp.name), {})
        self.assertEqual(self.hook('Stop', cwd=self.temp.name), {})
        self.assertEqual(self.rpc.writes, [])

    def test_outside_target_thread_does_not_trigger(self):
        self.rpc.thread['cwd'] = self.temp.name
        self.assert_not_triggered()

    def test_nested_repository_does_not_trigger(self):
        nested = self.root / 'nested'
        nested.mkdir()
        subprocess.run(['git', 'init', '-q', str(nested)], check=True)
        self.rpc.thread['cwd'] = str(nested)
        self.assert_not_triggered()

    def test_forks_and_subagents_do_not_trigger(self):
        for extra in ({'forkedFromId': 'parent'}, {'parentThreadId': 'parent'},
                      {'sessionId': 'parent'}, {'source': {'subAgent': {'thread_spawn': {}}}}):
            with self.subTest(extra=extra):
                self.rpc.thread.update(extra)
                self.assert_not_triggered()
                for key in extra:
                    self.rpc.thread.pop(key)

    def test_rpc_read_failure_never_blocks_the_user_answer(self):
        self.begin_turn()
        self.rpc.fail_read = True
        self.assertEqual(self.hook('Stop'), {})
        self.assertEqual(self.hook('UserPromptSubmit', turn_id='turn-2'), {})
        self.assertEqual(self.rpc.writes, [])

    def test_unrelated_events_have_no_effect(self):
        for event in ('SessionStart', 'PostToolUse', 'SessionEnd', 'unknown'):
            with self.subTest(event=event):
                self.assertEqual(self.hook(event), {})
        self.assertFalse((self.root / '.local/title-turns').exists())
        self.assertEqual(self.rpc.writes, [])

    def test_hooks_only_write_their_turn_state_directory(self):
        self.set_title()
        local = self.root / '.local'
        before = {path.relative_to(local): path.read_bytes()
                  for path in local.rglob('*') if path.is_file()}
        self.begin_turn()
        self.hook('Stop')
        after = {path.relative_to(local): path.read_bytes()
                 for path in local.rglob('*') if path.is_file()}
        for relative, content in before.items():
            self.assertEqual(after.get(relative), content, str(relative))
        self.assertTrue(set(after) - set(before))
        self.assertTrue(all(path.parts[0] == 'title-turns' for path in set(after) - set(before)))
        self.assertEqual(len(self.rpc.writes), 1)

    def test_invalid_session_ids_cannot_write_outside_turn_state(self):
        before = {path.relative_to(self.root) for path in self.root.rglob('*')}
        absolute_id = str(Path(self.temp.name) / 'escape')
        for session_id in ('../escape', absolute_id, '', None, 'a' * 129):
            with self.subTest(session_id=session_id):
                self.assertEqual(self.begin_turn(session_id=session_id), {})
                self.assertEqual(self.hook('Stop', session_id=session_id), {})
        self.assertEqual({path.relative_to(self.root) for path in self.root.rglob('*')}, before)
        self.assertEqual(self.rpc.writes, [])

    def test_symlinked_turn_directory_cannot_receive_state(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        (self.root / '.local/title-turns').symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.begin_turn(), {})
        self.assertEqual(self.hook('Stop'), {})
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlinked_local_directory_is_not_used(self):
        outside = Path(self.temp.name) / 'outside-local'
        local = self.root / '.local'
        local.rename(outside)
        local.symlink_to(outside, target_is_directory=True)
        before = {path.name: path.read_bytes() for path in outside.iterdir() if path.is_file()}
        self.assertEqual(self.begin_turn(), {})
        self.assertEqual(self.hook('Stop'), {})
        after = {path.name: path.read_bytes() for path in outside.iterdir() if path.is_file()}
        self.assertEqual(after, before)
        self.assertFalse((outside / 'title-turns').exists())

    def test_symlinked_turn_state_cannot_overwrite_an_external_file(self):
        directory = self.root / '.local/title-turns'
        directory.mkdir()
        outside = Path(self.temp.name) / 'preserve.json'
        outside.write_text('keep this external file')
        state_path = directory / 'test-thread.json'
        state_path.symlink_to(outside)
        self.assertEqual(self.begin_turn(), {})
        self.assertEqual(self.hook('Stop'), {})
        self.assertTrue(state_path.is_symlink())
        self.assertEqual(outside.read_text(), 'keep this external file')

    def test_busy_turn_lock_does_not_consume_the_repair_opportunity(self):
        self.begin_turn()
        lock_path = self.root / '.local/title-turns/test-thread.lock'
        self.assertTrue(lock_path.is_file())
        with lock_path.open('r+') as lock_stream:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            clock = itertools.count(start=0, step=4)
            with patch('time.monotonic', side_effect=lambda: next(clock)):
                self.assertEqual(self.hook('Stop'), {})
        self.assertEqual(self.hook('Stop').get('decision'), 'block')

    def test_symlinked_turn_lock_does_not_touch_an_external_file(self):
        self.begin_turn()
        outside = Path(self.temp.name) / 'preserve-lock'
        outside.write_text('keep this external lock file')
        lock_path = self.root / '.local/title-turns/test-thread.lock'
        lock_path.unlink()
        lock_path.symlink_to(outside)
        self.assertEqual(self.hook('Stop'), {})
        self.assertTrue(lock_path.is_symlink())
        self.assertEqual(outside.read_text(), 'keep this external lock file')


if __name__ == '__main__':
    unittest.main()
