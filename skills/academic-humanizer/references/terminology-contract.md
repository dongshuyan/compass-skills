# Manuscript-wide terminology contract

Use this contract for every multi-span generation, rewrite, or file edit. Its
purpose is referential precision: one scientific concept has one canonical term
throughout the editable manuscript, while genuinely distinct concepts remain
distinct.

## Contents

1. Scope and invariant
2. Terminology ledger
3. Canonical-term authority
4. Allowed forms
5. Protected and distinct terms
6. Resolution procedure
7. Generation and revision rules
8. Optional deterministic audit
9. Final terminology gate

## 1. Scope and invariant

Apply the contract jointly to all supplied editable prose:

- title, abstract, keywords, and main text;
- headings, figure and table captions, labels, and notes;
- appendix and supplementary prose;
- reviewer responses or cover letters when they describe the same manuscript.

The invariant is concept-based, not word-based. The same concept uses its
canonical term or an explicitly allowed form everywhere. Similar-looking labels
for distinct models, modules, objectives, variables, cohorts, or measurements
must not be collapsed.

Newly coined names require the strongest protection. Once a method, component,
loss, metric, dataset, benchmark, or task is formally named, later sections must
reuse that name exactly unless the manuscript declares an abbreviation or
bilingual equivalent.

## 2. Terminology ledger

Build an internal ledger before style repair. Use one row per scientific concept:

| Field | Meaning |
|---|---|
| `concept_id` | stable internal identifier |
| `canonical_term` | exact preferred term for editable prose |
| `definition_span` | definition or first formal naming that grounds the term |
| `allowed_forms` | declared abbreviations, grammatical forms, or language mappings |
| `observed_variants` | other labels that may denote the same concept |
| `distinguish_from` | nearby concepts that must remain separate |
| `language_mapping` | explicit Chinese-English correspondence when supplied |
| `status` | `resolved`, `intentional-distinction`, or `uncertain` |

The ledger records identity decisions; it does not invent definitions. Keep it
internal unless the user requests diagnostics or an audit trail.

## 3. Canonical-term authority

Choose the canonical term using this order:

1. the user's glossary, nomenclature table, or explicit decision;
2. a formal definition or explicit naming statement in the source bundle;
3. the first unambiguous formal naming in the editable manuscript;
4. an author-approved resolution requested when the preceding evidence is absent.

Do not choose by raw frequency, stylistic preference, familiarity, or what sounds
more natural. A frequent variant may be the error. Preserve capitalization,
hyphenation, spacing, number, and acronym form when they are part of a coined
name.

## 4. Allowed forms

Variation is allowed only when it preserves a declared identity and serves a
real grammatical or cross-language function:

- a full name followed by its declared abbreviation, then the abbreviation;
- singular/plural or possessive inflection that grammar requires;
- a declared Chinese-English mapping in bilingual material;
- a notation symbol explicitly mapped to the named quantity;
- a short form explicitly introduced by the author.

An allowed form must be recorded in the ledger. Do not treat free synonymy,
paraphrase, generic hypernyms, or pronouns with unclear antecedents as declared
forms. Ordinary anaphora may remain when its referent is unambiguous and no
technical identity is lost.

## 5. Protected and distinct terms

Do not normalize inside locked spans:

- quotations, cited historical terminology, survey items, and verbatim policy;
- formulas, code, variable names, citation keys, and reference entries;
- proper names or user-locked text.

When prior work uses a different term, preserve that term as an attributed
mention. The manuscript's own term remains canonical for its concept.

Do not merge labels merely because they share words or appear near each other.
For example, an `evidence encoder` may embed passages while an `evidence router`
selects them; a model, its training objective, and its loss are distinct unless
the source explicitly equates them.

## 6. Resolution procedure

For each apparent variation:

1. identify the candidate occurrences across the complete editable scope;
2. compare definitions, inputs, outputs, role, notation, and cited provenance;
3. classify the pair as:
   - **declared form**: both forms are authorized;
   - **same-concept drift**: normalize editable occurrences;
   - **intentional distinction**: preserve both and record `distinguish_from`;
   - **protected mention**: preserve the quoted or attributed wording;
   - **uncertain identity**: preserve and ask or flag;
4. verify the classification against the claim ledger before editing;
5. after editing, rescan every supplied section, caption, table, and appendix.

Semantic evidence controls the decision. Lexical similarity only identifies a
candidate for review.

## 7. Generation and revision rules

During generation:

- establish a canonical term when a concept is first formally introduced;
- declare an abbreviation before using it alone;
- reuse the ledger during every later section;
- avoid creating alternative names to achieve lexical variety.

During revision:

- normalize only confirmed same-concept drift;
- make the smallest replacement that preserves syntax and every claim;
- do not modify locked spans or attributed historical names;
- do not rewrite one distinct concept into another;
- do not silently resolve uncertain identity.

If the requested edit covers only one excerpt, enforce local consistency and
state outside the clean artifact that manuscript-wide consistency requires the
remaining sections. Never claim a full-manuscript pass without seeing the full
editable scope.

## 8. Optional deterministic audit

`scripts/terminology_audit.py` checks an explicit JSON ledger against a text
file. It reports occurrences of declared `observed_variants` outside common
protected spans. The helper is candidate-level evidence only:

```bash
python3 scripts/terminology_audit.py paper.txt --ledger terms.json --json
```

The helper does not infer whether two terms denote the same concept and never
rewrites the manuscript. An empty report means that the supplied variants were
not found; it does not prove global conceptual consistency.

## 9. Final terminology gate

The terminology layer passes only when:

- every resolved scientific concept uses its canonical term or an allowed form;
- coined names remain exact after their formal introduction;
- title, abstract, body, captions, tables, and supplied appendices agree;
- every abbreviation and bilingual equivalent is declared;
- attributed terminology and locked spans remain unchanged;
- distinct concepts remain distinct;
- every uncertain identity is surfaced outside the clean artifact.

Failure at this gate blocks a claim that the manuscript is fully revised. Ask
for an author decision or return a precise diagnostic instead of guessing.
