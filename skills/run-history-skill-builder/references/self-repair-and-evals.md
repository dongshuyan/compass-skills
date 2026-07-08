# Self-Repair And Evals

Read this file before delivery, after validation failures, or whenever the generated package still feels ambiguous.

## Structural Validation

Run the bundled validator:

```bash
<python> <skill-dir>/scripts/validate_skill_package.py <target-skill-dir>
```

Then run the platform validator if the current host provides one.

## Trigger Review

Prepare at least:

- 3 should-trigger prompts;
- 3 should-not-trigger prompts;
- 2 boundary prompts.

If the samples reveal false positives or false negatives, fix the frontmatter `description` first, then the body.

## Adversarial Checklist

Before release, ask:

- Does another agent know exactly when this skill should fire?
- Is the output directory locked before file writes?
- Is the request actually about a new skill rather than an existing-skill upgrade?
- Which branch still depends on a guess instead of user confirmation or machine-checkable evidence?
- Which deterministic checks should be scripted instead of repeated in prose?
- Are there useless resources or placeholder files left behind?
- Is any private path, credential-like string, or hidden internal note still present?

## Eval Design

Create realistic prompts in `evals/evals.json` and make them check:

- trigger accuracy;
- output package shape;
- boundary handling;
- privacy discipline;
- plan-only behavior when requested;
- correct redirection to the upgrader when the user actually wants to modify an existing skill.

Minimal example:

```json
{
  "id": 1,
  "prompt": "Turn the document-processing workflow we just stabilized into a new skill.",
  "expected_output": "A new skill package with trigger wording, state gates, reusable checks, and validation results.",
  "expectations": [
    "The response creates a package instead of a prose-only summary.",
    "The package captures reusable gates and checks.",
    "The final response reports real validation results."
  ]
}
```

## Repair Loop

If validation fails:

1. Find the structure owner: frontmatter, workflow, references, scripts, evals, or final response contract.
2. Fix that owner instead of scattering reminders elsewhere.
3. Update examples or evals if the failure came from a real run.
4. Re-run the smallest sufficient validation set.
5. Report any remaining warnings as residual risk.

## Comparison Evaluations

Run before/after comparisons when:

- the skill will be reused often;
- mistakes are expensive;
- the trigger boundary changed materially;
- the user asks for measurable improvement.

If comparison testing is not practical, provide the prompts and review checklist instead of pretending that the comparison already happened.
