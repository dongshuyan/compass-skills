# Examples

These are public, sanitized upgrade patterns. They are not a license to turn every incident into a permanent rule.

## Example 1: Missing Finalization Gate

Signal:

- a workflow claimed success before the final processed artifact actually existed.

Good upgrade:

- add or strengthen a finalization gate;
- move the success claim behind a deterministic check;
- update examples and validation accordingly.

## Example 2: Source Drift

Signal:

- a previously used source now looks inaccessible.

Good upgrade:

- check whether the problem is temporary, authentication-related, moved, rate-limited, or truly discontinued;
- replace or deprecate only with strong evidence;
- keep the plan conservative if evidence is weak.

## Example 3: Durable vs Temporary Preference

Signal:

- the user wants a certain output style or field included every time.

Good upgrade:

- keep it durable only if the user clearly wants the preference preserved across future runs;
- otherwise treat it as task-local and avoid changing the skill.

## Example 4: Candidate Idea

Signal:

- an agent or user suggests parallelizing the skill.

Good upgrade:

- keep it as a candidate idea until run evidence shows that concurrency solves a real bottleneck without unsafe shared-state collisions.

## Example 5: Prune Or Merge

Signal:

- the skill keeps growing and repeats the same rule in multiple places.

Good upgrade:

- identify the strongest structure owner;
- merge duplicate prose;
- delete low-value reminders that add no validation power.

## Example 6: Platform Drift

Signal:

- a familiar UI changed enough that the old workflow no longer lines up with visible states.

Good upgrade:

- update the documented visible checks and any affected selector or navigation logic;
- keep user-error cases separate from platform-drift cases.

## Example 7: Overfit Incident

Signal:

- one failed path or one temp filename is proposed as a permanent rule.

Good upgrade:

- abstract to the underlying validation gate;
- if no clean abstraction exists, choose `no_change` or `maintenance_note_only`.

## Example 8: Plan-Only Boundary

Signal:

- the user asks for direct edits before seeing a plan.

Good upgrade:

- produce the plan, say that no files were modified yet, and wait for explicit approval that points to the plan.
