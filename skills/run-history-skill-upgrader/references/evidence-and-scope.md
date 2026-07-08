# Evidence And Scope

Read this file before drafting the upgrade plan.

## Target Lock

Always lock:

- target skill name;
- absolute or repository-relative path;
- requested scope;
- whether the user asked for plan-only or has already approved a specific plan.

## Evidence Priority

1. Current target-skill files.
2. User feedback and corrections.
3. Real run outputs: logs, tests, screenshots, artifacts, diffs.
4. Official docs or first-party repos that explain source or platform drift.
5. Public references used for pattern comparison only.

## Allowed By Default After Scope Lock

- current visible conversation;
- target skill files inside the agreed repository;
- user-provided artifacts, logs, screenshots, and transcripts;
- repository diffs and test output tied to the current run.

## Explicit Approval Required

- unrelated local session archives;
- browser cookies, local storage, saved sessions, or account caches;
- passwords, tokens, API keys, MFA material, or other credentials;
- unrelated private folders outside the agreed project scope.

## Signal Classes

Use one or more of these labels:

- `process_gap`
- `validation_gap`
- `source_drift`
- `platform_drift`
- `user_preference`
- `candidate_idea`
- `incident`
- `routing_gap`
- `content_bloat`

The label shapes the upgrade plan. An `incident` alone does not justify a durable rule. A repeated `validation_gap` often does.

## Snapshot Discipline

Before file edits, keep at least one of:

- a diff reference;
- a snapshot path;
- an unmodified branch state that can be compared later.

If that is not practical, say so in the plan and treat it as extra risk.

## Strong And Weak Evidence

Strong:

- reproducible failure;
- repeated user correction;
- validator or test output;
- official source or platform change.

Weak unless corroborated:

- one timeout;
- one vague complaint;
- one private temp path;
- one speculative idea;
- one search result snippet not opened and checked.

## When To Choose No Change

Prefer `no_change` or `maintenance_note_only` when:

- the evidence is weak or one-off;
- the proposed rule would hardcode a path, date, account, or temporary workaround;
- the change increases complexity without adding validation or clarity;
- the user preference was clearly task-local rather than durable.
