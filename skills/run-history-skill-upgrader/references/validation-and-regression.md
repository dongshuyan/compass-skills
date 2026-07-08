# Validation And Regression

Read this file after the user approves the plan and before claiming the upgrade is complete.

## Baseline Checks

Run at least:

- the target skill's own validator, if it has one;
- this skill's `validate_upgrade_artifacts.py`;
- `python -m py_compile` on modified Python scripts;
- `python -m json.tool` on modified JSON files;
- reference-path existence checks.

## Regression Levels

Choose the smallest sufficient level:

- `smoke`: structure and critical-path checks;
- `reliable`: multiple cases or stronger deterministic verification;
- `regression`: high-risk side effects or repeated failures;
- `manual_review`: subjective quality, visual checks, or unstable external UI.

## Required Regression Slices

When relevant, test these slices:

- approval gate;
- generalization gate;
- source drift vs one-off outage;
- platform drift vs user error;
- durable preference vs temporary preference;
- content bloat vs true net improvement;
- weak-route deletion or hardening.

## Trigger Regression

If the target skill's `description` changed, review:

- 3 should-trigger prompts;
- 3 should-not-trigger prompts;
- 2 boundary prompts.

## Route Regression

If routes changed, verify:

- user-owned decisions still wait for user confirmation;
- machine-checkable facts now rely on scripts, tests, schema, diffs, or files;
- deleted weak routes do not reappear through examples or prose.

## Case Regression

For high-risk changes, cover:

- the original failure;
- at least one similar positive case;
- at least one near-negative case.

Use holdout challenges only after the change is applied.

## Optional Maintenance Summary

If the target skill already keeps a maintenance note or log, append a short entry only after approval. Keep it concise:

```markdown
## YYYY-MM-DD

- reason:
- evidence:
- upgrade level:
- files changed:
- validation:
- follow-up risks:
```

Do not create a new maintenance log by default if the target skill has never used one and the user did not ask for durable maintenance history.

## Failure Handling

If validation fails:

1. do not claim the upgrade is complete;
2. record the failing command and a short output summary;
3. attempt one direct fix if the root cause is clear;
4. otherwise stop and report the remaining risk.
