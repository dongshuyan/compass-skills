# Upgrade Decision Protocol

Read this file while turning evidence into a concrete plan.

## Gate Sequence

Each candidate change should pass these gates in order:

1. `evidence_gate`: is the problem or opportunity grounded in traceable evidence?
2. `generalization_gate`: is the change likely to help future runs, not just one incident?
3. `route_gate`: does the change remove weak subjectivity or move facts to verifiable checks?
4. `net_benefit_gate`: is the gain larger than the cost in length, complexity, or overfitting risk?
5. `validation_gate`: can you show how to prove the change helped or at least did not regress?

## Case Design

Split examples and tests into:

- `incident`: the original failure or confusion;
- `candidate_rule`: the proposed durable behavior;
- `regression_case`: a case that should continue to pass;
- `boundary_case`: a near-negative or over-broad case;
- `holdout_challenge`: a keep-back challenge used only after the change is applied.

Do not use the holdout challenge to invent the rule itself.

## Route Effect Mapping

Describe the route impact of each planned change with labels such as:

- `delete_weak_route`
- `user_confirmed_route`
- `tool_verified_route`
- `evidence_first_route`
- `merge_duplicate_route`

If you cannot explain who corrects a route when it goes wrong, the route is still weak.

## Upgrade Levels

- `no_change`
- `maintenance_note_only`
- `prune_or_consolidate`
- `local_refactor`
- `cross_reference_refactor`
- `major_refactor`
- `deprecate_or_replace_source`

Prefer the smallest level that solves the real problem.

## Plan Template

For each candidate change, include:

- evidence;
- signal class;
- root cause;
- planned change type;
- affected files or structure owners;
- route effect;
- validation method;
- risks and non-goals.

Also include:

- deletion or merge candidates;
- ideas that were rejected;
- the exact approval needed before application.

## Anti-Overfit Rule

Do not turn these into permanent rules without stronger evidence:

- literal temp paths;
- one-day UI wording;
- account-specific behavior;
- one-time emergency workarounds;
- temporary user preferences not marked as durable.
