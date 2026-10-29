# Publication Audit

Initial audit date: 2026-08-25. The [2026-10-30 addition](#2026-10-30-addition) records the latest integration checks; the [2026-10-19 addition](#2026-10-19-addition) and earlier results below retain their original scope.

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

## 2026-10-19 addition

### Scope

- Added the independent Clear Communication skill, its original hypothetical examples, optional host interface metadata, design-source notes, and two retained upstream MIT notices.
- Kept the core instructions and examples byte-identical to the existing writing skill. The original project and user-level installation remain unchanged.
- Updated all three README files, the agent adapter, and the skill catalogue to include ten released skills.
- Reviewed the existing candidate-age changes: explicit self-reported age takes precedence, partial birth dates retain the appropriate precision, and a labeled assumption-based estimate is displayed while audit bounds remain available.
- Fixed the self-reported-age display validator so that a structured age of 27 cannot validate a display of 127, a conflicting age, a fractional age, or a negative age. Added a regression test that failed before the fix and passed afterward.
- Included seven existing suitcase-example screenshots after visual and PNG-metadata inspection. They illustrate conversations rather than establish model-performance differences.

### Checks completed

- Candidate assessment: 83 tests passed on Python 3.11 and Python 3.14. The suite includes public-package privacy checks, Python 3.10 syntax parsing, age and portrait contracts, report generation, and offline report validation.
- Ruff passed for the candidate scripts and tests. The report template's executable inline JavaScript passed Node syntax checking.
- Clear Communication passed the repository's structural package validator with no errors or warnings, and both changed skill packages passed the Skill structure validator using the existing Python 3.11 environment.
- All repository JSON files parsed; the catalogue names exactly match the ten released skill directories. Local Markdown links in the changed documentation and new skill files resolve.
- With skills CLI 1.5.23, local discovery found ten skills. Copy installation into isolated Codex and Claude Code project directories preserved all six Clear Communication package files byte for byte, including source and license notes.
- Codex 0.163.0-alpha.10.2 discovered the temporary package as an enabled repository skill through its native skills-list interface.
- Claude Code 2.1.296 listed the temporary package as a project skill through its native initialization interface, using an isolated configuration directory with hooks disabled. Neither native check sent a model task.
- New writing instructions and changed documentation were checked for machine-specific user paths. The core instructions and examples contained no email address or credential assignment. The seven screenshots showed no private identity, contact detail, or local path, and contained no text or EXIF metadata.
- Source revisions and MIT notices were verified against the inspected upstream checkouts. The Federation definition is linked through Clarity's institutional page; the older reference URL was not reused after it returned unrelated content during this audit.

### Remaining boundaries

These checks establish package structure, installation, native discovery, and the tested candidate-report behavior. They do not measure reader comprehension, test automatic skill selection on real model tasks, or establish behavior across all Harnesses.

No physical Windows or Linux host was used. The previously pending independent browser visual review of the candidate portrait layout remains pending; this update checked its template syntax and existing render and offline contracts.

## 2026-10-30 addition

Scope: the optional Agent Clarity 0.5.0 Codex title plugin under `plugins/clarity-session-titles/`, its installer and compatibility imports under `scripts/`, the title-specific `tests/`, `docs/session-titles.md`, and repository documentation. The existing ten portable skills are unchanged. The earlier portability statements in this audit apply to those skills; the title plugin uses POSIX interfaces, is tested on macOS, is expected but not exercised on Linux, and does not support Windows.

The plugin runtime and installer were copied from the existing 0.5.0 implementation without importing local account state or development logs. Distribution changes add the COMPASS MIT license to the bundle, mark the plugin-only Skill as internal for the generic skills CLI, and explain how to recover from an incomplete standalone Skill installation. The real lifecycle test derives its upgrade version from the manifest. Opening this repository or installing its portable skills does not activate the plugin.

Checks performed on macOS:

- The source implementation's 114 title-specific tests passed before integration. The copied suite plus relocation and bound-source safety regressions passes 116 tests on Python 3.11 and Python 3.14. The relocation test deploys from a checkout with spaces in its path and starts the deployed runtime after the original checkout path changes. A bound-source regression first reproduced a lifecycle test creating state outside its disposable Codex home (inside a temporary sentinel fixture); the lifecycle script now rejects a generated source binding before creating any state, and unit fixtures explicitly isolate runtime bindings.
- `python3 tests/live_plugin_lifecycle.py --execute` passed 22 checks with Codex `0.165.0-alpha.1.2`. It uses a disposable, unauthenticated home and real local plugin discovery. Checks cover project separation, same-version refresh, manifest-derived version upgrade, preservation of activation time and user configuration, removal/reinstallation, global discovery across two Git projects and a non-Git directory, untrusted-hook readiness, and project-to-global handover. It does not bypass hook trust or call a model.
- `skills@1.5.25` lists ten portable skills in ordinary, full-depth, and wildcard/full-depth modes. The internal plugin Skill is excluded in each case. `INSTALL_INTERNAL_SKILLS=1` explicitly exposes it; the plugin Skill contains guidance for a missing full package. A wildcard/full-depth copy install into disposable Codex and Claude Code project roots preserves all tracked files of the ten skills byte for byte and does not install hooks.
- Ruff's fatal/undefined-name checks (`E9,F63,F7,F82`) pass for the title scripts, plugin, and tests. All new Python files parse with Python 3.11 syntax, and plugin/hook JSON plus `skills.sh.json` parse successfully. This is not a full style cleanup of the imported implementation.
- The three copied helpers are AST-identical to the pinned upstream functions. The retained upstream MIT notice is byte-identical to that revision's `LICENSE`. Attribution describes the three-part format, segment protection and prompting pattern as upstream work, distinguishes copied/adapted code from Agent Clarity additions, and does not imply endorsement.

This integration does not reinstall the live title plugin or migrate real accounts. The runtime's shared-state behavior remains covered by the imported unit tests; no new live multi-account/model run or desktop-sidebar visual acceptance was performed for this snapshot. Local lifecycle evidence stays in ignored `.local/plugin-integration/`, outside the public source files. A successful local check does not establish remote publication.
