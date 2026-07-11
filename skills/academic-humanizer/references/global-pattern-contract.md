# Local-to-document pattern contract

Use this contract for every multi-sentence generation, detection, rewrite, or
file edit. It separates a locally defective expression from a pattern that only
becomes defective through repetition, clustering, or positional regularity.

## Contents

1. Evidence stance and scope
2. Units and distribution map
3. Candidate families
4. Two-level activation test
5. Protected recurrence
6. Whole-document repair
7. Optional deterministic profile
8. Final gate

## 1. Evidence stance and scope

Treat dashes, connectives, contrast, parallel lists, sentence length, and other
surface forms as editing candidates, never proof of machine authorship. Their
frequency varies with language, model, prompt, domain, genre, and section. A
single occurrence is often legitimate; even a frequent form may be required by
Methods, Results, formal proofs, definitions, or reviewer responses.

Apply the global pass only to the supplied editable scope. A sentence supports a
local judgment. Multiple paragraphs support a distributional judgment about
those paragraphs. Only a complete supplied manuscript supports a claim of
whole-manuscript review. State a scope limitation outside the clean artifact
when the requested judgment exceeds the available text.

Do not use a universal count, percentage, sentence-length target, or healthy
range. Within-document distribution and rhetorical function control the audit.

## 2. Units and distribution map

Build an internal map after locking nonprose and quoted spans. Record candidates
at these levels:

| Level | Record |
|---|---|
| sentence | pattern family, exact span, position, claim/relation load |
| paragraph | sentence sequence, opening/closing function, candidate cluster |
| section | genre function, expected parallelism, length sequence |
| document | recurrence, dispersion, dominant template, cross-section transfer |

For each candidate family, inspect five dimensions:

1. **recurrence**: how often the form or rhetorical move returns;
2. **dispersion**: whether it is isolated, clustered, or spread across sections;
3. **position**: whether it repeatedly occupies sentence starts, paragraph ends,
   or the same step in a paragraph template;
4. **function**: whether each occurrence expresses a necessary relation or merely
   repeats emphasis, coverage, or ceremony;
5. **interaction**: whether several families reinforce one mechanical pattern.

Counts and locations are descriptive evidence. They never make the decision.

## 3. Candidate families

### G1. Punctuation and sentence-initial routing

Map dashes and repeated sentence-initial markers such as `此外`, `然而`, and
`值得注意的是` or their English counterparts. Preserve punctuation that marks a
real boundary and markers that disambiguate addition, contrast, cause, or scope.
Audit repeated openings when the relation is already clear or every sentence is
announced in the same way.

### G2. Opposition scaffolds

Map repeated `not X but Y` / `不是 X 而是 Y` families, then run
`contrast-logic.md` on every occurrence. Repetition can expose a dominant
rhetorical template, but it never invalidates a supported contrast. Repair only
unsupported staging or redundant recurrence.

### G3. Parallel triads and exhaustive coverage

Map three-part lists, repeated adjective triples, `首先—其次—最后`, and flat
coverage of every imaginable case. Preserve real metrics, contributions,
conditions, steps, and taxonomies. A list is defective when its items are
interchangeable abstractions, when enumeration replaces an available argument
hierarchy, or when repeated triads manufacture completeness without evidence.

Reorganize only with relations already present in the source. Do not invent a
taxonomy, omit a condition, or collapse distinct cases for elegance.

### G4. Repeated templates and rhetorical moves

Map recurring sentence openings, clause frames, paragraph sequences, and
background-list-summary molds. Evaluate the function sequence, not only exact
words. A document can repeat one template while changing vocabulary.

Parallel Results, protocol steps, definitions, and structured abstracts may
require repeated frames. Elsewhere, change structure only when the template
obscures the actual reasoning.

### G5. Sentence rhythm

