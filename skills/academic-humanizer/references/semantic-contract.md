# Semantic preservation contract

Use this contract for every generation, rewrite, or file edit. Style repair is
valid only inside these boundaries.

## Contents

1. Source bundle
2. Locked spans
3. Internal claim and evidence ledger
4. Allowed transformations
5. Prohibited transformations
6. Deletion safety test
7. Generation contract
8. Final semantic gate

## 1. Source bundle

The source bundle contains:

- the editable text;
- facts, data, citations, outline points, and sources supplied by the user;
- explicit user decisions about intended meaning;
- user-supplied glossaries, nomenclature, abbreviations, and terminology decisions;
- clearly marked hypothetical premises.

The editable draft is authoritative for the claim the author currently intends
to express. It is not independent proof that a cited work, quotation, reported
result, or external fact exists. Supplied data, reference entries, source files,
and explicit user assertions provide provenance at different strengths; record
the distinction instead of treating all manuscript sentences as verified facts.

Style requests, checklists, word limits, editor instructions, and conversation
about how to write belong to the process layer. They are not manuscript claims.

## 2. Locked spans

Do not rewrite:

- direct quotations and translated passages marked as quotations;
- formulas, equations, code, variable names, units, and statistical notation;
- reference-list entries, citation keys, and citation markers;
- proper nouns, dataset/model/instrument names, formally established canonical
  coined names, and verbatim policy text;
- text the user explicitly requires verbatim.

You may flag a suspected error outside the clean artifact. Do not silently repair
a locked span.

## 3. Internal claim and evidence ledger

Before editing, map each material source claim to an internal ID. Record only what
is needed to verify the rewrite:

| Field | Preserve exactly |
|---|---|
| entities and setting | author/agent, population, dataset, method, place, time |
| quantities | number, unit, sign, interval, uncertainty, denominator |
| relation | association, cause, prediction, comparison, definition, attribution |
| polarity | affirmation, negation, exception, absence, failure |
| comparison | baseline, direction, dimension, scope |
| strength | may, suggests, supports, shows, demonstrates, proves |
| boundaries | limitation, condition, population, venue, intended use |
| provenance | citation, quotation, user statement, supplied source |
| evidence status | supplied source, user-asserted, draft-only, hypothetical, verified |

After editing, map every output claim back to a source ID and verify that every
material source ID remains represented.

`draft-only` means the proposition exists in the draft but the evidence it cites
or implies was not supplied or verified. In rewrite/edit mode, preserve the claim
and flag the evidence gap outside the clean artifact. Do not silently validate,
delete, or extend it. In generation mode, do not use a draft-only premise to
create a new result, mechanism, citation, or downstream conclusion.

Concept identity is recorded separately in the terminology ledger defined by
`terminology-contract.md`. The claim ledger establishes what each concept does;
the terminology ledger establishes which names may refer to it. Neither ledger
may override the other.

## 4. Allowed transformations

- delete process-layer leakage while preserving content in the same sentence;
- delete or compress wording that carries no proposition or logical relation;
- replace promotional or vague wording with a plainer expression of the same claim;
- combine or split sentences when all claims and relations survive;
- change a connective or sentence order when contrast, addition, cause,
  concession, chronology, and scope remain unchanged;
- normalize confirmed terminology drift under `terminology-contract.md` and
  normalize repetition or punctuation without changing content;
- reduce unsupported certainty or elevation when the supplied evidence already
  establishes a weaker relation;
- turn a supported additive contrast into a neutral additive sentence while
  preserving both X and Y.

## 5. Prohibited transformations

Do not add or infer:

- a number, citation, comparator, baseline, dataset, population, or method detail;
- a mechanism, motivation, example, author intention, or personal experience;
- a limitation, future-work item, practical implication, or generalization;
- causal force, certainty, novelty, significance, or scope beyond the source;
- a negative premise introduced only so it can be rejected;
- an actor such as `we observed` when the source does not identify that actor.

Do not treat a citation-shaped string, plausible author/year pair, polished
quotation, or confident sentence as verified evidence. Do not fabricate missing
bibliographic details or replace an unverified claim with a plausible alternative.

Do not infer that two labels denote the same concept merely because their words,
locations, or functions appear similar. Uncertain identity must remain unchanged
until the author resolves it.

Do not delete a concrete negation, comparison, limitation, or attribution merely
because its surface form resembles an AI pattern.

## 6. Deletion safety test

Before deleting a span, ask:

1. Does it assert, deny, quantify, attribute, limit, compare, or connect anything?
2. Would deletion change what a reader believes about the evidence or argument?
3. Does adjacent text depend on the relation it expresses?

If any answer is yes, preserve the meaning through direct wording or flag the
case as uncertain. If all are no, the span is eligible for subtraction.

For false-opposition candidates, X is itself a proposition. A concrete X cannot
be removed automatically just because it lacks local support; use the uncertainty
path in `contrast-logic.md`.

## 7. Generation contract

Build claims only from the supplied source bundle. Missing content remains
missing: ask, use a visible user-approved placeholder, or omit the unsupported
claim. Never generate a plausible citation, result, contrast, mechanism, example,
or limitation.

Hypotheticals must be marked as hypothetical. A model-generated illustration is
not evidence and must not be presented as an observed case.

## 8. Final semantic gate

The artifact passes only when:

- output-to-source mapping has no unsupported claim;
- source-to-output mapping has no material omission;
- locked spans are unchanged;
- polarity, modality, causal force, comparison direction, baseline, and scope match;
- process text and tool residue are absent;
- uncertainty remains uncertainty.
- every evidence-bearing claim is either grounded in supplied/verified material
  or retained with a `draft-only` diagnostic outside the artifact;

Run the whole-manuscript terminology gate in `terminology-contract.md` alongside
this semantic gate, and the whole-document pattern gate in
`global-pattern-contract.md`. Passing one gate does not compensate for failing
another.

Keep the ledger internal unless the user asks for it.
