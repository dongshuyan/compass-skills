# Publication Audit

Audit date: 2026-08-24

Scope:

- `skills/user-profile-keeper`
- `skills/task-forest`
- `skills/task-clarifier`
- `skills/session-handoff-prompt`
- `skills/run-history-skill-builder`
- `skills/run-history-skill-upgrader`
- `skills/academic-humanizer`
- `skills/assess-interview-candidate`
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
- Reviewed every file in `assess-interview-candidate`; no real candidate name, personal contact detail, private workspace name, credential, or machine-specific user path remains.
- Replaced fixed `python3` and Bash command examples with `<python>` and single-line argument forms. Added capability-based PDF, browser, and research guidance plus Windows, macOS, and Linux path rules.
- Kept `assess-interview-candidate/agents/openai.yaml` as optional interface metadata. The core `SKILL.md` does not require Codex, Claude Code, OpenAI, or another named host.

## Local-First Boundaries

- `user-profile-keeper` writes only to local profile storage.
- `task-forest` writes only to the current workspace's `.agent-workbench/task-forest/` directory and an optional lightweight local registry.
- `task-clarifier` is instruction-only and does not persist data.
- `session-handoff-prompt` is read-only by default.
- `run-history-skill-builder` reads only user-authorized workflow history and writes new skill files only to a user-approved local directory.
- `run-history-skill-upgrader` is plan-only by default and edits existing skills only after explicit approval of a concrete plan.
- `assess-interview-candidate` writes pseudonymous case data and offline reports only below a user-approved local root. It does not upload resumes, reports, or interview records.
- Candidate-provided age, birthplace, hometown, marital status, and location can appear in the interviewer overview but cannot enter fit scoring, ranking, hiring, rejection, or stability predictions.
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
python3.11 -B -m unittest discover -s skills/assess-interview-candidate/tests -p 'test_*.py' -v
python3.14 -B -m unittest discover -s skills/assess-interview-candidate/tests -p 'test_*.py' -v
ruff check --no-cache skills/assess-interview-candidate/scripts skills/assess-interview-candidate/tests
python <skill-creator-dir>/scripts/quick_validate.py skills/assess-interview-candidate
npx skills add . --list
npx skills --version
```

The existing released skills remain covered by earlier validation notes. This audit extends the current source-tree coverage to `assess-interview-candidate` and the updated repository manifests.

## Results

- `run-history-skill-builder`: package validator passed.
- `run-history-skill-upgrader`: package validator passed.
- Codex `quick_validate.py`: both new skills passed.
- Python compile check: passed.
- Eval JSON parsing: passed.
- `assess-interview-candidate`: 26 tests passed on Python 3.11 and Python 3.14.
- Skill structure, Ruff, Python 3.10 syntax parsing, JSON parsing, JavaScript syntax, offline HTML validation, and local browser interaction checks passed.
- Local install discovery with `skills@1.5.23` found eight released skills. A temporary copy install of `assess-interview-candidate` succeeded for Codex and Claude Code.
- Windows and Linux support is contract- and test-backed but was not exercised on physical Windows or Linux hosts in this audit.
- Repository manifests and docs now reflect eight released skills.

## Scan Notes

Path/privacy scans were run across Markdown, Python, YAML, and JSON files. Intentional remaining matches are limited to:

- generic safety words such as `token`, `credential`, or `cookie` in privacy-boundary documentation;
- `<skill-dir>`-style placeholders in portable command examples;
- references to Codex or Claude Code as supported hosts, not as mandatory runtime assumptions.
- synthetic Windows, macOS, Linux, UNC, and WSL path strings inside `tests/test_public_package.py`, used only to verify the privacy scanner.
- synthetic email, mobile-phone, and identity-number values inside `tests/test_interviewer_report.py`, used only to verify that interviewer-facing data rejects those fields.

No personal absolute path, real candidate identity, contact detail, credential, browser-session export, remote publish action, or private maintenance record remains in `assess-interview-candidate`.
