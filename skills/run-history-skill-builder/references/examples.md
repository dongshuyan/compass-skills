# Examples

These examples are public, sanitized patterns. They exist to teach reusable packaging decisions, not to preserve one private machine or one one-off task.

## Example 1: Browser Publishing Workflow

User request:

```text
Turn the browser-based publishing workflow we just stabilized into a new skill.
```

Evidence worth extracting:

- a validated final artifact exists and is distinct from raw intermediates;
- the form has required metadata fields and a risky final submit step;
- there was a false-success failure mode where a visible field looked correct but the submitted value was wrong;
- success must be proven by a platform-visible confirmation, resulting artifact, or other checkable evidence.

Good package outcome:

- state gates for input resolution, metadata readiness, pre-submit validation, submission, and success verification;
- a failure-recovery example for the false-success case;
- privacy boundaries that keep account data and credentials out of the package.

## Example 2: Local Document-Conversion Pipeline

User request:

```text
We finally stabilized a DOCX to PDF workflow. Make it a reusable skill.
```

Package outcome:

- input and output naming contract;
- deterministic conversion or validation helpers in `scripts/`;
- checks for output existence, page count, extraction sanity, and common failure states;
- examples for missing fonts, layout drift, or failed generation.

## Example 3: Plan-Only Design

User request:

```text
Give me a full skill-design plan, but do not write files yet.
```

Expected behavior:

- list the candidate files and their owners;
- explain the validation plan;
- explicitly say that no files were written.

## Example 4: Existing Skill Upgrade Handoff

User request:

```text
Improve the existing release-publisher skill based on this failure.
```

Expected behavior:

- recognize that this is not a new-skill request;
- prepare a clean handoff for `$run-history-skill-upgrader`;
- do not create a new skill package and do not edit the existing skill here.

## Example 5: Minimal Package

User request:

```text
Package this short local query workflow as a skill.
```

Expected behavior:

- first decide whether the workflow is frequent enough, error-prone enough, and stable enough to deserve a skill;
- if yes, prefer only `SKILL.md` plus optional `agents/openai.yaml`;
- avoid empty `references/`, `scripts/`, or `evals/`.

## Example 6: Pattern-Mining Request

User request:

```text
Search similar public skills, inspect them, and then package our workflow.
```

Expected behavior:

- inspect real public references and record what was adopted;
- do not cite repositories you did not read;
- do not ship the temporary research clones as part of the released skill.
