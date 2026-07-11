# English academic rules

Load this file only for English-majority editable prose. The semantic,
terminology, global-pattern, whitelist, contrast, and SKILL arbitration contracts
remain controlling.

## Contents

1. Activation standard
2. English pattern rules E1-E14
3. Generation constraints
4. Final language check

## 1. Activation standard

Edit locally when wording is vacuous, unsupported, or misleading. Edit globally
when recurrence and redundant function jointly create a dominant document
pattern. A word or construction is not defective merely because language models
often use it.

Before activating a rule, ask:

- What proposition or relation does the span carry?
- Is that proposition supported by the source bundle?
- Is the wording conventional in this section or discipline?
- Would the proposed edit preserve modality, polarity, comparison, and scope?

When uncertain, keep or flag. Do not force variation for its own sake.

## 2. English pattern rules

### E1. Empty significance and novelty inflation

Candidates: `pivotal`, `groundbreaking`, `transformative`, `remarkable`,
`paradigm shift`, `watershed`, `testament to`, `underscores the importance of`.

Act when the phrase contributes only importance or novelty without a supplied
reason. Delete the inflation or state the already-supplied result. Do not invent a
number, comparison, mechanism, or implication to make the sentence concrete.

Technical uses such as `statistically significant`, a defined `paradigm`, or a
cited novelty claim remain protected.

### E2. Promotional metaphor and business vocabulary

Candidates: `landscape`, `ecosystem`, `journey`, `unlock`, `unleash`, `leverage`,
`harness`, `seamless`, `game-changing`, `at its core`, `cutting-edge`.

Act when the word is metaphorical and replaceable by a direct technical action.
Preserve literal or field-standard uses. If no direct action exists in the source,
delete the ornament rather than supplying one.

### E3. Pseudo-analysis tails

Candidate: an `-ing` clause appended after a result to add generic importance,
applicability, or promise, for example `..., highlighting the broad potential...`.

End at the result when the tail adds no claim. Preserve an `-ing` clause that
states a sourced mechanism, condition, consequence, or simultaneous action.

### E4. Unsupported rhetorical contrast

Candidates include `not X but Y`, `not merely X`, `not only X but also Y`,
`less about X and more about Y`, and split-sentence variants.

Apply [contrast logic](contrast-logic.md). Occurrence count does not determine
validity. Preserve supported experimental, definitional, scope, and reviewer-
response contrasts. Flag concrete but unverified contrasts instead of deleting
them. In additive forms, preserve both supported claims.

### E5. Inflated copula substitutes

Candidates: `serves as`, `stands as`, `represents`, `boasts`, `features` where
`is` or `has` carries the same meaning.

Use the plain verb when the original verb adds no relation. Preserve `represents`
in mathematical, sampling, or explicit representational senses.

### E6. Ornamental intensifiers

Candidates: `remarkably`, `dramatically`, `fundamentally`, `deeply`, `vastly`,
`critically`, and unsupported `significantly`.

Keep magnitude or statistical language backed by the source. Otherwise delete
the intensifier; never manufacture a quantity.

### E7. Hedge stacking

Compress constructions such as `may suggest that X could potentially...` to the
minimum hedge that preserves the original evidence strength. Do not remove the
last hedge from observational, exploratory, or uncertain claims.

### E8. Vague attribution

Candidates: `experts argue`, `studies show`, `researchers believe` without a
source or identifiable referent.

Name the supplied source when present. Otherwise retain an appropriately limited
claim or flag the missing attribution. Never invent an author or citation.

### E9. Generic challenge and conclusion formulas

Candidates: `Despite these challenges`, `future research is warranted`, `the
future looks bright`, `only time will tell`, and generic `opens new avenues`.

Delete an empty closer or retain a specific finding, limitation, or open question
already in the source. Do not add a plausible limitation or future-work item.

### E10. Template opening and meta-narration

Candidates: `In today's rapidly evolving...`, `In recent years...` without a
specific fact, `This section will explore...`, `Let us examine...`, assistant
prefaces, and process commentary.

Start with the actual subject or supplied context. Preserve conventional section
signposting when the venue uses it. Process leakage is governed by C0.

### E11. Decorative enumeration and rule-of-three

Preserve genuine three-part methods, outcomes, contributions, and criteria. Act
only when repeated triads or list scaffolds package interchangeable abstractions
without adding structure. Rewrite as direct prose; do not change the number of
substantive items.

For multi-paragraph recurrence, apply `global-pattern-contract.md`. Preserve a
single or repeated three-part list when the source genuinely contains three
metrics, contributions, stages, conditions, or outcomes.

### E12. False range and local lexical cycling

- Repair `from X to Y` when X and Y do not define a scale or span.
- Remove stylistic synonym cycling in ordinary prose when it obscures a stable
  referent.

Preserve established taxonomy, true ranges, and terminology required by the
field. Manuscript-wide scientific term identity, declared abbreviations, coined
names, and intentional distinctions are governed by
`terminology-contract.md`. Never merge genuinely different participant groups,
variables, models, modules, objectives, or measurements.

### E13. Mechanical rhythm and document patterning

Look for repeated sentence templates, repeated openings, decorative dash asides,
or paragraphs that all perform the same rhetorical sequence. Repair only the
repetition that impairs reading. A short Methods paragraph, parallel result list,
or single purposeful dash does not require variation.

Apply `global-pattern-contract.md` to sentence-initial connectives, ordered
sentence lengths, paragraph closures, triads, certainty, and rhetorical-peak
saturation. Do not impose sentence-length quotas or a universal dash budget.
Sentence form follows content and section function.

### E14. Tool, format, and placeholder residue

Flag or remove from the clean artifact:

- assistant prefaces and sign-offs;
- citation-rendering tokens and attachment markers;
- AI-tool tracking parameters while preserving the clean URL;
- Markdown markers inappropriate to the target format;
- unresolved placeholders.

Never fill a placeholder, repair a citation, or infer missing metadata without a
verified source.

## 3. Generation constraints

When drafting:

1. Start from supplied claims rather than a generic historical zoom-out.
2. Do not introduce a negative premise merely to reject it.
3. Use discourse markers, passive voice, hedging, and terminology when they carry
   academic function.
4. Vary syntax only as the content warrants; do not follow a sentence-length recipe.
5. Use lists only for genuinely enumerable material.
6. End on a supplied finding, boundary, or open question, or simply stop when the
   content is complete.
7. Mark hypotheticals and missing information honestly.
8. Treat a citation-shaped statement in the draft as a claim, not as proof that
   the cited evidence exists; preserve and flag missing provenance.

## 4. Final language check

- No unsupported claim, attribution, comparison, mechanism, or limitation was added.
- No concrete negation or contrast was erased without grounding analysis.
- Functional hedging, passive voice, discourse relations, and domain terms remain.
- Promotional language and empty ceremony were removed without casualizing prose.
- Terminology has passed the manuscript-wide contract; ordinary referents are stable.
- The global pattern gate passed without suppressing functional recurrence.
- Process commentary and tool residue are absent from the clean artifact.
