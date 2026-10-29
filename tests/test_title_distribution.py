"""The public title bundle works after relocation, without its original checkout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TitleDistributionTests(unittest.TestCase):
    def test_relocated_export_installs_a_self_contained_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            export = base / 'public checkout with spaces'
            plugin = Path('plugins/clarity-session-titles')
            shutil.copytree(ROOT / plugin, export / plugin,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc',
                                                         'global-installation.json'))
            (export / 'scripts').mkdir()
            for name in ('title_plugin.py', 'session_title.py', 'codex_rpc.py'):
                shutil.copyfile(ROOT / 'scripts' / name, export / 'scripts' / name)
            project = base / 'unrelated project'
            project.mkdir()
            subprocess.run(['git', 'init', '-q', str(project)], check=True)
            home = base / 'isolated codex home'
            home.mkdir()
            environment = dict(os.environ, CODEX_HOME=str(home))
            code = (
                'import json,sys; sys.path.insert(0,sys.argv[1]); '
                'from title_plugin import Installer; '
                'print(json.dumps(Installer(sys.argv[2]).configure()))'
            )
            configured = subprocess.run(
                [sys.executable, '-c', code, str(export / 'scripts'), str(project)],
                cwd=base, env=environment, text=True, capture_output=True, check=True,
            )
            record = json.loads(configured.stdout)
            installed = Path(record['source']) / plugin
            self.assertTrue((installed / 'LICENSE').is_file())
            self.assertTrue((installed / 'LICENSES/agent-session-titles.txt').is_file())
            export.rename(base / 'source no longer at original path')
            runtime = subprocess.run(
                [sys.executable, str(installed / 'scripts/title_runtime.py'), 'set', '--help'],
                cwd=base, env=environment, text=True, capture_output=True, check=True,
            )
            self.assertIn('--progress', runtime.stdout)
            self.assertIn('clarity-session-titles@', record['plugin_id'])

    def test_lifecycle_rejects_bound_source_before_creating_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            export = base / 'export'
            shutil.copytree(ROOT / 'plugins', export / 'plugins',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc',
                                                         'global-installation.json'))
            shutil.copytree(ROOT / 'scripts', export / 'scripts',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            (export / 'tests').mkdir()
            lifecycle = export / 'tests/live_plugin_lifecycle.py'
            shutil.copyfile(ROOT / 'tests/live_plugin_lifecycle.py', lifecycle)
            outside = base / 'state outside disposable codex home'
            binding = export / 'plugins/clarity-session-titles/global-installation.json'
            binding.write_text(json.dumps({'version': 1, 'root': str(outside)}))
            home = base / 'isolated home'
            home.mkdir()
            result = subprocess.run(
                [sys.executable, str(lifecycle), '--execute'], cwd=base,
                env=dict(os.environ, CODEX_HOME=str(home)),
                text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(outside.exists())
            self.assertFalse((export / '.local').exists())
            self.assertIn('global-installation.json', result.stderr)


if __name__ == '__main__':
    unittest.main()
