# Security And Privacy

COMPASS is designed as a local-first skills system.

## Data Boundaries

- `user-profile-keeper` stores profile data locally under `.compass-skills/user-profiles/v1` in the user's home directory by default.
- `task-forest` stores task data inside the current workspace under `.agent-workbench/task-forest/`.
- `task-clarifier` does not write persistent data.
- The skills do not upload profile data, task data, credentials, or browser session information.

## Sensitive Data Rules

These skills must not save:

- API keys, tokens, passwords, private keys, verification codes, or cookies.
- Browser session data.
- Raw sensitive or intimate evidence.
- Unconfirmed sensitive inferences.

`user-profile-keeper` may store private background information only when the user explicitly provides or confirms it. Other skills should only read the low-risk `clarification_summary` view.

## External Side Effects

The released skills do not publish, push, upload, email, schedule, or remotely write anything by themselves. If an agent uses these skills while a user asks for an external side effect, the agent should require explicit user confirmation before the final action.

## Local Files

- Task graph writes must go through `task-forest/scripts/task_forest.py`.
- Profile writes must go through `user-profile-keeper/scripts/profile_store.py`.
- HTML task-forest exports are static offline views and do not modify the task graph.

## Reporting Issues

Before reporting a security issue publicly, remove private paths, profile content, task graph content, tokens, and local logs from the report.

