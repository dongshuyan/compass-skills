# COMPASS

[中文](README.md)

**司南: 个性化 AI 任务总控 Skills 系统**  
**COMPASS: Personal Alignment Skills OS for AI Agents**

COMPASS helps AI agents understand the user, see the full task landscape, and avoid goal drift. It combines a local user profile, a repo-local task graph, and an alignment router into a reusable skills system for long-running AI work.

![task-forest demo](assets/task-forest-demo.gif)

## Why COMPASS

Most agents are good at the current prompt. Long-running work fails in different ways:

- **No user model**: the agent does not know your communication preferences, risk boundaries, or recurring omissions.
- **No task map**: a new session sees only local context and cannot reliably place new work in the global project.
- **Goal drift**: work can look productive while slowly moving away from the original purpose.

COMPASS gives agents a durable work foundation: understand the user, map the task forest, and pass every ambiguous or risky task through an alignment gate.

## The Three-Layer Model

| Layer | Skill | Purpose |
| --- | --- | --- |
| **Know the user** | [`user-profile-keeper`](skills/user-profile-keeper/) | Maintains a local, auditable, correctable user profile for communication preferences, risk boundaries, and collaboration style. |
| **Know the work** | [`task-forest`](skills/task-forest/) | Maintains a repo-local task forest / DAG with goals, subtasks, dependencies, progress, deviations, todos, and history snapshots. |
| **Know the direction** | [`task-clarifier`](skills/task-clarifier/) | Decides whether to proceed, research first, ask, confirm risk, offer choices, or stop before costly or ambiguous work. |

```text
User Profile Keeper answers: who is the user and how should we collaborate?
Task Forest answers: where does this task fit and what changed?
Task Clarifier answers: should we do this, and how do we avoid drifting?
```

## Ecosystem DAG

```mermaid
flowchart TD
  U["User"] --> UPK["user-profile-keeper<br/>Local user profile"]
  U --> TC["task-clarifier<br/>Alignment gate"]
  U --> TF["task-forest<br/>Task forest / DAG"]

  UPK -. "low-risk clarification_summary" .-> TC
  TC --> TF
  TF --> SH["session-handoff-prompt<br/>session resume prompts"]
  TF --> ACR["Local Agent Control Room<br/>multi-agent status"]
  TF --> GR["Gap Router<br/>low-switching-cost tasks"]

  SH --> TF
  GR -. "completion via proposal" .-> TF
  ACR -. "review / risk via proposal" .-> TF

  TF --> RHB["run-history-skill-builder<br/>build skills from real runs"]
  TF --> RHU["run-history-skill-upgrader<br/>upgrade skills from failures"]
  TC --> RHB
  UPK --> RHU

  RHB --> ECO["Future ecosystem<br/>daily reports / weekly reports / planning / habits / retrospectives"]
  RHU --> ECO
```

![COMPASS system map](assets/compass-system-map.svg)

## Installation And Compatibility

The three released skills use Python standard-library scripts and Markdown instructions. They do not depend on cloud services and do not upload user data.

- macOS / Linux examples use `python3`.
- Windows users can use `py -3` or `python`.
- `task-forest` stores task data in the current workspace at `.agent-workbench/task-forest/`.
- `user-profile-keeper` stores profile data under the local user home at `.compass-skills/user-profiles/v1` by default. Override with `COMPASS_USER_PROFILE_HOME`.
- All writes are local files or local SQLite databases. There is no browser-cookie access, credential access, network upload, or remote write.

Copy the three folders under `skills/` into your local skills directory, then invoke them in any session:

```text
$user-profile-keeper
$task-forest
$task-clarifier
```

## Released Skills

### user-profile-keeper: Local User Profile

Maintains a local user profile that is auditable, correctable, and retractable. It is for collaboration preferences, clarification style, risk boundaries, capability boundaries, and recurring omissions. It does not save secrets or upload data.

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

Routes ambiguous, costly, risky, or evidence-sensitive tasks. It asks only decision-changing questions and otherwise researches first, proceeds with safe defaults, confirms risk, offers workflow choices, or blocks.

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
- No browser-cookie, token, credential, private-key, or session reading.
- Full profile data is not exposed to ordinary skills; only low-risk `clarification_summary` may be read.
- `task-forest` stores full task content in repo-local files and keeps any global registry lightweight.
- Destructive actions, publishing, remote writes, credential use, and global configuration changes require explicit confirmation.
- HTML exports are static offline files and do not modify the task graph.

See [SECURITY.md](SECURITY.md).

## Roadmap

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

