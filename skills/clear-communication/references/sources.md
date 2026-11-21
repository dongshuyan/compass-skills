# Sources and attribution

Clear Communication combines instructions for choosing information, organizing an explanation, and checking that the result preserves the source. Its examples are hypothetical and were written for this skill.

## Writing principles

| Source | Inspected revision | Contribution |
| --- | --- | --- |
| [GPT with Taste](https://github.com/NB-Corp/gpt-with-taste/tree/079fb262b4d7932515ba4e6341fd57b6f2122f4a) | 079fb262b4d7932515ba4e6341fd57b6f2122f4a | Reader-first organization, selection of information that helps the current task, and removal of repetitive process reporting. |
| [plain-english](https://github.com/Tradelord223/plain-english/blob/d108f2b61544cdabb33cd67f6365faf3f51259a9/skills/plain-english/SKILL.md) | d108f2b61544cdabb33cd67f6365faf3f51259a9 | Preservation of facts, conditions, negation, certainty, operational state, and exact technical names. |
| [International Plain Language Federation definition, reproduced by Clarity](https://www.clarity-international.org/) | Institutional page checked on 2026-10-19 | Evaluating communication by whether the intended audience can locate, understand, and apply the information it needs. |

The first two projects informed and were adapted into the writing guidance. Their original MIT notices are included in [GPT with Taste's license](licenses/gpt-with-taste.txt) and [plain-english's license](licenses/plain-english.txt).

This package contains writing instructions and examples. It does not contain the upstream installers, hook implementations, model-instruction replacement machinery, or TOML helper. The GPT with Taste license is retained in full, including its upstream helper attribution.

## Evaluation references

| Source | Inspected revision | Contribution and limit |
| --- | --- | --- |
| [plain-writing-skill evaluation procedure](https://github.com/docwriter-org/plain-writing-skill/blob/f0d3630983ac7a82aa580f1c1509d72df739ee12/evals/README.md) | f0d3630983ac7a82aa580f1c1509d72df739ee12 | Same-task, same-model comparisons and anonymous judging. Its reported rule-following results do not establish a benefit for this skill. |
| [Agrawal and Carpuat, 2024: Do Text Simplification Systems Preserve Meaning? A Human Evaluation via Reading Comprehension](https://aclanthology.org/2024.tacl-1.24/) | TACL 12, pages 432-448 | Reading-comprehension questions as an aid to checking meaning preservation. Such questions cover only part of a document, so they supplement a full check of important information. |

These are methodological references; this package does not redistribute their datasets, evaluation code, paper, or reported results as its own.

## Evidence and runtime boundaries

The skill defines a workflow for a language model to follow. Package validation and successful installation check its structure and availability; they do not measure reader comprehension or guarantee that every response improves.

The core instructions use no host-specific tool names, absolute machine paths, shell commands, scripts, model settings, network services, or hardware interfaces. Hosts determine discovery, invocation, permissions, and context retention. The optional OpenAI interface file supplies display metadata and is not required to read or follow the skill.

## Local skill-design references

The package structure and routing guidance were also checked against the repository's [skill design protocol](../../run-history-skill-builder/references/skill-design-protocol.md) and [skill-writing tutorial](../../../skill-writing-tutorial.html). They support few strong routes, progressive disclosure, explicit evidence and state gates, and small verifiable checks. They are design inputs for this package, not evidence that the communication behavior has been benchmarked.
