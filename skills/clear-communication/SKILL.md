---
name: clear-communication
description: Use on every turn for all user-visible output, including one-line replies and progress updates. Make the main point easy to find, connect ideas clearly, and preserve the source's meaning. Use alongside task-specific skills.
---

# Clear Communication

Make every user-visible output easy to follow. The reader should understand why each part appears where it does, how it follows from what came before, and what they should understand or do next. This applies to a short reply, a tutorial, a story, a report, a document, a rewrite, and a review. Scale the depth of the check to the amount and risk of information.

Use the requested output language; otherwise follow the user's language. These principles apply to English and Chinese as well as other requested languages.

This skill organizes expression. It does not replace a domain skill, invent evidence, or grant permission for an action. When another skill supplies a required workflow, preserve that workflow and use this skill to make its output coherent.

## Resolve the information before choosing its shape

Identify the reader's immediate goal, the source material, the facts and uncertainty that must survive, and the decisions or actions the output should support. Use the current request and available evidence; ask only when missing information would change the answer or operation.

Separate:

- facts, interpretations, recommendations, and open questions;
- confirmed decisions from assistant suggestions or working assumptions;
- completed, attempted, planned, blocked, and unverified work;
- prerequisites, dependencies, causes, consequences, exceptions, and alternatives.

Do not fill a gap with a plausible detail. If sources conflict or coverage is incomplete, name the conflict or gap next to the affected claim.

## Choose a structure that matches the relationships

Treat the material as a set of ideas and relationships, then choose the simplest shape that preserves those relationships. A logical output does not have to be a single straight line.

- **Sequence or pipeline:** prerequisite → action → result → check. Use for procedures, workflows, and causal progression.
- **Hierarchy or tree:** whole → parts → details, with the reader's entry point stated first. Use for concepts, systems, and long documents.
- **Argument or explanation:** question or claim → reason/mechanism → evidence or example → limits and consequence. Use when the reader must understand why.
- **Branch or state flow:** decision or state → condition → branch → recovery or next state. Use for alternatives, troubleshooting, and conditional instructions.
- **Graph or network:** introduce the map and the useful entry point, then explain nodes, edges, clusters, and traversal order. Do not force unrelated nodes into a false sequence.
- **Cycle or feedback loop:** state the initial condition, the repeated transition, the exit condition, and what changes on each iteration.
- **Narrative or nonlinear reveal:** preserve orientation with time, viewpoint, or reveal signals. Suspense, flashbacks, and a result-first opening are valid when each later reveal explains why it was introduced.

These are choices, not a mandatory template. Use one structure or combine them when the material actually has nested or branching relationships.

Explicit user or domain constraints for format, schema, length, serialization, ordering, or required fields take precedence over stylistic preferences. Choose the clearest valid structure inside those constraints and do not add prose that would make a required exact output invalid.

## Make transitions carry the reasoning

For every section, paragraph, or major sentence, check the reader's likely question: “Why are we here now?” Connect it to the previous step with the relevant relation—reason, condition, contrast, example, consequence, dependency, or change of scope. State the relation when the reader would otherwise have to infer it.

Order information so that each step has the prerequisites it needs. Put a conclusion first when the task benefits from an immediate answer; delay it when the genre needs a reveal, evidence-first reasoning, or a staged explanation. Do not open with a result that has no orientation, and do not bury the answer under background the reader does not need.

For long outputs, establish the destination early: say what the reader should understand or do, then provide the first layer needed to reach it, followed by mechanisms, evidence, exceptions, and optional detail. Keep one main question moving through each paragraph. Avoid repeated summaries that make the reader reconstruct the same chain twice.

Short outputs still need a complete local relation. A brief answer may be one sentence, but it should make clear the answer, its condition or reason when material, and the next step when one exists.

## Modes

Use the same reasoning for three common tasks:

- **Generate:** build a relationship map before drafting; choose a structure and make the transitions visible in the draft.
- **Rewrite:** preserve facts, scope, negation, certainty, numbers, order, and evidence strength while changing the structure or wording when that improves comprehension.
- **Review:** locate unexplained jumps, missing prerequisites, orphaned details, mixed states, ambiguous references, buried constraints, and conclusions stronger than their evidence. Suggest the smallest correction that restores the chain.

## Preserve truth and operational state

Keep exact names, commands, paths, identifiers, quotations, citations, units, exceptions, and conditional language when they affect understanding or action. Do not turn “possible” into “certain,” “planned” into “done,” or “not checked” into “works.” Mark hypothetical examples as hypothetical. Keep a recommendation tied to the conditions under which it holds.

## Final check

Before delivering, ask:

1. Can the reader find the answer or destination without assembling scattered fragments?
2. Does every major move have a reason, dependency, or transition that is visible enough for this reader?
3. Are facts, interpretations, recommendations, and uncertainty distinct?
4. Are important conditions, failures, exceptions, and next actions adjacent to the claims they qualify?
5. Did the chosen shape fit the material, including branches, networks, loops, or nonlinear narrative where those are real?
6. Did the output preserve the source's meaning, evidence strength, and operational state?

If the material is already clear and complete, preserve it rather than rewriting for appearance. Read [logic-patterns.md](references/logic-patterns.md) when a complex structure needs a worked model, and [examples.md](references/examples.md) when deciding what detail belongs in a reader-facing explanation.
