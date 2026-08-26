# Validation And Regression

Read this file after the user approves the plan and before claiming the upgrade is complete.

## Baseline Checks

These checks establish structural legality and deterministic correctness only. A passing validator does not execute the eval definitions or prove behavioral improvement; that requires the relevant trigger, route, case, or comparison regression below.

Run only the checks that apply to the changed surface:

- this skill's `validate_upgrade_artifacts.py`;
- the target skill's own validator, if it has one;
- `python -m py_compile` when Python scripts changed;
- `python -m json.tool` when JSON files changed;
- reference-path checks when references changed and no existing validator covers them.

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

- one representative should-trigger prompt;
- one nearby should-not-trigger prompt;
- one boundary prompt.

Expand this set only when the trigger remains unstable, covers many neighboring tasks, or carries high-cost failure modes.

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
