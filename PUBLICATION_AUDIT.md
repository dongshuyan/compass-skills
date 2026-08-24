# Publication Audit

Audit date: 2026-08-25

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
- Added a canonical PNG-only portrait pipeline: extracted rasters must be converted and visually rechecked, dimensions are bounded before decompression, pixel data is validated, and non-display metadata plus trailing bytes are removed. JPEG is rejected instead of being trusted through segment-only parsing; no candidate image is stored in the released package.
- Added display-only timeline age ranges with fixed assumptions, explicit provenance, and year-only graduation fallback. Structured validators reject explicit age and appearance signals from fit and scoring fields; policy review remains required for indirect semantic paraphrases.

## Local-First Boundaries

- `user-profile-keeper` writes only to local profile storage.
- `task-forest` writes only to the current workspace's `.agent-workbench/task-forest/` directory and an optional lightweight local registry.
- `task-clarifier` is instruction-only and does not persist data.
- `session-handoff-prompt` is read-only by default.
- `run-history-skill-builder` reads only user-authorized workflow history and writes new skill files only to a user-approved local directory.
- `run-history-skill-upgrader` is plan-only by default and edits existing skills only after explicit approval of a concrete plan.
- `assess-interview-candidate` writes pseudonymous case data and offline reports only below a user-approved local root. It does not upload resumes, reports, or interview records.
- Candidate-provided age and separately labeled timeline-age estimates, along with birthplace, hometown, marital status, and location, can appear in the interviewer overview but cannot enter fit scoring, ranking, hiring, rejection, or stability predictions.
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
- `assess-interview-candidate`: 77 tests passed on Python 3.11 and Python 3.14.
- Skill structure, Ruff, Python 3.10 syntax parsing, JSON parsing, JavaScript syntax, and offline HTML contract validation passed.
- The current portrait-layout update was not independently re-run in a live browser because the available browser rejected local-file navigation; its DOM generation and interactions remain covered by render and contract tests, and live visual verification is still pending.
- Local install discovery with `skills@1.5.23` found eight released skills. A temporary copy install of `assess-interview-candidate` succeeded for Codex and Claude Code.
- Windows and Linux support is contract- and test-backed but was not exercised on physical Windows or Linux hosts in this audit.
- Repository manifests and docs now reflect eight released skills.

## Scan Notes

Path/privacy scans were run across Markdown, Python, YAML, and JSON files. Intentional remaining matches are limited to:

- generic safety words such as `token`, `credential`, or `cookie` in privacy-boundary documentation;
- `<skill-dir>`-style placeholders in portable command examples;
- references to Codex or Claude Code as supported hosts, not as mandatory runtime assumptions.
- synthetic Windows, macOS, Linux, UNC, and WSL path strings inside `tests/test_public_package.py`, used only to verify the privacy scanner.
- synthetic email, mobile-phone, identity-number, and image-metadata values inside the test files, used only to verify that interviewer-facing data rejects or strips those fields.

No personal absolute path, real candidate identity, contact detail, credential, browser-session export, remote publish action, or private maintenance record remains in `assess-interview-candidate`.
