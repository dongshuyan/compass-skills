# History Mining

Read this file when you need to reconstruct what really happened before packaging it into a new skill.

## Source Priority

1. Current visible conversation and direct user corrections.
2. User-provided files, logs, screenshots, artifacts, and transcript paths.
3. Current workspace files, diffs, tests, generated outputs, and terminal evidence.
4. Public references used only for packaging patterns, not as proof that the local workflow succeeded.

## What To Extract

- user goal and acceptance criteria;
- true inputs, outputs, and side effects;
- successful path;
- failed attempts, blockers, and misjudgments;
- fixes that actually worked;
- approval gates and stop conditions;
- observable success evidence.

## Evidence Sheet

For each candidate rule, record:

- `observation`: what happened;
- `source_type`: conversation, file, log, artifact, browser, diff, test, or public reference;
- `confidence`: high / medium / low;
- `invariant`: the reusable part that belongs in a skill;
- `local_detail`: the path, account, date, or one-off circumstance that should not be released as a rule.

## Facts vs Assumptions

- Facts come from files, tool output, user statements, or public evidence you actually read.
- Inferences are allowed only when clearly marked and relevant to packaging.
- If success cannot be externally checked, say so and keep the package conservative.

## Authorized Defaults

Usually safe after scope is locked:

- current thread context;
- current repository files and diffs;
- user-provided artifact directories;
- user-provided screenshots and logs;
- temporary local scratch files created for this task.

Require explicit approval:

- broad local conversation archives unrelated to the task;
- browser-session stores, cookies, local storage, or saved sessions;
- passwords, tokens, API keys, MFA material, or other credentials;
- private folders outside the agreed project scope.

## Workflow Reconstruction Output

Before writing the skill, produce:

- a success timeline;
- a failure-to-fix table;
- a state transition list;
- validation gates;
- unresolved assumptions.

If you cannot produce these, you do not yet understand the workflow well enough to package it.

## Reusable Invariants vs Local Accidentals

Reusable:

- "choose the validated final artifact, not a raw intermediate";
- "check visible success evidence before claiming publication";
- "gate risky submission steps behind explicit confirmation".

Local-only:

- one temporary file path;
- one account name;
- one machine-specific directory;
- one-day UI wording;
- one-time manual preference not marked as durable.

## External Side Effects

For workflows that publish, upload, send, deploy, or mutate shared systems:

- capture the exact pre-submit gate;
- capture the observable success proof;
- capture the stop condition when evidence is missing;
- never reconstruct the workflow as "do the action and hope it worked".
