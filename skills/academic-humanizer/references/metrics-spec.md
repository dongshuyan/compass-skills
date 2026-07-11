# Metrics specification

`scripts/metrics.py` provides reproducible descriptive diagnostics. It does not
identify an author, assign an AI probability, or decide whether prose passes.

Terminology identity is outside this script's scope. Use the explicit-ledger
candidate helper documented in `terminology-contract.md` when a deterministic
residual scan is useful; semantic coreference still requires manuscript context.
The `global_patterns` profile supports `global-pattern-contract.md` by locating
surface candidates and ordered sentence lengths. It does not decide whether a
pattern is functional, defective, or machine-authored.

## Contents

1. Routing
2. Descriptive fields
3. Protected-span masking
4. Prohibited interpretations
5. Optional runtime commands

## Routing

Routing is based on editable prose after removing fenced/inline code, formulas,
Markdown block quotations, and a trailing References/Bibliography/Works
Cited/参考文献 section. Reference headings are normalized before matching:
case, Markdown heading marks, an optional section number, surrounding whitespace,
and a trailing ASCII or full-width colon do not affect recognition. Ordinary
sentences that merely begin with `References` or `参考文献` remain prose.

`r = CJK tokens / (CJK tokens + Latin word tokens)`

Each CJK character is one orthographic token; each contiguous Latin word is one
token. This practical tokenizer favors the surrounding Chinese grammar over a
few long embedded technical names. `r >= 0.5` routes Chinese; otherwise English.
No countable prose returns `unknown` rather than defaulting to English.

## Descriptive fields

| Field | Unit | Interpretation limit |
|---|---|---|
| `lexical_diversity` | English word TTR or Chinese character diversity plus token count | length-sensitive description; no normal range |
| `sentence_length` | word count (EN) or CJK characters + Latin words (ZH) | descriptive mean, spread, min, max |
| `transitions` | sentence-initial candidates per 100 sentences | high or low values are not defects by themselves |
| `passive_candidates` | conservative English sentence candidates | misses valid passives and may retain false positives; never a style target |
| `dashes` | mutually exclusive glyph/pair counts | punctuation inventory only |
| `leaks` | context-bearing regex candidates | quotations are masked; selected research-mention contexts are excluded; contextual review remains required |
| `contrast_candidates` | pattern candidates | candidate only; use `contrast-logic.md` for the decision |
| `global_patterns.scope` | prose paragraphs and sentences | describes only the supplied editable scope |
| `global_patterns.sentence_length_sequence` | ordered length by paragraph/sentence | no target variance or rhythm |
| `global_patterns.sentence_initial_markers` | marker, count, paragraph, sentence | relation and section function require review |
| `global_patterns.dash_distribution` | glyph counts and locations | no universal dash budget |
| `global_patterns.contrast_distribution` | contrast family and locations | semantic validity and repeated rhetorical function require review |
| `global_patterns.parallel_enumeration_candidates` | surface list candidates | cannot decide whether three items are substantive |
| `global_patterns.certainty_candidates` | lexical candidates and locations | compare with evidence strength before editing |
| `global_patterns.ending_elevation_candidates` | ending-position candidates | cannot identify a justified synthesis or “golden sentence” |
| `global_patterns.repeated_opening_candidates` | selected repeated opening families | incomplete recall; no syntactic parser |

Chinese character diversity is not lexical TTR. Traditional TTR is sensitive to
text length, so values from different lengths or languages are not comparable.

## Protected-span masking

Leak, contrast, and global-pattern scans mask direct quotations, fenced/inline
code, formulas, Markdown block quotations, and trailing references. This reduces
false positives but cannot parse every document format. Findings remain candidates.

Chinese process-leak rules distinguish three cases:

- a direct second-person request cue, such as `根据您的要求`;
- a generic request cue followed by a document target or editing action;
- an AI-style self-reference cue, excluding quoted and explicitly discussed
  research examples.

These distinctions improve candidate recall without turning a match into deletion
authority.

## Prohibited interpretations

Do not:

- combine fields into a score or probability;
- claim a universal healthy range;
- rewrite until a threshold is crossed;
- treat passive voice, transitions, sentence variance, or dashes as defects alone;
- infer a universal threshold from one document, language, section, or model;
- call a short excerpt a whole-document audit;
- treat a parallel list, categorical theorem consequence, or ending synthesis as
  defective without checking its content and function;
- use a regex candidate as automatic deletion evidence.

## Optional runtime commands

These commands do not modify the input file:

```bash
<python> "<skill-dir>/scripts/metrics.py" "<input-file>" --json
<python> "<skill-dir>/scripts/metrics.py" "<input-file>" --route
<python> "<skill-dir>/scripts/terminology_audit.py" "<input-file>" --ledger "<terms-file>" --json
```

The terminology audit consumes an author-supplied ledger and reports candidates;
it does not infer concept identity or rewrite the manuscript. The metrics profile
locates selected local and distributional candidates without assigning authorship
or quality.
