# COMPASS

[中文](README.md)

**司南: 个性化 AI 任务总控 Skills 系统**  
**COMPASS: Personal Alignment Skills OS for AI Agents**

COMPASS helps AI agents understand the user, see the full task landscape, and avoid goal drift. It combines a local user profile, a repo-local task graph, and an alignment router into a reusable skills system for long-running AI work.

## Understand It In 30 Seconds

**Use case 1: before a task starts, avoid doing the wrong thing.**
When a request is ambiguous, costly, or risky, use `$task-clarifier` to turn fuzzy intent into a shared executable requirement: the user understands what they want, the agent understands it the same way, and the user can verify that understanding. It does not ask more questions; it asks fewer, better questions that change the path.

**Use case 2: during and after work, turn progress into a task map.**
Use `$task-forest` to convert session goals, progress, deviations, dependencies, todos, and decisions into a proposal. After approval, it exports a tree view, DAG view, task detail cards, and a recommended queue so the next agent or next session knows why the task exists, what changed, and what to do next.

**Use case 3: over long-term collaboration, personalize without overreaching.**
Use `$user-profile-keeper` to store an auditable, correctable, retractable local collaboration profile. It does not save secrets or upload data; `task-clarifier` can read a low-risk summary to ask questions in a way that fits the user. Without a profile, `task-clarifier` still works normally and provides strong alignment.

Tree view and session update flow:

![task-forest tree demo](assets/task-forest-demo.gif)

Live DAG relationship view:

![task-forest live DAG view](assets/task-forest-live-dag.png)

Live task details, purpose, requirements, evidence, and scheduling:

![task-forest live detail view](assets/task-forest-live-detail.png)

User profile and alignment flow:

![COMPASS user profile and alignment flow](assets/profile-alignment-flow.en.png)

## Why COMPASS

Most agents are good at the current prompt. Long-running work fails in different ways:

- **No user model**: the agent does not know your communication preferences, risk boundaries, or recurring omissions.
- **No task map**: a new session sees only local context and cannot reliably place new work in the global project.
- **Goal drift**: work can look productive while slowly moving away from the original purpose.

COMPASS gives agents a durable work foundation: understand the user, map the task forest, and pass every ambiguous or risky task through an alignment gate.

If you are new to `SKILL.md` skills, start with the Chinese static tutorial: [How to Write Skills](skill-writing-tutorial.html). It covers the minimum structure, progressive disclosure, reuse audits, AI-assisted drafting, distillation from real runs, and iteration checks.

## The Three-Layer Model

| Layer | Skill | Purpose |
| --- | --- | --- |
| **Know the user** | [`user-profile-keeper`](skills/user-profile-keeper/) | Maintains a local, auditable, correctable user profile for communication preferences, risk boundaries, and collaboration style. |
| **Know the work** | [`task-forest`](skills/task-forest/) | Maintains a repo-local task forest / DAG with goals, subtasks, dependencies, progress, deviations, todos, and history snapshots. |
| **Know the direction** | [`task-clarifier`](skills/task-clarifier/) | Turns fuzzy intent into a shared executable requirement that the user understands, the agent understands, and the user can verify. |

```text
User Profile Keeper answers: who is the user and how should we collaborate?
Task Forest answers: where does this task fit and what changed?
Task Clarifier answers: should we do this, and how do we avoid drifting?
```

## Ecosystem DAG

![COMPASS skills ecosystem DAG](assets/compass-system-map.en.svg)

## Installation And Agent Compatibility

The three released skills use Python standard-library scripts and Markdown instructions. They do not depend on cloud services and do not upload user data.

- macOS / Linux examples use `python3`.
- Windows users can use `py -3` or `python`.
- `task-forest` stores task data in the current workspace at `.agent-workbench/task-forest/`.
- `user-profile-keeper` stores profile data under the local user home at `.compass-skills/user-profiles/v1` by default. Override with `COMPASS_USER_PROFILE_HOME`.
- All writes are local files or local SQLite databases. There is no browser-cookie access, credential access, network upload, or remote write.

COMPASS is not Codex-only. It is an agent-agnostic `SKILL.md` skills package: any agent that supports `SKILL.md`, YAML frontmatter, Markdown instructions, and optional `scripts/` / `references/` can use it natively or near-natively. Agents without native skills support can use the root [AGENTS.md](AGENTS.md) as a lightweight adapter.

| Agent / Environment | Recommended setup |
| --- | --- |
| Codex | Copy the three folders under `skills/` into a Codex-discoverable skills directory, or use them as repo-local skills. |
| Claude Code | Copy the three folders under `skills/` into the Claude Code custom skills directory, or place them under a project skills root. |
| OpenClaw | Place them under workspace `skills/`, `.agents/skills`, or a personal/managed skills directory, following OpenClaw precedence. |
| OpenCode | Keep this repo's `skills/` and [AGENTS.md](AGENTS.md); let the agent discover and read the matching `SKILL.md` through the AGENTS rules. |
| Other agents | If the agent can read local files and run local scripts, load the package through [AGENTS.md](AGENTS.md): read `SKILL.md` first, then use `references/` and `scripts/` as needed. |

**Simplest agent-assisted install prompt**

Send the prompt below to the AI agent you are using. It should review the safety boundary first, then copy the released skills to the real local skills directory for the current agent / harness. If it cannot identify the install path reliably, it should output an installation plan instead of guessing and writing files.

