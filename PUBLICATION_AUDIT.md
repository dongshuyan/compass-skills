# Publication Audit

Audit date: 2026-06-15

Scope:

- `skills/user-profile-keeper`
- `skills/task-forest`
- `skills/task-clarifier`
- root README files, security note, and visual assets

## Sanitization

- Removed maintenance logs and runtime caches.
- Removed installed-machine paths and user-specific paths from public documentation.
- Replaced fixed installed-skill command examples with `<skill-dir>` placeholders.
- Changed the default user-profile storage path to `<home>/.compass-skills/user-profiles/v1`.
- Generalized task-forest validation sample data and UI title-shortening rules.
- Generalized Codex-first wording and defaults into agent-agnostic `SKILL.md` usage, with `COMPASS_AGENT_NAME` for actor labeling and `COMPASS_USER_PROFILE_HOME` for profile storage overrides.
- Added public visual assets. Live task-forest screenshots were re-encoded with semantic filenames; raw source screenshot filenames are excluded by `.gitignore`.
- Added explicit plaintext local-storage warnings for `user-profile-keeper` and clarified that `task-clarifier` works with or without a profile.

## Local-First Boundaries

- `user-profile-keeper` writes only to local profile storage.
- `task-forest` writes only to the current workspace's `.agent-workbench/task-forest/` directory and an optional lightweight local registry.
- `task-clarifier` is instruction-only and does not persist data.
- No released skill uploads profile data, task data, credentials, cookies, or browser sessions.

## Validation Run

Commands run from the package parent:

```bash
python3 <skill-creator-dir>/scripts/quick_validate.py compass-skills/skills/task-forest
python3 <skill-creator-dir>/scripts/quick_validate.py compass-skills/skills/task-clarifier
python3 <skill-creator-dir>/scripts/quick_validate.py compass-skills/skills/user-profile-keeper
python3 -m py_compile compass-skills/skills/task-forest/scripts/task_forest.py compass-skills/skills/task-forest/scripts/validate_task_forest_export.py compass-skills/skills/user-profile-keeper/scripts/profile_store.py compass-skills/skills/user-profile-keeper/scripts/onboarding_webui.py compass-skills/skills/user-profile-keeper/scripts/smoke_test_onboarding.py
python3 compass-skills/skills/task-forest/scripts/validate_task_forest_export.py --skill-dir compass-skills/skills/task-forest
COMPASS_USER_PROFILE_HOME=<temp>/profile python3 compass-skills/skills/user-profile-keeper/scripts/profile_store.py init --user default
COMPASS_USER_PROFILE_HOME=<temp>/profile python3 compass-skills/skills/user-profile-keeper/scripts/profile_store.py read --user default --view clarification_summary
COMPASS_USER_PROFILE_HOME=<temp>/profile python3 compass-skills/skills/user-profile-keeper/scripts/smoke_test_onboarding.py
```

Results:

- Skill validation: passed for all three skills.
- Python compile check: passed.
- Task-forest clean-room export validation: passed.
- User-profile keeper init/read smoke check: passed.
- Onboarding smoke tests: passed.

## Scan Notes

Secret/path scans were run across Markdown, Python, YAML, and SVG files. Remaining intentional matches:

- `127.0.0.1` in `onboarding_webui.py` and questionnaire docs: local-only Web UI binding.
- private-key, provider-token, and credential-like patterns in `onboarding_webui.py`: secret redaction detectors, not real secrets.
- `token` in `task_forest.py`: random local lock token, not a credential.
- `private` / `secret` in docs: privacy boundary terminology.

No personal path, real credential, browser-cookie access, remote publish action, or runtime cache remains in the package.
