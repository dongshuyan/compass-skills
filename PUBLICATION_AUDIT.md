# Publication Audit

Audit date: 2026-07-08

Scope:

- `skills/user-profile-keeper`
- `skills/task-forest`
- `skills/task-clarifier`
- `skills/session-handoff-prompt`
- `skills/run-history-skill-builder`
- `skills/run-history-skill-upgrader`
- root README files, `AGENTS.md`, `SECURITY.md`, `skills.sh.json`, and visual assets

## Sanitization

- Removed internal-only maintenance notes from the released `run-history` upgrader package.
- Replaced installed-machine command examples with `<skill-dir>`, `<target-skill-dir>`, `<workspace>`, or host-tooling wording.
- Removed personal absolute paths, workspace-specific examples, and target names tied to private workflows.
- Reworked `run-history` examples and evals into generic browser-publishing, document-conversion, source-drift, and overfit-boundary cases.
- Kept `agents/openai.yaml` as optional interface metadata only; no release package depends on Codex-only runtime behavior.
- Kept validators and scripts on Python standard-library components only so they can run on macOS, Linux, and Windows.
- Preserved plan-only approval gates for the upgrader and output-directory locking for the builder.
- Kept per-skill `README` files out of the released packages to match the local tutorial and `skill-creator` packaging rules.

## Local-First Boundaries

- `user-profile-keeper` writes only to local profile storage.
- `task-forest` writes only to the current workspace's `.agent-workbench/task-forest/` directory and an optional lightweight local registry.
- `task-clarifier` is instruction-only and does not persist data.
- `session-handoff-prompt` is read-only by default.
- `run-history-skill-builder` reads only user-authorized workflow history and writes new skill files only to a user-approved local directory.
- `run-history-skill-upgrader` is plan-only by default and edits existing skills only after explicit approval of a concrete plan.
- No released skill uploads profile data, task data, credentials, cookies, or browser sessions.

## Validation Run

Representative validation was run from the package root:

```bash
python3 skills/run-history-skill-builder/scripts/validate_skill_package.py skills/run-history-skill-builder
python3 skills/run-history-skill-upgrader/scripts/validate_upgrade_artifacts.py --skill skills/run-history-skill-upgrader
python <skill-creator-dir>/scripts/quick_validate.py skills/run-history-skill-builder
python <skill-creator-dir>/scripts/quick_validate.py skills/run-history-skill-upgrader
python3 -m py_compile skills/run-history-skill-builder/scripts/validate_skill_package.py skills/run-history-skill-upgrader/scripts/validate_upgrade_artifacts.py
python3 -m json.tool skills/run-history-skill-builder/evals/evals.json
python3 -m json.tool skills/run-history-skill-upgrader/evals/evals.json
```

The existing released skills remain covered by the previous audit and validation notes. This audit extends that coverage to the two new `run-history` packages and the updated repository manifests.

## Results

- `run-history-skill-builder`: package validator passed.
- `run-history-skill-upgrader`: package validator passed.
- Codex `quick_validate.py`: both new skills passed.
- Python compile check: passed.
- Eval JSON parsing: passed.
- Repository manifests and docs now reflect six released skills.

## Scan Notes

Path/privacy scans were run across Markdown, Python, YAML, and JSON files. Intentional remaining matches are limited to:

- generic safety words such as `token`, `credential`, or `cookie` in privacy-boundary documentation;
- `<skill-dir>`-style placeholders in portable command examples;
- references to Codex or Claude Code as supported hosts, not as mandatory runtime assumptions.

No personal absolute path, real credential, browser-session export, remote publish action, or private maintenance record remains in the released `run-history` packages.
