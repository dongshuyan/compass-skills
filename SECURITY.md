# Security And Privacy

COMPASS is designed as a local-first skills system.

## Data Boundaries

- `user-profile-keeper` stores profile data locally under `.compass-skills/user-profiles/v1` in the user's home directory by default.
- Profile storage is plaintext local storage. It is not encrypted by default and should not be treated as a secure vault.
- `task-forest` stores task data inside the current workspace under `.agent-workbench/task-forest/`.
- `session-handoff-prompt` is read-only by default. It creates continuation prompts from the current conversation, explicit transcript/log files, workspace evidence, and optional task-forest exports.
- `task-clarifier` does not write persistent data.
- `run-history-skill-builder` reads only user-authorized workflow history and writes new skill files only to a user-approved local directory.
- `run-history-skill-upgrader` is plan-only by default. It reads existing skill files and run evidence, and it edits target skill files only after explicit approval of a concrete plan.
- `assess-interview-candidate` reads only recruiter-authorized candidate materials and optional, consent-bounded public professional sources. It writes pseudonymous case data and offline reports only below a user-approved local directory.
- The skills do not upload profile data, task data, credentials, or browser session information.

## Sensitive Data Rules

These skills must not save:

- API keys, tokens, passwords, private keys, verification codes, or cookies.
- Browser session data.
- Raw sensitive or intimate evidence.
- Unconfirmed sensitive inferences.

Candidate materials may contain personal data. `assess-interview-candidate` keeps phone numbers, email addresses, and precise addresses out of the interviewer report; it does not search for private life, family, health, financial, political, or religious information. Candidate-provided age and separately labeled, bounded timeline-age estimates, along with birthplace, hometown, marital status, and location details, may be displayed for interviewer reference but must not enter job-fit scoring, ranking, hiring, rejection, or stability predictions. Resume portraits are accepted only from the canonical local PDF copy, structurally validated, stripped of non-display metadata and trailing bytes, and never used for biometric or appearance analysis.

`user-profile-keeper` may store private background information only when the user explicitly provides or confirms it. Other skills should only read the low-risk `clarification_summary` view.

Users should decide whether local plaintext profile storage is acceptable for their device, account model, backup tools, and threat model before using `user-profile-keeper`. Do not store secrets or highly sensitive personal information in the profile.

## External Side Effects

The released skills do not publish, push, upload, email, schedule, or remotely write anything by themselves. If an agent uses these skills while a user asks for an external side effect, the agent should require explicit user confirmation before the final action.

## Local Files

- Task graph writes must go through `task-forest/scripts/task_forest.py`.
- Profile writes must go through `user-profile-keeper/scripts/profile_store.py`.
- New skill-package writes must stay inside the user-approved target directory chosen for `run-history-skill-builder`.
- Existing-skill edits from `run-history-skill-upgrader` must stay inside the user-approved target skill scope and happen only after plan approval.
- Candidate cases and reports from `assess-interview-candidate` must stay below the user-approved case root and outside the installed skill directory. Existing cases and reports are not overwritten by default.
- Session handoff prompts can preserve local workspace paths for same-machine continuation. Use `session-handoff-prompt/scripts/redact_handoff.py --privacy shareable` before sharing a handoff outside the local machine or trusted agent session.
- HTML task-forest exports are static offline views and do not modify the task graph.

## Optional Codex Session-Title Plugin

`clarity-session-titles` has a separate, opt-in installer. Installing the portable skills or opening this repository does not enable its hooks. The installer writes managed configuration/rules blocks, deployment files and local records, plus Codex's plugin cache and coordination lock. A project installation also adds `/.local/` to its `.gitignore`; uninstall leaves that ignore entry in place. It can remove an exactly matching legacy title-hook file after backing it up. Project configuration and rules can contain absolute local paths: keep their generated installation blocks out of shared commits. Review the two hook definitions through Codex `/hooks` before they run.

The runtime reads conversation metadata without turns and uses the local Codex API to set/read titles. Protection records, turn checks, and installation backups stay under the selected `.local/` or `CODEX_HOME/agent-clarity/`. Shared mode embeds a local absolute state-root binding in the deployed package; that generated binding and account state must never be committed. It does not discover accounts or copy credentials. Treat title text and local backups as potentially private.

API readback verifies persistence, not immediate desktop refresh. Locks coordinate the plugin's writers but cannot atomically exclude a simultaneous desktop rename. The hooks permit at most one repair request per turn and allow uncertain/error states to end the turn. See [installation and limits](docs/session-titles.md) before selecting a scope or changing an existing installation.

## Reporting Issues

Before reporting a security issue publicly, remove private paths, profile content, task graph content, tokens, and local logs from the report.
