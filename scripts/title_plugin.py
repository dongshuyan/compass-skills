#!/usr/bin/env python3
"""Install, update, inspect, or uninstall titles for one project or this Codex home."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib

from codex_rpc import CodexRPC, RPCError
from session_title import (activate, installation, in_scope, locked, write_json, build_hooks,
                           codex_home, global_root, ID, scope_locked, read_title_state)

SOURCE = Path(__file__).resolve().parents[1] / 'plugins/clarity-session-titles'
PLUGIN = 'clarity-session-titles'
RULE_START = '<!-- agent-clarity-titles:start -->'
RULE_END = '<!-- agent-clarity-titles:end -->'
CONFIG_START = '# agent-clarity-titles:start'
CONFIG_END = '# agent-clarity-titles:end'


class InstallError(RuntimeError):
    pass


def hook_readiness(response, plugin_id, root):
    hooks = [hook for entry in response.get('data', []) if Path(entry['cwd']).resolve() == root.resolve()
             for hook in entry.get('hooks', []) if hook.get('pluginId') == plugin_id]
    expected = {'userPromptSubmit', 'stop'}
    ready = ({hook['eventName'] for hook in hooks} == expected and len(hooks) == 2
             and all(hook.get('enabled') and hook.get('trustStatus') in ('trusted', 'managed') for hook in hooks))
    return {'runtime_ready': ready,
            'needs_hook_review': any(hook.get('trustStatus') in ('untrusted', 'modified') for hook in hooks),
            'hooks': [{k: hook.get(k) for k in ('eventName', 'enabled', 'trustStatus')} for hook in hooks]}


def block(text, start, end, body):
    """Replace only our delimited block; preserve all unrelated text."""
    if text.count(start) != text.count(end) or text.count(start) > 1:
        raise InstallError('托管标记不完整或重复，请先检查文件；未覆盖用户内容')
    replacement = f'{start}\n{body.rstrip()}\n{end}' if body is not None else ''
    if start in text:
        a, b = text.index(start), text.index(end) + len(end)
        if b < a:
            raise InstallError('托管标记顺序错误')
        return text[:a] + replacement + text[b:]
    return text + ('\n\n' if text and not text.endswith('\n\n') else '') + replacement + '\n' if body is not None else text


def safe_path(root, path):
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise InstallError(f'拒绝通过符号链接修改文件：{part}')
    if not path.is_relative_to(root):
        raise InstallError('目标文件不在项目中')


def digest_files(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise InstallError(f'插件文件不能是符号链接：{path}')
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def atomic_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.clarity-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class Installer:
    def __init__(self, root=None, *, source=SOURCE, global_mode=False, portable=False):
        if portable and not global_mode:
            raise InstallError('共享安装只适用于全局插件')
        self.portable = portable
        if global_mode and root is not None:
            raise InstallError('--global 与 --project 不能同时使用')
        if not global_mode and root is None:
            raise InstallError('请选择 --global 或 --project')
        self.global_mode = global_mode
        self.scope = 'global' if global_mode else 'project'
        self.root = global_root() if global_mode else Path(root).resolve()
        self.boundary = codex_home() if global_mode else self.root
        self.query_cwd = self.boundary
        self.source = Path(source).resolve()
        self.data = self.root / '.local/agent-clarity'
        self.catalog = self.data / 'marketplace'
        self.receipt = self.data / 'plugin.json'
        prefix = 'agent-clarity-global-' if global_mode else 'agent-clarity-'
        self.market = prefix + hashlib.sha256(str(self.root).encode()).hexdigest()[:12]
        self.plugin_id = f'{PLUGIN}@{self.market}'
        self.config = self.boundary / ('config.toml' if global_mode else '.codex/config.toml')
        override = self.boundary / 'AGENTS.override.md'
        self.agents = (override if global_mode and override.is_file() and override.stat().st_size
                       else self.boundary / 'AGENTS.md')
        self.legacy_hooks = self.root / '.codex/hooks.json'

    def preflight(self):
        safe_path(self.boundary, self.receipt)
        record = self.read_receipt()
        if record and record.get('rules_path'):
            recorded_rules = Path(record['rules_path'])
            allowed = [self.boundary / 'AGENTS.md']
            if self.global_mode:
                allowed.append(self.boundary / 'AGENTS.override.md')
            if recorded_rules not in allowed:
                raise InstallError('规则记录不在允许的路径内')
            self.agents = recorded_rules
        if self.global_mode and (self.root != global_root() or not self.boundary.is_dir()):
            raise InstallError('CODEX_HOME 不存在或已改变')
        if not self.global_mode and not in_scope(self.root, self.root):
            raise InstallError('--project 必须指向独立 Git 仓库的根目录')
        for path in (self.data, self.receipt, self.catalog, self.config, self.agents,
                     self.legacy_hooks, self.root / '.gitignore', self.root / '.local/title-installation.json'):
            safe_path(self.boundary, path)

    def read_receipt(self):
        if not self.receipt.exists():
            return None
        value = json.loads(self.receipt.read_text())
        if (not isinstance(value, dict) or value.get('project') != str(self.root)
                or value.get('plugin_id') != self.plugin_id or value.get('source') != str(self.catalog)
                or value.get('scope', 'project') != self.scope):
            raise InstallError('安装记录损坏或项目已移动，未自动覆盖')
        return value

    def configure(self):
        self.preflight()
        self.data.mkdir(parents=True, exist_ok=True)
        with scope_locked(), locked(self.data / 'install.lock'):
            return self._configure()

    def install(self, *, update=False):
        self.preflight()
        self.data.mkdir(parents=True, exist_ok=True)
        with scope_locked(), locked(self.data / 'install.lock'):
            if update and not self.receipt.exists():
                raise InstallError('本项目尚未安装，请先执行 install')
            self._configure()
            return self._refresh()

    def _configure(self):
        previous = self.read_receipt()
        if self.catalog.exists():
            if not previous or digest_files(self.catalog) != previous.get('files'):
                raise InstallError('已部署的插件文件被修改；保留修改，未覆盖')
        manifest = json.loads((self.source / '.codex-plugin/plugin.json').read_text())
        if manifest['name'] != PLUGIN:
            raise InstallError('插件包名称不符')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', manifest.get('version', '')):
            raise InstallError('插件版本号无效')
        digest_files(self.source)  # reject symlinks before any project edits
        original_config = self.config.read_text() if self.config.exists() else ''
        original_rules = self.agents.read_text() if self.agents.exists() else ''
        migrate_hooks = False
        if self.legacy_hooks.exists():
            hooks = json.loads(self.legacy_hooks.read_text())
            migrate_hooks = hooks == build_hooks(self.root)
            if not migrate_hooks and str(self.root / 'scripts/session_title.py') in json.dumps(hooks):
                raise InstallError('旧标题钩子含用户修改，未覆盖；请先移除其中旧标题项，再安装插件')
        clean_config = block(original_config, CONFIG_START, CONFIG_END, None)
        parsed = tomllib.loads(clean_config)
        if self.plugin_id in parsed.get('plugins', {}) or self.market in parsed.get('marketplaces', {}):
            raise InstallError('已有同名插件配置不属于安装器，未覆盖')
        config_body = (f'[marketplaces.{json.dumps(self.market)}]\nsource_type = "local"\n'
                       f'source = {json.dumps(str(self.catalog), ensure_ascii=False)}\n\n'
                       f'[plugins.{json.dumps(self.plugin_id)}]\nenabled = true')
        next_config = block(original_config, CONFIG_START, CONFIG_END, config_body)
        tomllib.loads(next_config)
        rules = ('## 本项目的三段式会话标题\n\n'
                 '明确需求后、实际进展变化时和交付前，使用 `clarity-session-titles:manage-title` 插件 Skill，'
                 '主动维护“状态｜初始需求｜当前进展”。初始需求保持稳定，状态和进展按事实更新。\n'
                 '每轮最终回复前都调用插件脚本核对一次；简短问答、无需其他工具的回合也不例外。'
                 '已有标题仍准确时，脚本只记录已检查，不重复改名。\n'
                 '若插件未出现在技能列表，读取本项目 `.local/agent-clarity/plugin.json` 的 `skill_path` '
                 '并加载该 Skill；安装记录或 Skill 不存在则跳过。不要自行安装或启用。\n'
                 '仅接管本项目启用后新建的根会话；保留手动修改。回答结束不等于任务完成。')
        next_rules = block(original_rules, RULE_START, RULE_END, rules)
        if self.global_mode:
            rules = ('## 全局三段式会话标题\n\n'
                     '本账户各目录的新会话和继续对话的已有会话，在每轮最终回复前使用 '
                     '`clarity-session-titles:manage-title` 插件核对“状态｜初始需求｜当前进展”。'
                     '初始需求保持稳定，状态与进展按事实更新；简短问答也要核对。'
                     '仅维护当前会话，不批量处理历史会话、不处理内部子代理。\n'
                     '使用插件内的 title_runtime.py --global set；'
                     '若插件未列出，可读取 ' + str(self.receipt) + ' 的 skill_path 并加载该 Skill。'
                     '安装记录或 Skill 不存在则跳过，不自行安装或启用。'
                     '保留手动修改；回答结束不等于任务完成。')
            next_rules = block(original_rules, RULE_START, RULE_END, rules)
        ignore = self.root / '.gitignore'
        original_ignore = ignore.read_text() if ignore.exists() else ''
        next_ignore = original_ignore
        if not self.global_mode and not any(line.strip() in ('.local/', '/.local/', '.local', '/.local') for line in original_ignore.splitlines()):
            next_ignore += '\n# Agent Clarity local state and installation backups\n/.local/\n'
        before = {p: p.read_bytes() if p.exists() else None for p in
                  (self.config, self.agents, *([] if self.global_mode else [ignore]), self.receipt, self.legacy_hooks,
                   self.root / '.local/title-installation.json')}
        backup = self.data / 'backups' / str(time.time_ns())
        safe_path(self.boundary, backup)
        backup.mkdir(parents=True)
        for path, value in before.items():
            if value is not None:
                dest = backup / path.relative_to(self.boundary)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(value)
                dest.chmod(0o600)
        staged = Path(tempfile.mkdtemp(prefix='stage-', dir=self.data))
        old_catalog = backup / 'marketplace'
        catalog_changed = False
        try:
            shutil.copytree(self.source, staged / 'plugins' / PLUGIN,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            portable = self.portable or bool(previous and previous.get('portable'))
            if portable:
                # Harbor inherits this package but deliberately keeps account
                # homes separate. Carry the explicitly selected activation root
                # with the package instead of depending on copied private state.
                write_json(staged / 'plugins' / PLUGIN / 'global-installation.json',
                           {'version': 1, 'root': str(self.root)})
            catalog_file = staged / '.agents/plugins/marketplace.json'
            catalog_file.parent.mkdir(parents=True)
            catalog_file.write_text(json.dumps({'name': self.market,
                'interface': {'displayName': f'Agent Clarity — {self.root.name}'},
                'plugins': [{'name': PLUGIN, 'source': {'source': 'local', 'path': f'./plugins/{PLUGIN}'},
                             'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'},
                             'category': 'Productivity'}]}, ensure_ascii=False, indent=2) + '\n')
            if self.catalog.exists():
                self.catalog.rename(old_catalog)
            catalog_changed = True
            staged.rename(self.catalog)
            record = {'project': str(self.root), 'plugin_id': self.plugin_id, 'source': str(self.catalog),
                      'scope': self.scope, 'rules_path': str(self.agents),
                      'version': manifest['version'], 'files': digest_files(self.catalog), 'enabled': True}
            if portable:
                record['portable'] = True
            # Retain a usable installed path during a same-version refresh.
            if previous and previous.get('version') == record['version'] and previous.get('skill_path'):
                record['skill_path'] = previous['skill_path']
            record['cached_versions'] = previous.get('cached_versions', {}) if previous else {}
            atomic_text(self.config, next_config)
            atomic_text(self.agents, next_rules)
            if not self.global_mode:
                atomic_text(ignore, next_ignore)
            if migrate_hooks:
                self.legacy_hooks.unlink()
            write_json(self.receipt, record)
            activate(self.root, global_mode=self.global_mode)
            return record
        except BaseException:
            # Synchronous transaction: restore only files this operation wrote.
            for path, value in before.items():
                if value is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_text(path, value.decode('utf-8'))
            if catalog_changed and self.catalog.exists():
                shutil.rmtree(self.catalog)
            if old_catalog.exists():
                old_catalog.rename(self.catalog)
            raise
        finally:
            if staged.exists():
                shutil.rmtree(staged)

    def refresh(self):
        """Codex copies the project-configured plugin into its official cache."""
        self.preflight()
        with scope_locked(), locked(self.data / 'install.lock'):
            return self._refresh()

    def _refresh(self):
        record = self.read_receipt()
        if not record or not record['enabled']:
            raise InstallError('本项目尚未启用插件')
        # Refresh same-version edits too. Only remove cache files we previously
        # recorded unchanged; Codex repopulates them using the project source.
        retained = self.clear_cache(record)
        if retained:
            raise InstallError('插件缓存有本地修改，未覆盖：' + ', '.join(retained))
        home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).resolve()
        expected_cache = home / 'plugins/cache' / self.market / PLUGIN / record['version']
        safe_path(home, expected_cache)
        cache_files = {name.removeprefix(f'plugins/{PLUGIN}/'): checksum
                       for name, checksum in record['files'].items() if name.startswith(f'plugins/{PLUGIN}/')}
        # Register the expected cache BEFORE asking Codex to populate it. A crash
        # after copying can then be cleaned up by a subsequent uninstall.
        record['cached_versions'] = {str(expected_cache): cache_files}
        write_json(self.receipt, record)
        skills = []
        for attempt in range(2):
            with CodexRPC(cwd=self.query_cwd, timeout=30, local_only=True) as rpc:
                # Discover local sources, then load the project configuration.
                # config/read populates the official cache from that catalog.
                catalog = rpc.request('plugin/list', {'cwds': [str(self.query_cwd)],
                                                      'marketplaceKinds': ['local']})
                if catalog.get('marketplaceLoadErrors'):
                    raise InstallError('Codex 无法读取本地插件源：' + json.dumps(catalog['marketplaceLoadErrors'], ensure_ascii=False))
                rpc.request('config/read', {'cwd': str(self.query_cwd), 'includeLayers': False})
                response = rpc.request('skills/list', {'cwds': [str(self.query_cwd)], 'forceReload': True})
            skills = [s for entry in response.get('data', []) for s in entry.get('skills', [])
                      if s.get('pluginId') == self.plugin_id and s.get('enabled')]
            if skills:
                break
            # A cold-cache refresh can copy the package after its skill snapshot
            # was built. Reopen the server once; never loop on an untrusted repo.
            if not expected_cache.is_dir():
                break
        if not skills:
            raise InstallError('项目文件已配置，但 Codex 尚未加载插件。请先在 Codex 中打开并信任此项目，再重试安装。')
        skill = next((s for s in skills if s['name'].endswith(':manage-title')), None)
        if not skill or not Path(skill['path']).is_file():
            raise InstallError('Codex 返回的插件 Skill 不完整')
        cache = Path(skill['path']).parents[2]
        if cache != expected_cache or digest_files(cache) != cache_files:
            raise InstallError('Codex 插件缓存与当前安装包不一致，未报告安装成功')
        record['skill_path'] = skill['path']
        with CodexRPC(cwd=self.query_cwd, timeout=30, local_only=True) as rpc:
            record.update(hook_readiness(rpc.request('hooks/list', {'cwds': [str(self.query_cwd)]}),
                                         self.plugin_id, self.query_cwd))
        write_json(self.receipt, record)
        return record

    def status(self):
        self.preflight()
        record = self.read_receipt()
        if not record:
            return {'result': 'not_installed'}
        if record.get('enabled'):
            with CodexRPC(cwd=self.query_cwd, timeout=30, local_only=True) as rpc:
                record.update(hook_readiness(rpc.request('hooks/list', {'cwds': [str(self.query_cwd)]}),
                                             self.plugin_id, self.query_cwd))
        else:
            record['runtime_ready'] = False
        return record

    def clear_cache(self, record):
        home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).resolve()
        parent = home / 'plugins/cache' / self.market / PLUGIN
        retained = []
        for name, checksums in record.get('cached_versions', {}).items():
            path = Path(name)
            if path.parent != parent:
                retained.append(name)
                continue
            safe_path(home, path)
            if path.exists():
                if digest_files(path) != checksums:
                    retained.append(name)
                else:
                    shutil.rmtree(path)
        return retained

    def replace_project(self, project):
        """Explicit transition: retain title protection, then disable the old project package."""
        if not self.global_mode:
            raise InstallError('只有全局安装可以接管项目安装')
        self.preflight()
        active = installation(self.root)
        if not active or not active['enabled']:
            raise InstallError('请先完成全局安装，再迁移项目')
        local = Installer(project)
        local.preflight()
        record = local.read_receipt()
        if not record or not record['enabled']:
            return {'result': 'not_installed', 'migrated_states': 0}
        source = local.root / '.local/titles'
        destination = self.root / '.local/titles'
        safe_path(local.root, source)
        safe_path(self.root, destination)
        with scope_locked(), locked(self.data / 'install.lock'), locked(local.data / 'install.lock'), \
                locked(self.root / '.local/title-installation.lock'), \
                locked(local.root / '.local/title-installation.lock'):
            active = installation(self.root)
            if not active or not active['enabled']:
                raise InstallError('全局安装已停用，保留项目版，未迁移')
            states, kept = [], 0
            for path in sorted(source.glob('*.json')):
                safe_path(local.root, path)
                if not ID.fullmatch(path.stem):
                    raise InstallError('项目标题记录含无效会话 ID，未迁移')
                state = read_title_state(path)
                if (not isinstance(state, dict) or state.get('version') not in (1, 2)
                        or not isinstance(state.get('topic'), str)
                        or type(state.get('paused')) is not bool):
                    raise InstallError('项目标题记录损坏，未迁移')
                target = destination / path.name
                safe_path(self.root, target)
                if target.exists():
                    current = read_title_state(target)
                    if (current.get('version') not in (1, 2) or not isinstance(current.get('topic'), str)
                            or type(current.get('paused')) is not bool):
                        raise InstallError('全局标题保护记录损坏，未迁移')
                    if current.get('revision', 0) > state.get('revision', 0):
                        kept += 1
                        continue
                    if current.get('revision', 0) == state.get('revision', 0) and current != state:
                        raise InstallError('全局已有不同的标题保护记录，保留双方记录，未卸载项目版')
                states.append((target, state))
            destination.mkdir(exist_ok=True)
            for target, state in states:
                write_json(target, state)
            active = installation(local.root)
            if active:
                active['enabled'] = False
                write_json(local.root / '.local/title-installation.json', active)
        removed = local.uninstall()
        return {**removed, 'migrated_states': len(states), 'kept_newer_global_states': kept}

    def uninstall(self):
        self.preflight()
        if not self.receipt.exists():
            return {'result': 'not_installed'}
        with scope_locked(), locked(self.data / 'install.lock'):
            record = self.read_receipt()
            config = self.config.read_text() if self.config.exists() else ''
            rules = self.agents.read_text() if self.agents.exists() else ''
            next_config = block(config, CONFIG_START, CONFIG_END, None)
            next_rules = block(rules, RULE_START, RULE_END, None)
            tomllib.loads(next_config)
            with locked(self.root / '.local/title-installation.lock'):
                current = installation(self.root)
                if current:
                    current['enabled'] = False
                    write_json(self.root / '.local/title-installation.json', current)
            atomic_text(self.config, next_config)
            atomic_text(self.agents, next_rules)
            record['enabled'] = False
            write_json(self.receipt, record)
            # Preserve changed files; removal of rules/config already stops loading.
            preserved = self.catalog.exists() and digest_files(self.catalog) != record['files']
            if self.catalog.exists() and not preserved:
                shutil.rmtree(self.catalog)
            retained_cache = self.clear_cache(record)
            return {'result': 'uninstalled', 'preserved_modified_files': bool(preserved),
                    'retained_cache': retained_cache, 'plugin_id': self.plugin_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'update', 'uninstall', 'status'])
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--project', type=Path)
    scope.add_argument('--global', dest='global_mode', action='store_true')
    parser.add_argument('--migrate-project', type=Path,
                        help='全局安装就绪后迁移此项目的标题保护记录，并卸载项目版')
    parser.add_argument('--portable', action='store_true',
                        help='在全局包中固定共享状态位置，供多个 CODEX_HOME 继承')
    args = parser.parse_args()
    if args.migrate_project and (not args.global_mode or args.command not in ('install', 'update')):
        parser.error('--migrate-project 仅用于全局 install 或 update')
    try:
        manager = Installer(args.project, global_mode=args.global_mode, portable=args.portable)
        if args.command == 'status':
            result = manager.status()
            result = {k: v for k, v in result.items() if k not in ('files', 'cached_versions')}
        elif args.command == 'uninstall':
            result = manager.uninstall()
        else:
            result = {k: v for k, v in manager.install(update=args.command == 'update').items()
                      if k not in ('files', 'cached_versions')}
            result['result'] = 'installed' if args.command == 'install' else 'updated'
            if not result.get('runtime_ready'):
                result['result'] = 'needs_hook_review' if result.get('needs_hook_review') else 'runtime_not_ready'
                result['next_step'] = ('在同一 Codex 账户运行 codex，输入 /hooks，仅审查并信任 '
                                       + manager.plugin_id + ' 的 UserPromptSubmit 和 Stop；随后运行 status 检查 runtime_ready。')
            elif args.migrate_project:
                result['project_transition'] = manager.replace_project(args.migrate_project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('result') in ('needs_hook_review', 'runtime_not_ready') else 0
    except (InstallError, RPCError, OSError, ValueError, RuntimeError) as error:
        print(json.dumps({'result': 'error', 'message': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
