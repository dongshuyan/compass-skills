# Agent Clarity: Codex session titles

Agent Clarity 0.5.0 maintains a title such as `验证中｜会话标题自动化｜检查手动改名保护`: status, the user's initial request, and current progress. The initial request stays stable while the other segments follow actual progress. Manually edited segments are preserved; an external title that cannot be safely split pauses automatic updates.

This is an optional **Codex plugin** with a bundled Skill, two lifecycle hooks, Python scripts, and a scoped installer. The ten portable packages under `skills/` use their usual installation flow. Installing those packages with `npx skills add` does not install this plugin or its hooks. Its internal `manage-title` Skill depends on the rest of the plugin and is excluded from normal skills CLI discovery, including full-depth discovery (verified with skills CLI 1.5.25).

## Requirements

- Tested on macOS. Linux is expected to work based on the POSIX interfaces used, but has not been exercised for this snapshot. Windows is unsupported.
- Python 3.11 or later, Git, and a local Codex CLI exposing the plugin, hooks, and app-server interfaces used by the installer.
- A trusted Git root for project installation. Account-global installation also supports non-Git working directories.
- User review of the two hook definitions in the same Codex home where they will run.

The runtime uses only Python's standard library, including POSIX `fcntl` and `select`. The `python3` resolved by Codex's hook environment must also be 3.11 or later; running the installer with a separate newer interpreter does not change the hook command. `status` checks loading and trust, not the hook interpreter's version. CLI interfaces can change; see [the current verification record](../PUBLICATION_AUDIT.md#2026-10-30-addition) for the tested version and limits. Distribution from this repository is separate from submission to OpenAI's universal public plugin directory.

## Install in one scope

Clone the repository, then run its installer:

```sh
git clone https://github.com/dongshuyan/compass-skills.git
cd compass-skills

# Only this trusted Git project
python3 scripts/title_plugin.py install --project /absolute/path/to/project

# Or all directories in the current Codex home
python3 scripts/title_plugin.py install --global
```

Choose one scope. `--global` means the current `CODEX_HOME`, or the default `~/.codex` when that variable is unset. It does not discover other accounts or install across machines. Opening this repository alone does not activate title management.

The installer deploys a self-contained plugin, registers a scoped local marketplace, and adds managed configuration and title instructions. It preserves unrelated configuration and makes backups. An existing deployment or cache with local changes is retained rather than silently overwritten.

Project installation writes `.codex/config.toml`, a managed block in `AGENTS.md`, `.local/` deployment/state/backups, and an ignore entry in `.gitignore`; Codex also keeps an account-side plugin cache and coordination lock. The generated configuration and rule blocks contain local paths, so keep them out of shared commits. Uninstall leaves the `/.local/` ignore entry in place. An exactly matching legacy `.codex/hooks.json` title file can be backed up and removed during migration; modified legacy definitions stop the operation for review.

A first install normally returns `needs_hook_review` with exit code 2. In the **same Codex home**, open the CLI and run `/hooks`. Review the `UserPromptSubmit` and `Stop` entries belonging to the exact plugin ID printed by the installer, and trust those two definitions. Review any changed definitions again after an update. Project installation also requires Codex to trust the target project.

Check readiness, matching the original scope:

```sh
python3 scripts/title_plugin.py status --project /absolute/path/to/project
python3 scripts/title_plugin.py status --global
```

Use the command for the scope you installed. Confirm `runtime_ready: true`, with both hook entries enabled and `trusted` or policy-managed. Restart Codex or open a new session so the installed plugin is loaded. Try a short question, then continue the conversation. Verify the title itself; successful installation alone does not prove that a model has executed the title instructions.

Do not install just the plugin folder through another marketplace and expect it to activate: the scoped installer also creates the activation and protection records that the runtime requires. Do not copy `plugins/clarity-session-titles/skills/manage-title/` into a general skill directory. Explicitly opting into internal skills in a generic installer still does not deploy this plugin's dependencies.

## How it works

1. `UserPromptSubmit` records the turn and supplies a reminder, including for short answers that need no other tools.
2. The Agent chooses the title's meaning and calls the bundled `title_runtime.py`. It uses the current `CODEX_THREAD_ID`, checks the scope, merges protected segments, calls `thread/name/set`, and reads the name back through `thread/read`.
3. `Stop` checks whether this turn completed the title check. If it was missed, it requests at most one repair. Errors, uncertain writes, and paused protection do not cause an endless repair loop.

The hooks prompt and verify; they do not independently infer the user's task. Model compliance remains necessary. The runtime uses Codex's API and does not use a direct SQLite-writing fallback. It only manages the caller's conversation and excludes internal subagents. Global mode can manage existing chats when continued; project mode only admits root chats created after that project's activation.

Two description segments are limited to 28 characters each. Generated status words are Chinese: `讨论中`, `调研中`, `方案中`, `实现中`, `验证中`, `待确认`, `待验证`, `已完成`, `已暂停`, and `受阻`. Ending an answer does not by itself mean the task is complete.

## Optional shared installation for Codex/Harbor homes (advanced)

Harbor is a local Codex account/window manager used by the original installation. This shared-state mode has unit coverage, but this COMPASS snapshot has not repeated a live cross-home run.

Use this only when you want multiple local Codex homes to share one activation record and title-protection state. Choose a persistent directory on an internal disk; it must survive account switching and temporary-instance cleanup. For example:

```sh
CLARITY_SHARED_HOME="$HOME/.local/share/agent-clarity/codex"
mkdir -p "$CLARITY_SHARED_HOME"
CODEX_HOME="$CLARITY_SHARED_HOME" python3 scripts/title_plugin.py install --global --portable
```