```text
Safely install COMPASS Skills.

Repo: https://github.com/dongshuyan/compass-skills

Goal: after confirming safety, install all released skills under this repo's `skills/` directory.

Requirements:
1. Read and review README, SECURITY, AGENTS.md, every `skills/*/SKILL.md`, and the relevant `references/` and `scripts/`.
2. Confirm that the skills do not upload user data, read credentials / tokens / cookies, write remotely, change global configuration, or run dangerous commands.
3. Identify the local skills directory and loading rules for the current agent / harness. If this cannot be identified reliably, provide an install plan and do not write files.
4. Copy only the released skill folders under `skills/`. Do not copy `.git`, runtime caches, user profiles, task graphs, raw screenshots, or local environment files.
5. After installation, run available local validation, such as Python compile checks and the task-forest export regression. If a check cannot run, explain why and state the remaining risk.
6. Report the install location, installed skills, safety review result, validation result, and how to invoke the skills in a session.
```

For manual installation, copy the three folders under `skills/` into your target agent's local skills directory, then invoke them in any session:

```text
$user-profile-keeper
$task-forest
$task-clarifier
```

## Released Skills

### user-profile-keeper: Local User Profile

Maintains a local user profile that is auditable, correctable, and retractable. It is for collaboration preferences, clarification style, risk boundaries, capability boundaries, and recurring omissions. It does not save secrets or upload data. `task-clarifier` may read only the low-risk `clarification_summary` to ask better questions; it also works well without a profile.

**Important:** `user-profile-keeper` stores data locally in plaintext. It is not an encrypted vault. These skills are designed not to upload, exfiltrate, or read credentials, but local files may still be readable by other processes, backups, or users with access to the same machine. Use it only after understanding this risk, and do not store secrets, tokens, passwords, private keys, verification codes, or highly sensitive information.

**Initial profile prompt**

```text
Use $user-profile-keeper to initialize my local user profile.

Goal: build an auditable, correctable, retractable profile from a local questionnaire or the current context.
Boundaries:
1. Store locally only. Do not upload anything or read browser cookies, tokens, or credentials.
2. Private background information should become pending proposals first.
3. Do not treat this task's operational instructions as long-term profile facts.
4. Report what was saved, proposed, skipped, or redacted.
```

**Update-from-session prompt**

```text
Use $user-profile-keeper to update my local user profile from this session.

Extract only durable collaboration signals, such as communication preferences, risk-confirmation style, recurring omissions, capability boundaries, and privacy boundaries.
Auto-apply only explicit, low-risk, non-conflicting facts. Put inferred, private, sensitive, or conflicting claims into pending proposals.
Do not save secrets, tokens, passwords, private keys, verification codes, or browser-session information.
```

### task-forest: Task Map And Progress Control

Maintains a repo-local task forest / DAG. It tracks goals, subtasks, dependencies, progress, deviations, todos, decisions, and session history. Its HTML export gives users an offline tree view, DAG view, history view, and review queue.

**Build or update task forest prompt**

```text
Use $task-forest to analyze the current session and maintain the task forest for this workspace.

Goal: turn durable goals, tasks, progress, deviations, risks, decisions, and follow-ups from this session into a task-forest proposal.
Requirements:
1. Read the current list and todo first; initialize task-forest if missing.
2. Identify which long-term goal this session served. If no relation is clear, do not force an edge; ask me or create a question/risk node.
3. If a task cannot serve the real user goal, record a deviation or propose a better alternative.
4. Save a proposal and show me the planned changes before applying.
5. After approval, apply, validate, export, and report the HTML path.
```

### task-clarifier: Alignment And Risk Gate

Turns fuzzy intent into a shared executable requirement: the user understands what they want, the agent understands it the same way, and the user can verify that understanding. It routes ambiguous, costly, risky, or evidence-sensitive tasks by asking only decision-changing questions; otherwise it researches first, proceeds with safe defaults, confirms risk, offers workflow choices, or blocks.

If `user-profile-keeper` is installed, `task-clarifier` can use a low-risk profile summary to tailor its questions. If no profile exists, it still works normally from the current context, files, and evidence.

**General prompt**

```text
Use $task-clarifier to align the task below.

Task: ...
Material: ...
Constraints: do not ask what can be inferred from files, context, or reliable sources. Ask only questions that change scope, method, evidence, format, safety, or acceptance criteria.
Output: decide whether to proceed, research-first, ask, confirm, offer-method-choice, or block, and explain why.
```

## Security And Privacy

COMPASS defaults:

- No network upload for profile or task data.
- `user-profile-keeper` uses local plaintext storage by default. It provides local-first, auditable, deletable storage; it does not provide encryption.
- No browser-cookie, token, credential, private-key, or session reading.
- Full profile data is not exposed to ordinary skills; only low-risk `clarification_summary` may be read.
- `task-forest` stores full task content in repo-local files and keeps any global registry lightweight.
- Destructive actions, publishing, remote writes, credential use, and global configuration changes require explicit confirmation.
- HTML exports are static offline files and do not modify the task graph.

See [SECURITY.md](SECURITY.md).

## Roadmap

![COMPASS roadmap skills ecosystem](assets/compass-roadmap-ecosystem.en.png)

Coming next:

- `run-history-skill-builder`: build reusable skills from real task histories.
- `run-history-skill-upgrader`: upgrade existing skills from failures, feedback, and validation evidence.
- `session-handoff-prompt`: generate restart prompts for long sessions using task-forest as structured context.
- Local Agent Control Room: summarize local agent states, risk, waiting-human items, and review queues.
- Gap Router: recommend low-switching-cost tasks using wait time, energy, and task-forest todos.
- Daily / weekly reports, project retrospectives, task ordering, deadline planning, and healthier work-rhythm systems.

## Pre-Release Checklist

- [ ] Choose and add an open-source license.
- [ ] Confirm installation paths for the target distribution channel.
- [ ] Run Python compile checks and the task-forest clean-room export validation.
- [ ] Scan for private paths, tokens, credentials, internal logs, and runtime residue.
- [ ] Test the three prompts in a fresh workspace.