Inspect the ordered sentence-length sequence within each functional section.
Uniformly long, uniformly short, or mechanically alternating sentences are
candidates when the rhythm conflicts with information structure. Do not vary
length for its own sake. Split or combine sentences only where propositions and
relations define a natural boundary.

### G6. Ending elevation and rhetorical-peak saturation

Map unsupported elevation near sentence or paragraph endings, including repeated
`彰显了`, `反映了`, `标志着`, generic importance, and aphoristic conclusions.
One evidence-backed synthesis may be appropriate. Repeated abstract peaks are a
distributional defect when several paragraphs end by restating importance rather
than advancing or delimiting the argument.

Delete empty elevation; retain a sourced implication, limitation, or synthesis.
Do not manufacture a weaker slogan to replace a stronger slogan.

### G7. Certainty and epistemic calibration

Map categorical expressions such as `一定`, `必然`, `毫无疑问`, `无疑`, and
English equivalents. Compare each with the claim/evidence ledger. Preserve
deductive consequences, definitions, proven invariants, and source-calibrated
certainty. Repair certainty that exceeds observational, exploratory, incomplete,
or unverified evidence.

Repeated certainty is both a distribution signal and a semantic risk. C1 blocks
weakening or strengthening until the source establishes the intended evidence
level.

## 4. Two-level activation test

Choose one classification:

- **local defect**: the individual span is unsupported, vacuous, misleading, or
  semantically excessive even if it appears once;
- **distributional defect**: individual instances can be grammatical, but their
  recurrence/position and redundant function dominate the supplied scope;
- **functional/protected**: recurrence follows evidence, section convention, or
  an explicit parallel structure;
- **uncertain**: available scope or evidence cannot support a decision.

A distributional defect requires two findings together:

1. recurrence, clustering, or positional regularity; and
2. repeated rhetorical function that adds no necessary claim or relation.

Lexical count alone is insufficient. A single unsupported factual claim or false
causal relation remains a local defect under C1 even without repetition.

## 5. Protected recurrence

Keep repeated forms when they encode:

- parallel experimental conditions, metrics, outcomes, or error categories;
- ordered method/protocol steps or a supplied taxonomy;
- theorem premises and consequences;
- repeated terminology required by `terminology-contract.md`;
- citations, quotations, survey items, and attributed historical language;
- genuine contrast, concession, or cause that would become ambiguous if removed;
- venue-required structured labels or reviewer-by-reviewer responses.

Do not replace canonical terminology with synonyms to create superficial variety.

## 6. Whole-document repair

Repair the argument system, not a counter:

1. preserve the claim, evidence, polarity, scope, and terminology ledgers;
2. select the smallest redundant occurrences whose removal breaks the mechanical
   pattern;
3. retain explicit connectives where the relation would otherwise be unclear;
4. group lists only by source-supported hierarchy;
5. let sentence boundaries follow proposition and relation boundaries;
6. retain one justified synthesis where it performs real argumentative work;
7. rescan the document to ensure the repair did not create a new repeated frame.

Do not randomly swap synonyms, force long-short alternation, delete every dash or
triad, or distribute a fixed number of rhetorical peaks. A zero-edit global pass
is valid when all recurrence is functional.

## 7. Optional deterministic profile

`scripts/metrics.py` can report paragraph/sentence scope, sentence-length
sequence, candidate locations, and distributions for selected surface families.
Use the profile to find where to read; do not use it to decide what to rewrite.
It cannot identify semantic equivalence, argument hierarchy, a “golden sentence,”
or authorship.

## 8. Final gate

The supplied scope passes only when:

- every changed local span has a supported reason;
- every claimed distributional defect has both recurrence evidence and redundant
  function;
- functional repetition and section conventions remain intact;
- sentence rhythm follows information structure rather than a variation recipe;
- unsupported elevation and certainty no longer dominate the supplied scope;
- no repair added facts, categories, relations, or terminology variants;
- the stated audit scope matches the text actually inspected.

If any item fails, restore the safer wording or return an `uncertain` diagnostic.
