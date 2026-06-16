# COMPASS Skills

[中文](README.zh.md) · [Security](SECURITY.md) · [License](LICENSE)

```bash
npx skills add dongshuyan/compass-skills --skill '*' -a claude-code
```

COMPASS Skills gives AI coding agents three local skills: task clarification, repo-local task memory, and a local collaboration profile.

The project currently ships three `SKILL.md` skills:

| Skill | Purpose |
| --- | --- |
| [`task-clarifier`](skills/task-clarifier/) | Aligns goals, scope, evidence, acceptance criteria, and risk boundaries before ambiguous, costly, or externally visible work. |
| [`task-forest`](skills/task-forest/) | Maintains a repo-local task forest / DAG with goals, subtasks, dependencies, progress, deviations, todos, decisions, and session history. |
| [`user-profile-keeper`](skills/user-profile-keeper/) | Maintains a local, auditable, correctable collaboration profile for communication preferences, risk style, and recurring working context. |

## Quick Start

List the available skills before installing:

```bash
npx skills add dongshuyan/compass-skills --list
```

Install all skills for Claude Code:

```bash
npx skills add dongshuyan/compass-skills --skill '*' -a claude-code
```

Install all skills for both Codex and Claude Code:

```bash
npx skills add dongshuyan/compass-skills --skill '*' -a codex -a claude-code
```

After installation, invoke the skills directly in a session:

```text
$task-clarifier
$task-forest
$user-profile-keeper
```

For manual installation, copy the three folders under [`skills/`](skills/) into the agent's local skills directory and keep their `references/`, `scripts/`, and `agents/` subdirectories intact.

## Why COMPASS Exists

Long-running agent work needs three kinds of state:

- User context: communication preferences, risk boundaries, recurring omissions, and collaboration style.
- Project context: where the current request fits, what it depends on, and how far it has progressed.
- Goal context: how the current task contributes to the original objective and whether it still matches it.

COMPASS organizes that state into three local workflows:

1. A local profile that the user can inspect and correct.
2. A repo-local task graph that survives session boundaries.
3. A clarification gate before ambiguous or risky execution.

## How The Three Skills Work Together

`task-clarifier` is the entry point for ambiguous, high-cost, high-risk, evidence-sensitive, or externally visible work. It first identifies the user-owned decisions that must be made, asks 1-3 focused questions with recommended answers, confirms shared understanding, and only then searches or executes.

`task-forest` records long-running work structure: why a task exists, where it fits, how far it progressed, what changed, and what remains unresolved.

`user-profile-keeper` stores collaboration preferences locally. Future sessions use the profile to ask relevant questions and apply the right risk boundary. Current files, logs, and user-provided context remain the authority; secrets stay out of the profile.

```text
user-profile-keeper -> who is the user and how should we collaborate?
task-forest         -> where does this task fit and is it still aligned?
task-clarifier      -> what should the agent do now?
```

## Screenshots

Task forest HTML export:

![task-forest tree demo](assets/task-forest-demo.gif)

Live DAG view:

![task-forest live DAG view](assets/task-forest-live-dag.png)

Task detail view:

![task-forest live detail view](assets/task-forest-live-detail.png)

User profile and alignment flow:

![COMPASS user profile and alignment flow](assets/profile-alignment-flow.en.png)

Ecosystem map:

![COMPASS skills ecosystem DAG](assets/compass-system-map.en.svg)

## Compatibility

COMPASS works across agent runtimes as a `SKILL.md` package with Markdown instructions, YAML frontmatter, optional `references/`, optional `scripts/`, and optional agent metadata.

| Agent / environment | Recommended setup |
| --- | --- |
| Claude Code | Use `npx skills add dongshuyan/compass-skills --skill '*' -a claude-code`, or copy the folders under `skills/` into Claude Code's custom skills directory. |
| Codex | Use the `skills` CLI with `-a codex` when supported by your environment, or use the repo as a local skills source. |
| OpenCode / OpenClaw / other agents | Keep [`AGENTS.md`](AGENTS.md) and load the matching `SKILL.md` first, then use `references/` and `scripts/` as needed. |

The scripts use Python standard-library components and run locally.

## Safety Model

COMPASS keeps runtime data local:

- No upload of task data or user-profile data.
- No browser cookie, token, private key, credential, or session extraction.
- `task-forest` stores task data under the current workspace, usually `.agent-workbench/task-forest/`.
- `user-profile-keeper` stores local profile data under `.compass-skills/user-profiles/v1` by default, or a user-selected `COMPASS_USER_PROFILE_HOME`.
- High-risk actions such as deletion, overwrite, publishing, remote writes, credential use, and global configuration changes require explicit confirmation.

Important: `user-profile-keeper` uses local plaintext storage without encryption. Do not store passwords, tokens, private keys, verification codes, or highly sensitive personal data in the profile.

See [SECURITY.md](SECURITY.md) for the security boundary.

## Example Prompts

Clarify a task before execution:

```text
Use $task-clarifier to align the task below.

Task: ...
Material: ...
Constraints: ask user-owned decisions first; infer discoverable facts from files, context, or reliable sources. Ask only questions that change scope, method, evidence, format, safety, or acceptance criteria.
Output: ask 1-3 key questions with recommended answers first; once the core need is clear, restate your understanding in 2-5 lines and ask me to confirm.
```

Maintain the task forest for a workspace:

```text
Use $task-forest to analyze the current session and maintain the task forest for this workspace.

Goal: create a task-forest proposal from long-running goals, tasks, progress, deviations, risks, decisions, and follow-ups in this session.
Requirements:
1. Read the current task-forest list and todo first; initialize task-forest if missing.
2. Identify which long-term goal this session served. If no relation is clear, ask me or create a question/risk node.
3. Save a proposal and show me the planned changes before applying.
4. After approval, apply, validate, export, and report the HTML path.
```

Initialize a local user profile:

```text
Use $user-profile-keeper to initialize my local user profile.

Goal: build an auditable, correctable, retractable profile from a local questionnaire or the current context.
Boundaries:
1. Store locally only. Do not upload anything or read browser cookies, tokens, or credentials.
2. Do not save secrets, passwords, private keys, verification codes, or browser-session information.
3. Put inferred, private, sensitive, or conflicting claims into pending proposals for my review.
4. Report what was saved, proposed, skipped, or redacted.
```

## Validation Status

The public install path has been validated with `skills@1.5.11`:

- `npx skills add dongshuyan/compass-skills --list` finds all 3 skills.
- `npx skills add dongshuyan/compass-skills --skill '*' -a claude-code --copy -y` installs all 3 skills into a temporary project's `.claude/skills/` directory.

## Roadmap

Planned additions:

- Build reusable skills from real task histories.
- Upgrade existing skills from observed failures, feedback, and validation evidence.
- Generate restart prompts for long sessions using `task-forest` as structured context.
- Summarize local agent states, waiting-human items, risks, and review queues.
- Recommend low-switching-cost follow-up tasks from the task graph.

## License

MIT. See [LICENSE](LICENSE).

## Community

The project is developed publicly at [dongshuyan/compass-skills](https://github.com/dongshuyan/compass-skills).

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=dongshuyan/compass-skills&type=Date)](https://www.star-history.com/#dongshuyan/compass-skills&Date)