The deployed package receives a generated `global-installation.json` binding to this state root. Keep that file local. Complete hook review in this home, then configure each intended consumer home to load the **same** local marketplace returned in the installer's `source` field and enable the returned `plugin_id`. The marketplace name is the part after `@` in that ID. The equivalent user-config entries are:

```toml
[marketplaces."<marketplace-name>"]
source_type = "local"
source = "/absolute/marketplace/path/from/source"

[plugins."clarity-session-titles@<marketplace-name>"]
enabled = true
```

Merge these into that home's existing `config.toml`; preserve unrelated settings. Review the two definitions through `/hooks` in **each** intended home, then restart its Codex instance. Harbor's configuration inheritance is intended to carry this marketplace into new homes; verify discovery and trust in each intended home. The installer itself neither discovers accounts nor changes their login or model-routing configuration.

Before migrating an existing title installation, retain its `.local/titles/` protection records and disable its old title plugin so duplicate hooks cannot race. The installer supports `--migrate-project` for a project-to-global transition:

```sh
python3 scripts/title_plugin.py install --global --migrate-project /absolute/path/to/project
```

Migration runs only after `runtime_ready` is true. If the first command returns `needs_hook_review`, complete the hook review and then rerun the migration flag:

```sh
python3 scripts/title_plugin.py update --global --migrate-project /absolute/path/to/project
```

For shared mode, prefix both migration commands with the same `CODEX_HOME="$CLARITY_SHARED_HOME"` used for its installation.

General account-to-shared-state migration is not automated here. Reinstalling separately in each consumer home creates separate state roots. Do not copy credentials or assume it creates a shared installation. Shared runtime packages verify their full file digests against the shared installation receipt before participating.

## Update and uninstall

Use the same scope and Codex home as the original installation:

```sh
git pull --ff-only
python3 scripts/title_plugin.py update --global
python3 scripts/title_plugin.py status --global
python3 scripts/title_plugin.py uninstall --global
```

For a project installation, replace `--global` with `--project /absolute/path/to/project`. For a shared installation, run these commands with the same `CODEX_HOME="$CLARITY_SHARED_HOME"` prefix. An update can require hook review again.

Uninstall disables that installation and removes its owned configuration, rules, and unchanged deployed files/cache. Existing titles, protection records, backups, and user-modified files are preserved. Disabling a shared root stops title maintenance for its consumers, but uninstall does not discover or remove configuration/cache entries from every consumer home; review those homes separately. An independently installed project is retained unless explicitly migrated.

## State, privacy, and limits

Project state and backups live under the selected project's `.local/`. Account-global state lives under `CODEX_HOME/agent-clarity/`. Shared mode uses the fixed root in the generated binding. This repository ignores local state and generated bindings; it contains no deployed account state, conversation logs, credentials, or personal installation paths.

The runtime reads conversation metadata with `includeTurns: false` and stores the title-protection and turn-check records locally. It does not extract or copy authentication files. It launches the existing Codex CLI for local API calls, without adding a separate model service. Keep backups and shared state in a directory you control.

Successful API write/readback does not prove immediate desktop-sidebar refresh. Codex does not provide a conditional name-set operation that atomically excludes a simultaneous manual rename; local locks coordinate this plugin's writers, while a desktop edit can still race. A late native auto-title can be observed as an external edit. Check actual names, hook readiness, and turn records before attributing a failure to UI refresh.

## Checks

From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 tests/live_plugin_lifecycle.py --execute
```

The unit suite uses isolated state and API doubles for runtime failure and concurrency cases. The lifecycle script uses real Codex plugin discovery in a disposable, unauthenticated home and makes no model calls. It records local evidence under `.local/plugin-integration/`; it does not install into your current account. The tests and their limits are recorded in [the publication audit](../PUBLICATION_AUDIT.md#2026-10-30-addition).

## Sources and contribution

We thank [panda-z519/agent-session-titles](https://github.com/panda-z519/agent-session-titles). This implementation substantially reuses its work. The comparison below is against the fixed [2d931a54a736a57c23a3e9a7fcfca56031dfd5f3 snapshot](https://github.com/panda-z519/agent-session-titles/tree/2d931a54a736a57c23a3e9a7fcfca56031dfd5f3), rather than a claim about what upstream's current version supports.

| Origin | Included work |
| --- | --- |
| Copied from upstream | `parse_three_part_title`, `protected_segments`, and `merge_protected_title` in `title_segments.py`. |
| Design and guidance adapted from upstream | The three-part format, per-segment manual-edit protection, lifecycle prompting pattern, manual-edit reconciliation, and `manage-title` Skill guidance. |
| Added in Agent Clarity | Scoped project/global installation, update/removal and backups; API-only writes with readback and uncertain-write handling; per-turn checks with at most one repair; scope handover and concurrent-write coordination; explicitly shared Codex/Harbor state with bundle checksums. |
| Added for COMPASS distribution | Public installer/docs/tests, an internal-skill marker and missing-package guidance, and relocation/discovery verification while preserving the existing ten portable skills. |

The upstream MIT notice is retained verbatim in [LICENSES/agent-session-titles.txt](../plugins/clarity-session-titles/LICENSES/agent-session-titles.txt). Original additions use the repository's MIT license, also included inside the plugin bundle. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). No upstream endorsement is implied.

Packaging and hook-review references: [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins), [Codex Hooks](https://learn.chatgpt.com/docs/hooks), and the [skills CLI source](https://github.com/vercel-labs/skills).
