import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
import os
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from title_plugin import Installer, InstallError, build_hooks


class PluginLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        binding = patch('title_runtime.GLOBAL_BINDING', Path(self.temp.name) / 'unbound-source.json')
        binding.start()
        self.addCleanup(binding.stop)
        home = Path(self.temp.name) / 'codex-home'; home.mkdir()
        self.env = patch.dict(os.environ, {'CODEX_HOME': str(home)})
        self.env.start()
        self.root = Path(self.temp.name).resolve() / 'test project'
        self.root.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / 'AGENTS.md').write_text('# My rules\nKeep my instructions.\n')
        (self.root / '.codex').mkdir()
        (self.root / '.codex/config.toml').write_text('model = "my-model"\n')
        self.installer = Installer(self.root)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_install_update_uninstall_preserves_unrelated_content(self):
        first = self.installer.configure()
        self.assertTrue(first['plugin_id'].startswith('clarity-session-titles@'))
        config = tomllib.loads((self.root / '.codex/config.toml').read_text())
        self.assertEqual(config['model'], 'my-model')
        self.assertTrue(config['plugins'][first['plugin_id']]['enabled'])
        activation = json.loads((self.root / '.local/title-installation.json').read_text())
        agents = self.root / 'AGENTS.md'
        agents.write_text(agents.read_text() + '\nUser added this later.\n')
        self.installer.configure()
        self.assertEqual(json.loads((self.root / '.local/title-installation.json').read_text()), activation)
        self.installer.uninstall()
        self.assertIn('User added this later.', agents.read_text())
        self.assertIn('Keep my instructions.', agents.read_text())
        self.assertNotIn('clarity-session-titles', agents.read_text())
        self.assertEqual(tomllib.loads((self.root / '.codex/config.toml').read_text()), {'model': 'my-model'})
        self.assertFalse(json.loads((self.root / '.local/title-installation.json').read_text())['enabled'])
        self.installer.uninstall()  # repeated uninstall is harmless

    def test_two_projects_have_independent_plugin_ids(self):
        other = self.root.parent / 'other'; other.mkdir()
        subprocess.run(['git', 'init', '-q', str(other)], check=True)
        a = self.installer.configure(); b = Installer(other).configure()
        self.assertNotEqual(a['plugin_id'], b['plugin_id'])
        self.installer.uninstall()
        self.assertTrue(json.loads((other / '.local/title-installation.json').read_text())['enabled'])

    def test_does_not_install_in_subfolder_or_without_git_root(self):
        child = self.root / 'child'; child.mkdir()
        with self.assertRaises(InstallError):
            Installer(child).configure()

    def test_symlinked_config_is_rejected_before_other_files_change(self):
        config = self.root / '.codex/config.toml'
        outside = self.root.parent / 'outside'; outside.write_text('model = "outside"\n')
        config.unlink(); config.symlink_to(outside)
        before = (self.root / 'AGENTS.md').read_text()
        with self.assertRaises(InstallError):
            self.installer.configure()
        self.assertEqual(outside.read_text(), 'model = "outside"\n')
        self.assertEqual((self.root / 'AGENTS.md').read_text(), before)

    def test_broken_managed_block_is_not_overwritten(self):
        self.installer.configure()
        agents = self.root / 'AGENTS.md'
        agents.write_text(agents.read_text().replace('<!-- agent-clarity-titles:end -->', ''))
        with self.assertRaises(InstallError):
            self.installer.configure()

    def test_modified_deployed_plugin_is_not_overwritten(self):
        info = self.installer.configure()
        file = Path(info['source']) / 'plugins/clarity-session-titles/skills/manage-title/SKILL.md'
        file.write_text('local user edit')
        with self.assertRaises(InstallError):
            self.installer.configure()

    def test_failed_staging_keeps_previous_installation(self):
        info = self.installer.configure()
        file = Path(info['source']) / 'plugins/clarity-session-titles/skills/manage-title/SKILL.md'
        expected = file.read_bytes()
        rules = (self.root / 'AGENTS.md').read_bytes()
        with patch('title_plugin.shutil.copytree', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.installer.configure()
        self.assertEqual(file.read_bytes(), expected)
        self.assertEqual((self.root / 'AGENTS.md').read_bytes(), rules)

    def test_legacy_generated_hooks_are_backed_up_and_removed(self):
        hook = self.root / '.codex/hooks.json'
        hook.write_text(json.dumps(build_hooks(self.root)))
        self.installer.configure()
        self.assertFalse(hook.exists())
        self.assertEqual(len(list((self.root / '.local/agent-clarity/backups').glob('*/.codex/hooks.json'))), 1)

    def test_unrelated_hooks_are_preserved(self):
        hook = self.root / '.codex/hooks.json'
        hook.write_text('{"hooks": {"Stop": []}}')
        self.installer.configure(); self.installer.uninstall()
        self.assertEqual(hook.read_text(), '{"hooks": {"Stop": []}}')

    def test_interrupted_cache_load_is_tracked_for_uninstall(self):
        self.installer.configure()
        home = self.root.parent / 'fake-home'; home.mkdir()
        manager = self.installer
        class InterruptedRPC:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def request(self, method, params):
                import shutil
                record = manager.read_receipt()
                cache = Path(next(iter(record['cached_versions'])))
                cache.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(manager.catalog / 'plugins/clarity-session-titles', cache)
                raise OSError('server stopped after copy')
        with patch.dict(os.environ, {'CODEX_HOME': str(home)}), patch('title_plugin.CodexRPC', InterruptedRPC):
            with self.assertRaises(OSError):
                manager.refresh()
            cache = Path(next(iter(manager.read_receipt()['cached_versions'])))
            self.assertTrue(cache.exists())
            manager.uninstall()
            self.assertFalse(cache.exists())

    def test_refresh_excludes_remote_marketplaces(self):
        self.installer.configure()
        calls = []
        class LocalOnlyRPC:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def request(self, method, params):
                calls.append((method, params))
                raise OSError('stop after catalog request')
        with patch('title_plugin.CodexRPC', LocalOnlyRPC):
            with self.assertRaises(OSError):
                self.installer.refresh()
        self.assertEqual(calls, [('plugin/list', {
            'cwds': [str(self.root)], 'marketplaceKinds': ['local']})])

    def test_uninstall_waits_for_cache_refresh(self):
        self.installer.configure()
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        errors = []
        def slow_refresh():
            entered.set()
            release.wait(2)
            return {}
        def uninstall():
            try:
                self.installer.uninstall()
                finished.set()
            except Exception as error:
                errors.append(error)
        with patch.object(self.installer, '_refresh', side_effect=slow_refresh):
            refresh = threading.Thread(target=self.installer.refresh); refresh.start()
            self.assertTrue(entered.wait(1))
            removal = threading.Thread(target=uninstall); removal.start()
            self.assertFalse(finished.wait(0.1))
            release.set(); refresh.join(3); removal.join(3)
        self.assertTrue(finished.is_set())
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
