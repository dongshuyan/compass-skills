# COMPASS Agent Adapter

This repository contains agent-agnostic `SKILL.md` skills. Use this file when your agent does not have native skills support, or when it needs explicit rules for discovering and applying the skills in `skills/`.

## Discovery

- Available skills live under `skills/<skill-name>/SKILL.md`.
- Read each skill's YAML frontmatter `name` and `description` to decide whether it applies.
- Prefer explicit user invocation such as `$task-clarifier`, `$task-forest`, `$session-handoff-prompt`, `$user-profile-keeper`, `$run-history-skill-builder`, or `$run-history-skill-upgrader`.
- If no skill clearly applies, continue normally; do not force a skill.

## Loading Protocol

When a skill applies:

1. Read the full `SKILL.md` before acting.
2. Resolve relative paths from the directory that contains that `SKILL.md`.
3. Read referenced files under `references/` only when the skill tells you to or when the current task needs them.
4. Run scripts from the skill's own `scripts/` directory instead of retyping large logic.
5. Keep generated runtime data out of the repository unless the user explicitly asks to commit it.

## Invocation Examples

```text
Use $task-clarifier to align this task before implementation.
Use $task-forest to update the task graph for this workspace.
Use $session-handoff-prompt to create a continuation prompt for a fresh session.
Use $user-profile-keeper to initialize or update my local profile.
Use $run-history-skill-builder to turn this completed workflow into a new skill package.
Use $run-history-skill-upgrader to plan a safe upgrade for this existing skill from recent run evidence.
```

## Local Paths

- `task-forest` writes task data under the current workspace: `.agent-workbench/task-forest/`.
- `session-handoff-prompt` is read-only by default. It may validate local handoffs with real workspace paths or redact shareable handoffs.
- `user-profile-keeper` writes profile data under the local user home: `.compass-skills/user-profiles/v1/`.
- `run-history-skill-builder` writes new skill packages only to a user-approved local directory.
- `run-history-skill-upgrader` is plan-only by default and edits existing skills only after explicit approval.
- Set `COMPASS_USER_PROFILE_HOME` to override the profile directory.
- Set `COMPASS_AGENT_NAME` to label task-forest changes by agent, for example `codex`, `claude-code`, `opencode`, or `openclaw`.

## Safety Rules

- Do not upload profile data, task data, credentials, cookies, browser sessions, or private local logs.
- Do not read password managers, keychains, SSH keys, browser cookies, API keys, tokens, or verification codes.
- Do not save secrets in user profiles or task graphs.
- Before destructive actions, publishing, remote writes, global configuration changes, credential use, or external side effects, ask for explicit user confirmation.
- Treat HTML exports as static offline views; they do not authorize modifying the task graph.

## Cross-Agent Notes

- Codex, Claude Code, OpenClaw, OpenCode, and similar local agents may expose different skill directories and invocation syntax.
- The portable contract is the file layout: `SKILL.md` plus optional `references/`, `scripts/`, `assets/`, and `agents/`.
- If your agent has no automatic skill router, use this `AGENTS.md` as the router policy.
