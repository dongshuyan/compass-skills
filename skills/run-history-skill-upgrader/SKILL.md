---
name: run-history-skill-upgrader
description: Use real run evidence, validation failures, source drift, platform drift, and user feedback to plan and, only after explicit approval, apply structural upgrades to an existing skill. Use when the user asks to improve an existing skill from recent runs, recurring failures, outdated sources, excessive bloat, changed platform behavior, or validated workflow feedback. Do not use to create a brand-new skill or to execute the business workflow itself.
---

# Run History Skill Upgrader

## Language Policy

Write all user-facing output in the user's language. Default to Chinese when the language is unknown.

## Role

Turn real run feedback into structural net improvement for an existing skill. Upgrades may add, modify, merge, delete, deprecate, or decide not to change anything.

## Portability

This skill is agent-agnostic. It should work in Codex, Claude Code, OpenCode, OpenClaw, Hermes, and similar local agent hosts that can read `SKILL.md` plus optional `references/`, `scripts/`, `evals/`, and `agents/`.

- Resolve `<skill-dir>` from the directory that contains this `SKILL.md`.
- Let `<python>` mean the host's available Python launcher: `python3`, `python`, or `py -3`.
- Do not assume a fixed skill root, shell, home-directory layout, or path separator.
- Placeholder paths such as `<skill-dir>/scripts/...` describe path segments, not a required separator style. On Windows, use the separator style that your shell or harness accepts.
- Treat platform-specific helper tooling as optional. Use it only when it is actually available.

## Mandatory Two-Stage Approval

This skill always starts in `plan_only`.

1. `plan_only`: read the target skill and the agreed evidence scope, then produce a concrete upgrade plan and stop.
2. `apply_after_approval`: modify files only after the user explicitly approves that specific plan.

The following are **not** approval by themselves:

- "upgrade it";
- "directly edit it";
- "don't ask me";
- "go ahead";
- the original request to improve a skill.

Valid approval must clearly point to the current plan, for example "approve plan A", "apply the plan above", or "yes, execute that upgrade plan".

## Workflow

1. Lock the target skill name and path.
2. Lock `plan_only` unless explicit post-plan approval already exists in the current conversation.
3. Lock the evidence scope: conversation, logs, screenshots, artifacts, diffs, tests, source docs, or user feedback.
4. Read the current target skill before proposing changes.
5. Classify the signals: process gap, validation gap, source drift, platform drift, user preference, candidate idea, incident, routing gap, or content bloat.
6. Design the case set: incident, candidate rule, regression case, boundary case, and optional holdout challenge.
7. Pass the generalization gate. A one-off incident does not automatically deserve a lasting rule.
8. Map route impact. Remove weak routes and move machine-checkable facts to tools, tests, schema checks, diffs, validators, or files.
9. Choose the net-improvement shape: `no_change`, `maintenance_note_only`, `prune_or_consolidate`, `local_refactor`, `cross_reference_refactor`, `major_refactor`, or `deprecate_or_replace_source`.
10. Produce the concrete plan and stop.
11. Apply only after explicit approval.
12. Validate, report what changed, and record follow-up risks.

## Evidence Rules

Strong evidence:

- user feedback or corrections;
- real run outputs, logs, screenshots, tests, or diffs;
- actual target-skill files;
- official docs or first-party repositories that explain source or platform drift.

Weak evidence unless corroborated:

- one-off timeouts;
- one failed page load;
- a search snippet without opening the source;
- a model-generated idea with no supporting run evidence;
- a private path or one temporary filename presented as if it were a universal rule.

## Upgrade Rules

- Prefer deleting or merging stale guidance over stacking new reminders on top.
- Keep examples only when they preserve complex behavior or important failure recovery.
- Temporary user preferences stay task-local unless the user clearly wants them kept as durable behavior.
- Holdout challenges are for post-apply validation, not for plan design.
- Do not ship an internal maintenance log with this released skill package. If the target skill already has one, update it only after approval and only if the user wants durable maintenance history there.

## File-Editing Discipline

Before applying changes:

- read the target skill's `SKILL.md`, relevant `references/`, `scripts/`, `evals/`, and optional agent metadata;
- preserve unrelated user changes;
- capture a diff or snapshot reference when practical;
- edit only files that belong to the current approved plan.

Do not write credentials, browser sessions, private account data, unrelated personal paths, or hidden prompts into the target skill.

## Validation

Run the bundled validator for this upgrader skill:

```bash
<python> <skill-dir>/scripts/validate_upgrade_artifacts.py --skill <skill-dir>
```

Then run the target skill's own validator and the smallest relevant technical checks:

- `python -m py_compile` for modified Python scripts;
- `python -m json.tool` for edited JSON files;
- trigger regression if the frontmatter `description` changed;
- route and boundary regression if the workflow changed;
- comparison against the original failure, at least one similar positive case, and at least one near-negative case for high-risk upgrades.

Do not claim that the upgrade is complete if validation was skipped or failed.

## Final Response

Report:

- the target skill and path;
- whether the result is plan-only or applied;
- evidence sources actually used;
- files actually changed;
- validation commands actually run and their results;
- deleted or rejected ideas and why;
- remaining risks or follow-up checks.

## References

- `references/evidence-and-scope.md`
- `references/upgrade-decision-protocol.md`
- `references/validation-and-regression.md`
- `references/examples.md`
- `scripts/validate_upgrade_artifacts.py`
- `evals/evals.json`
