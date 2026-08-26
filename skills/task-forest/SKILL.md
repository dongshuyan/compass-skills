---
name: task-forest
description: Maintains a repo-local task forest or task DAG for the current workspace. Use when the user asks to initialize or update a task forest, close a session, summarize evolving project work, align a request with a global goal, track progress/history/deviations/todos, save or apply a task proposal, or export the client-readable task-forest HTML. Do not use for executing the tracked tasks themselves or for generic HTML work.
---

# Task Forest

## Purpose

Maintain the current workspace's task structure, proposals, history, and progress. Produce one standalone HTML deliverable that a first-time reader can understand without opening another task list or internal file.

Use the user's language for task content, proposals, reports, and HTML. Default to Chinese when unknown.

## Portability

This skill is agent-agnostic. Install the whole `task-forest` directory in any host-supported skill location, then resolve scripts, references, and assets from the directory containing this `SKILL.md`. Do not assume a specific agent name, skill root, home-directory layout, shell, path separator, or operating system.

Use an available Python 3 launcher on the host (`python3`, `python`, or `py -3`). The scripts use the Python standard library and support macOS, Linux, and Windows. To label task history with the calling agent, set `COMPASS_AGENT_NAME` or `AGENT_NAME`, or pass `--actor`; otherwise the neutral value `agent` is used.

## Core Rules

1. Read and write task-forest data only through `scripts/task_forest.py`; never hand-edit `.agent-workbench/task-forest/` canonical files.
2. Use one primary `child_of` parent per node, `contributes_to` for secondary ownership, and `depends_on` for prerequisites.
3. Save graph changes as a proposal and wait for user confirmation before `proposal-apply --yes`.
4. Keep low-confidence inference in a question or proposal. Record material execution drift as a deviation.
5. Write visible task titles and purposes in plain language. A reader must understand what the task delivers, why it exists, and what has been completed without knowing internal codes such as `P04` or reading another file.
6. Export one HTML surface: `exports/task-forest.html`. It shows `done`, `in_progress`, and their necessary `child_of` ancestors, with history playback. Do not expose internal discussions, evidence, queues, filesystem paths, sessions, or proposal content in the HTML.
7. Keep HTML interactions read-only. Formal changes always return through the proposal workflow.
8. Keep task data and discovery metadata repo-local by default. Cross-workspace discovery is optional: enable it only after the user explicitly opts in by setting `TASK_FOREST_ENABLE_GLOBAL_REGISTRY=1`. This writes lightweight workspace paths and health summaries to `AGENT_WORKBENCH_DB`, or to `~/.agent-workbench/agent-workbench.sqlite3` when that variable is unset; it never stores task content.

## Main Workflow

When initializing, updating, or closing a session:

1. Run `init`.
2. Read `list --json` and `todo --json`.
3. Identify the global goal served by the session and the task structure that must remain visible.
4. When the workspace has an authoritative task list, preserve its meaningful `goal -> phase -> module -> concrete task` hierarchy and sibling order for every `done` or `in_progress` task. Include necessary ancestors, omit wholly unstarted branches, and attach extra fixes under the feature they improve. Never collapse several phases into one node or rely on edge creation order. If one sibling needs `display_order`, set a unique numeric value for the whole sibling group; partial, duplicate, or invalid values must fail validation.
5. Make every visible node independently understandable. Use a clear title plus `summary` or `purpose`; add outcomes or acceptance criteria when they clarify delivery. Treat internal codes as secondary labels, not as the task name.
6. Show and save a proposal. Do not apply it before confirmation.
7. After confirmation, run `proposal-apply --yes`, `validate`, and `export`.
8. Return the proposal path and the single HTML path.

Use `$task-clarifier` when user intent or the target global goal is genuinely unclear.

## Commands

Resolve `<skill-dir>` from this file and use an available Python 3 executable. The examples use `python3`; substitute the host's available launcher when needed.

```bash
python3 <skill-dir>/scripts/task_forest.py init
python3 <skill-dir>/scripts/task_forest.py list --json
python3 <skill-dir>/scripts/task_forest.py todo --json
python3 <skill-dir>/scripts/task_forest.py proposal-save --proposal-file /path/to/proposal.json
python3 <skill-dir>/scripts/task_forest.py proposal-apply <proposal-id> --yes
python3 <skill-dir>/scripts/task_forest.py validate
python3 <skill-dir>/scripts/task_forest.py export
```

The default workspace is the current directory. Use `--workspace` only when another workspace is explicit. Use `--root` only when the caller explicitly selected a non-default task-forest root.

Global registry integration is off by default. `TASK_FOREST_DISABLE_GLOBAL_REGISTRY=1` remains an explicit override when a host sets the enable flag globally.

## Outputs

The user-facing artifacts are:

```text
proposals/<proposal_id>.json
exports/task-forest.html
```

The exporter also maintains three internal compatibility files for `gap-router` and `local-agent-control-room`:

```text
exports/task-forest.graph.json
exports/task-forest.todos.json
exports/task-forest.timeline.json
```

Do not present those JSON files as delivery artifacts unless the user explicitly asks for machine-readable data.

## References and Validation

- Read `references/schema.md` for node fields, proposal actions, and canonical invariants.
- Read `references/goal-alignment.md` only when judging global-goal fit or competing candidate plans.
- Read `references/node-types.md` only when node classification is unclear.
- Read `references/concurrency.md` before resolving stale proposals or concurrent writes.
- Read `references/html-visualization-contract.md` when changing or validating the HTML.
- Read `references/integration-contract.md` only when changing JSON or registry compatibility.

For HTML or exporter changes, run:

```bash
python3 <skill-dir>/scripts/validate_task_forest_export.py --skill-dir <skill-dir>
```

The HTML remains a derived, read-only view. Canonical task data and proposal history stay repo-local.
