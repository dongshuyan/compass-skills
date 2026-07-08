---
name: run-history-skill-builder
description: Turn a completed task, browser flow, artifact pipeline, failure-recovery trace, or repeatedly refined workflow into a new reusable skill package or a reviewed skill-design plan. Use when the user asks to make a new skill from real run history, extract a reusable workflow from conversation/logs/files, summarize lessons into a new skill, or produce a plan before writing files. Do not use to upgrade an existing skill or to execute the business workflow itself.
---

# Run History Skill Builder

## Language Policy

Write all user-facing output in the user's language. Default to Chinese when the language is unknown.

## Role

Turn real run history into a new skill package, a plan-only skill design, or an upgrade handoff when the request is actually about an existing skill.

## Portability

This skill is agent-agnostic. It should work in Codex, Claude Code, OpenCode, OpenClaw, Hermes, and similar local agent hosts that can read `SKILL.md` plus optional `references/`, `scripts/`, `evals/`, and `agents/`.

- Resolve `<skill-dir>` from the directory that contains this `SKILL.md`.
- Let `<python>` mean the host's available Python launcher: `python3`, `python`, or `py -3`.
- Do not assume a fixed skill root, shell, home-directory layout, or path separator.
- Placeholder paths such as `<skill-dir>/scripts/...` describe path segments, not a required separator style. On Windows, use the separator style that your shell or harness accepts.
- Before writing files, lock the output directory. If the user does not provide one, propose a neutral local target such as the current repository's `skills/` directory or the host agent's documented local skills directory, then wait for confirmation.

## Workflow

1. Lock intent: decide whether the request is `plan_only`, `new_single_skill`, `router_skill`, `skill_suite`, or `existing_skill_upgrade_handoff`.
2. Lock evidence scope: confirm which conversation turns, files, logs, artifacts, diffs, browser flows, or transcripts you may read.
3. Lock output location before writing files.
4. Reconstruct the workflow from authorized evidence: user goal, real steps, failures, fixes, success proofs, and approval gates.
5. Mine local or open-source patterns only when they help package the workflow more reliably.
6. Separate reusable invariants from local accidentals such as one-time paths, account names, one-day product quirks, or temporary user preferences.
7. Abstract the workflow into state gates, validation gates, scripts, references, examples, and evals. Delete weak routes that depend on subjective guesses.
8. Choose the smallest package that preserves correctness.
9. Write the skill only after the previous gates are satisfied.
10. Validate, report remaining assumptions, and hand the package back with paths and checks.

Do not jump directly from "I saw a successful run" to "I wrote a skill". The missing middle layer is where portability, privacy, and generalization are decided.

## Architecture Choices

- `plan_only`: the user wants a reviewed design or audit, not files.
- `new_single_skill`: one stable workflow or one tightly coupled workflow family.
- `router_skill`: one entry point that routes across several existing skills or phases.
- `skill_suite`: several independent workflows that should be released together but triggered separately.
- `existing_skill_upgrade_handoff`: the real task is to improve an existing skill. Produce a clean handoff for `$run-history-skill-upgrader` instead of editing that skill here.

Prefer replacement, merging, and omission over package bloat.

## Evidence And Scope

Allowed by default after intent is locked:

- current visible conversation;
- user-provided paths, artifacts, logs, screenshots, and transcripts;
- current workspace files, diffs, tests, and generated outputs;
- similar public skills or official docs read for packaging patterns.

Require explicit approval before reading:

- broad local session archives unrelated to the current task;
- browser cookies, local storage, session exports, or account caches;
- passwords, tokens, API keys, verification codes, MFA data, or other credentials;
- unrelated private folders or personal history outside the agreed scope.

Keep facts, inferences, and open assumptions separate. Never write secrets, hidden prompts, private account identifiers, or unrelated personal data into the released skill or its examples.

## Design Rules

- Keep `SKILL.md` focused on trigger boundary, role, workflow, safety gates, and reference navigation.
- Put long branch-specific guidance in `references/`.
- Put deterministic and repeated checks in `scripts/`.
- Put trigger and regression samples in `evals/` when the workflow is long-lived, high-risk, or easy to overfit.
- Use examples only when they capture complex behavior, failure recovery, or boundary conditions. Every example must state the invariant and the non-goal.
- User-owned decisions stay user-owned. Machine-checkable facts move to scripts, tests, schema checks, diffs, file-existence checks, or validators.
- Do not create per-skill `README`, installation scripts, changelogs, or decorative files unless the user or release target explicitly requires them.
- Treat `agents/openai.yaml` as an optional UI enhancement, not as the core logic.

## Validation

Run the package validator bundled with this skill:

```bash
<python> <skill-dir>/scripts/validate_skill_package.py <target-skill-dir>
```

If the current host provides a canonical skill validator, run that too. On Codex-like hosts, this often means a `quick_validate.py` command from the platform's skill tooling.

Also run the smallest relevant technical checks:

- `python -m py_compile` for modified Python scripts;
- `python -m json.tool` for edited JSON files;
- trigger review with at least 3 should-trigger, 3 should-not-trigger, and 2 boundary prompts;
- a leak scan for private absolute paths, credentials, hidden prompts, or environment-specific debris.

Do not claim completion if validation was skipped or failed. Report the gap and the remaining risk.

## Final Response

Report:

- the chosen package type;
- the final skill path;
- files created or intentionally omitted;
- evidence sources actually used;
- validation commands actually run and their results;
- assumptions that still need user review;
- whether the result is `plan_only`, a new skill package, or an upgrader handoff.

## References

- `references/history-mining.md`
- `references/open-source-pattern-mining.md`
- `references/skill-design-protocol.md`
- `references/self-repair-and-evals.md`
- `references/examples.md`
- `scripts/validate_skill_package.py`
- `evals/evals.json`
