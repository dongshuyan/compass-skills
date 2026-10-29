#!/usr/bin/env python3
"""Real Codex plugin loading in a disposable home; no model calls or credentials."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from codex_rpc import CodexRPC
from title_plugin import Installer, SOURCE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', required=True)
    parser.parse_args()
    binding = SOURCE / 'global-installation.json'
    if binding.exists() or binding.is_symlink():
        raise RuntimeError('Lifecycle checks require an unbound source: remove the '
                           'generated global-installation.json from the test source copy.')
    base = ROOT / '.local/plugin-integration'; base.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='run-', dir=base))
    home = folder / 'codex-home'; home.mkdir()
    a, b = folder / 'project A', folder / 'project B'
    for project in (a, b):
        project.mkdir(); subprocess.run(['git', 'init', '-q', str(project)], check=True)
        (project / 'AGENTS.md').write_text('Keep existing project rules.\n')
    source = folder / 'source'
    shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    config = ''.join(f'[projects.{json.dumps(str(p))}]\ntrust_level = "trusted"\n' for p in (a, b))
    (home / 'config.toml').write_text(config)
    os.environ['CODEX_HOME'] = str(home)
    os.environ['CODEX_CLI_PATH'] = shutil.which('codex')

    def plugin_skills(project):
        with CodexRPC(cwd=project, timeout=30) as rpc:
            result = rpc.request('skills/list', {'cwds': [str(project)], 'forceReload': True})
        return [s for entry in result['data'] for s in entry.get('skills', []) if s.get('pluginId')]

    checks = {}
    manager = Installer(a, source=source)
    manager.configure(); first = manager.refresh()
    checks['real_plugin_loaded'] = any(s['pluginId'] == first['plugin_id'] for s in plugin_skills(a))
    checks['untrusted_hooks_not_ready'] = not first['runtime_ready'] and first['needs_hook_review']
    checks['other_project_excluded'] = not plugin_skills(b)
    activation = (a / '.local/title-installation.json').read_bytes()
    skill_source = source / 'skills/manage-title/SKILL.md'
    skill_source.write_text(skill_source.read_text() + '\nSame-version update marker.\n')
    manager.configure(); same = manager.refresh()
    checks['same_version_update'] = 'Same-version update marker.' in Path(same['skill_path']).read_text()
    manifest = source / '.codex-plugin/plugin.json'
    data = json.loads(manifest.read_text())
    major, minor, patch = map(int, data['version'].split('.'))
    next_version = f'{major}.{minor}.{patch + 1}'
    data['version'] = next_version
    manifest.write_text(json.dumps(data))
    manager.configure(); updated = manager.refresh()
    checks['version_update'] = (updated['version'] == next_version
                               and f'/{next_version}/' in updated['skill_path'])
    checks['activation_time_preserved'] = activation == (a / '.local/title-installation.json').read_bytes()
    other = Installer(b, source=source); other.configure(); second = other.refresh()
    checks['independent_installations'] = first['plugin_id'] != second['plugin_id']
    manager.uninstall()
    checks['uninstall_stops_loading'] = not plugin_skills(a)
    checks['uninstall_removes_owned_cache'] = not Path(updated['skill_path']).exists()
    checks['uninstall_preserves_other_project'] = any(s['pluginId'] == second['plugin_id'] for s in plugin_skills(b))
    checks['uninstall_preserves_user_rules'] = 'Keep existing project rules.' in (a / 'AGENTS.md').read_text()
    manager.uninstall()
    manager.configure(); reinstalled = manager.refresh()
    checks['reinstall_works'] = Path(reinstalled['skill_path']).is_file()
    checks['user_config_byte_unchanged'] = (home / 'config.toml').read_text() == config
    plain = folder / 'plain folder'; plain.mkdir()
    rules = home / 'AGENTS.md'; rules.write_text('Keep original global rules.\n')
    global_manager = Installer(source=source, global_mode=True)
    global_first = global_manager.install()
    global_id = global_first['plugin_id']
    checks['global_loads_in_two_repos_and_non_git'] = all(
        any(s['pluginId'] == global_id for s in plugin_skills(p)) for p in (a, b, plain))
    checks['global_untrusted_hooks_not_ready'] = not global_first['runtime_ready'] and global_first['needs_hook_review']
    global_manager.install(update=True)
    checks['global_update_keeps_original_config'] = config in (home / 'config.toml').read_text()
    transition = global_manager.replace_project(a)
    checks['global_transition_removes_duplicate_project'] = (transition['result'] == 'uninstalled'
        and not any(s['pluginId'] == reinstalled['plugin_id'] for s in plugin_skills(a)))
    global_manager.uninstall()
    checks['global_uninstall_stops_non_git_loading'] = not plugin_skills(plain)
    checks['global_uninstall_restores_config'] = (home / 'config.toml').read_text().strip() == config.strip()
    checks['global_uninstall_preserves_rules'] = rules.read_text().strip() == 'Keep original global rules.'
    checks['global_uninstall_keeps_independent_project'] = any(
        s['pluginId'] == second['plugin_id'] for s in plugin_skills(b))
    global_manager.install()
    checks['global_reinstall_works'] = any(s['pluginId'] == global_id for s in plugin_skills(plain))
    result = {'checks': checks, 'passed': all(checks.values()), 'folder': str(folder)}
    (folder / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)
    if not result['passed']:
        raise RuntimeError('Plugin integration failed')


if __name__ == '__main__':
    main()
