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
- The skills do not upload profile data, task data, credentials, or browser session information.

## Sensitive Data Rules

These skills must not save:

- API keys, tokens, passwords, private keys, verification codes, or cookies.
- Browser session data.
- Raw sensitive or intimate evidence.
- Unconfirmed sensitive inferences.

`user-profile-keeper` may store private background information only when the user explicitly provides or confirms it. Other skills should only read the low-risk `clarification_summary` view.

Users should decide whether local plaintext profile storage is acceptable for their device, account model, backup tools, and threat model before using `user-profile-keeper`. Do not store secrets or highly sensitive personal information in the profile.

## External Side Effects

The released skills do not publish, push, upload, email, schedule, or remotely write anything by themselves. If an agent uses these skills while a user asks for an external side effect, the agent should require explicit user confirmation before the final action.

## Local Files

- Task graph writes must go through `task-forest/scripts/task_forest.py`.
- Profile writes must go through `user-profile-keeper/scripts/profile_store.py`.
- New skill-package writes must stay inside the user-approved target directory chosen for `run-history-skill-builder`.
- Existing-skill edits from `run-history-skill-upgrader` must stay inside the user-approved target skill scope and happen only after plan approval.
- Session handoff prompts can preserve local workspace paths for same-machine continuation. Use `session-handoff-prompt/scripts/redact_handoff.py --privacy shareable` before sharing a handoff outside the local machine or trusted agent session.
- HTML task-forest exports are static offline views and do not modify the task graph.

## Reporting Issues

Before reporting a security issue publicly, remove private paths, profile content, task graph content, tokens, and local logs from the report.
