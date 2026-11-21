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

If the current skill already contains an equivalent rule for a step that failed, check the version used in that run. If the rule was added later, check whether the newer version already addresses the failure. If the rule was present, follow the available evidence:

- Did the entry point match the task, and did the relevant guidance load?
- Did the rule apply under the conditions of that run? Did another instruction conflict with it?
- Was the step carried out? Did the final artifact meet that run's requirements?

Propose the smallest change where the evidence locates the failure, such as repairing a broken reference or checking the final export. If the evidence shows only an incorrect artifact or otherwise leaves the cause unresolved, record the cause as unknown.

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
