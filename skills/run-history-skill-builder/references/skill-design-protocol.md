# Skill Design Protocol

Read this file after the workflow is reconstructed and before writing the package.

## Choose The Smallest Correct Package

Start with:

```text
<skill-name>/
└── SKILL.md
```

Add directories only when they have a clear job:

- `references/`: long branch-specific guidance, schemas, recovery notes, or source logs;
- `scripts/`: deterministic or repeated checks;
- `evals/`: trigger, regression, or boundary prompts worth preserving;
- `agents/`: optional UI metadata for hosts that use it;
- `assets/`: templates or files that the resulting skill must copy or consume.

Do not add per-skill `README`, installer scripts, or changelogs unless the user or release target explicitly needs them.

## Map Structure Owners

| Problem | Best owner |
| --- | --- |
| Trigger wording | `SKILL.md` frontmatter `description` |
| Main workflow and safety gates | `SKILL.md` body |
| Long branch details | `references/` |
| Deterministic checks | `scripts/` |
| Complex behavioral examples | `references/examples.md` |
| Trigger and regression prompts | `evals/evals.json` |

## Route Design

Keep routes few, strong, and verifiable.

- User-owned decisions: ask the user.
- Machine-checkable facts: script them, test them, or read them from files, diffs, schema, or validators.
- Weak branches such as "it seems okay" or "risk looks low" should be deleted or hardened into explicit gates.

## State Gates

Most packaged workflows need named checkpoints such as:

- input resolved;
- context understood;
- metadata ready;
- validation passed;
- risky action approved;
- success verified.

Do not claim later states without evidence for the earlier ones.

## Examples

Add one-shot or few-shot examples only when they preserve complex behavior that simple rules cannot express cleanly.

Every example should state:

- the invariant;
- the variable fields;
- the failure or ambiguity it prevents;
- the boundary where the example stops applying.

## Eval And Validation Strategy

Before shipping, make sure the package has enough checks to answer:

- When should it trigger?
- What files or resources are required?
- What should block risky steps?
- What proves success?
- What does the final response owe the user?

## Release Discipline

- Strip private paths, credentials, session data, and unrelated internal notes.
- Replace machine-specific examples with placeholders such as `<workspace>` or `<final-artifact>`.
- Keep commands portable: mention `python3`, `python`, or `py -3`, not one fixed runtime only.
- If the user asked for plan-only, stop before file creation and say so explicitly.
