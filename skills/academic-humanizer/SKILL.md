---
name: academic-humanizer
description: >-
  Draft, audit, or minimally revise English- or Chinese-language academic prose
  to reduce formulaic, vacuous, mechanically repetitive, or process-leaking
  language while preserving claims, evidence strength, logical relations,
  manuscript-wide terminology identity, and scholarly register. Use for papers,
  abstracts, grants, cover letters, and
  reviewer responses when the user asks to de-AI, humanize, audit AI-like
  phrasing, or rewrite text without changing meaning. English is primary;
  Chinese is supported. Not for detector evasion, policy circumvention, pure
  translation, non-academic copy, or adding facts, citations, examples, or
  author experiences that the source does not contain.
---

# Academic Humanizer

Improve academic prose by removing observable writing defects, not by imitating
imperfection or optimizing an authorship detector. Preserve the author's facts,
argument, uncertainty, and disciplinary voice. This skill does not guarantee how
any reader or detector will classify a text.

## Portability

This skill is agent-agnostic. Its core behavior is defined by `SKILL.md` and
`references/`; Python is optional and supports reproducible diagnostics.

- Resolve `<skill-dir>` from the directory containing this `SKILL.md`.
- Let `<python>` mean an available Python 3 launcher, such as `python3`, `py -3`,
  or `python`.
- Let `<input-file>` mean a user-authorized local text file. Quote paths that
  contain spaces and use the host shell's path separator.
- Do not assume a fixed skill root, home directory, shell, operating system,
  agent name, or path separator.
- `agents/openai.yaml` is optional interface metadata. Core behavior does not
  depend on a particular agent runtime.
- If Python is unavailable, skip the scripts and apply the same contracts
  directly.

## Load the operating references

Read these before drafting or editing:

1. [Semantic contract](references/semantic-contract.md) for claim preservation,
   locked spans, deletion safety, and the internal claim ledger.
2. [Terminology contract](references/terminology-contract.md) for canonical terms,
   declared aliases, coined names, intentional distinctions, and the internal
   terminology ledger. Always load it for multi-span or manuscript-level work.
3. [Academic whitelist](references/whitelist-academic.md) for protected scholarly
   forms in both languages.
4. [Contrast logic](references/contrast-logic.md) for false-opposition triage in
   English and Chinese. Always load it; this is a cross-language semantic rule.
5. Route once by the majority language of editable prose, then read exactly one:
   [English rules](references/rules-en.md) or
   [Chinese rules](references/rules-zh.md).

Read [worked examples](references/examples.md) on first use, after changing a
rule, or whenever fact preservation, contrast, or over-correction is uncertain.
Read [metrics specification](references/metrics-spec.md) before running
`scripts/metrics.py`; its output is descriptive evidence only.

## Supported operations

- **generate**: draft from user-supplied claims, outline, data, and sources.
- **detect**: identify high-confidence defects without rewriting.
- **rewrite**: minimally revise supplied prose; this is the default when the user
  asks to de-AI or humanize text.
- **edit**: apply the same minimal revisions to a named file.

Do not create another routing tree for paper section or discipline. Methods,
Results, Discussion, reviewer responses, and grants use the same contracts; the
whitelist handles legitimate register differences. Ask one direct question only
when the requested genre changes what counts as acceptable and context does not
resolve it.

## Language route

Route on editable prose, excluding fenced code, formulas, block quotations, and
a trailing reference list. Use orthographic tokens: each CJK character is one
token and each contiguous Latin word is one token. This keeps embedded terms such
as `Transformer` or `ImageNet` from outweighing the Chinese sentence around them:

`r = CJK tokens / (CJK tokens + Latin word tokens)`

- `r >= 0.5`: Chinese branch.
- `r < 0.5`: English branch.
- No countable prose: stop and ask for text or an intended output language.

English terms in Chinese prose and Chinese terms in English prose remain
verbatim. If Python is available and the route is genuinely unclear, optionally
run `<python> "<skill-dir>/scripts/metrics.py" "<input-file>" --route`.
Routing is internal and never appears in the clean artifact.

## Single arbitration order

Earlier rows win. References may elaborate this table but must not define a
second priority order.

| Priority | Constraint | Operational meaning |
|---|---|---|
| **C0** | Artifact boundary | Process instructions, editor narration, and tool residue never enter the artifact. C0 applies only to process-layer text; it never authorizes deletion of real content. |
| **C1** | Semantic fidelity | Every output claim maps to the source bundle; every material source claim remains represented. No added facts, relations, examples, citations, motivations, or limitations. |
| **C2** | Locked-span protection | Quotations, formulas, code, references, citation keys, statistical notation, proper nouns, and requested verbatim text remain unchanged. |
| **C3** | Terminology identity | One scientific concept uses one canonical term across the editable manuscript. Preserve declared full-name/abbreviation pairs, necessary grammatical forms, and intentional distinctions; never infer identity from similarity alone. |
| **C4** | Academic register | Preserve functional hedging, passive voice, nominalization, discourse markers, and Chinese scholarly morphology. |
| **C5** | Argument structure | Preserve causal strength, contrast, concession, addition, chronology, scope, and paragraph-level reasoning. Surface connectives may change when the relation survives. |
| **C6** | Style repair | Apply language-specific rules only to supported, vacuous, mechanical, or stacked defects. |

Examples of conflict resolution:

- A style rule suggests adding a number, mechanism, baseline, or limitation that
  is absent from the source: C1 blocks the addition.
- A leak and a result share one sentence: C0 removes only the process phrase;
  C1 and C5 preserve the result and its relation to adjacent sentences.
- A coined method name drifts across the abstract, body, and caption: C3 restores
  the canonical term after C1 and C2 confirm that the referent and spans permit it.
- A passive sentence is conventional in Methods: C4 blocks stylistic activation.
- A contrast pattern is present but its two concrete claims lack surrounding
  evidence: C1 blocks automatic deletion; mark it uncertain in diagnostic output.

## Workflow

### 1. Read the complete editable scope

Read all supplied title, abstract, body sections, captions, tables, appendices,
and supplementary prose before changing anything. Identify which parts are
editable and which are evidence or protected context. Separate content
requirements from style/process instructions. For generation, treat only
supplied claims, data, citations, and explicitly marked hypotheticals as content.

### 2. Lock spans and build both ledgers

Apply the semantic and terminology contracts. Build the claim ledger with
source-to-output mappings for:

- numbers, units, entities, citations, datasets, methods, and study design;
- negation, comparison direction and baseline;
- association, causation, prediction, and attribution;
- modality, uncertainty, limitations, population, time, and scope.

Build a separate terminology ledger for scientific concepts, especially newly
coined methods, modules, losses, metrics, datasets, and task names. Record:

- `concept_id`, `canonical_term`, and the span that defines or first formally
  names the concept;
- declared `allowed_forms`, including full-name/abbreviation pairs and necessary
  grammatical or bilingual mappings;
- `observed_variants`, `distinguish_from`, and resolution `status`.

Use explicit user terminology first, then formal definitions, then the first
unambiguous formal naming. Frequency alone never selects the canonical term.
Keep both ledgers internal unless the user asks for an audit trail.

### 3. Audit in priority order

1. Find process leakage and tool residue.
2. Audit terminology across the complete editable scope. Classify each apparent
   variation as **declared form**, **same-concept drift**, **intentional
   distinction**, **protected mention**, or **uncertain identity**.
3. Triage contrast candidates as **protected**, **unsupported rhetorical**, or
   **uncertain** using `contrast-logic.md`.
4. Apply the routed language rules with three questions:
   - **Load**: does the wording carry a claim or logical relation?
   - **Support**: can each claim be traced to the source bundle?
   - **Patterning**: is the defect mechanical, vacuous, or reinforced by other
     signals in the same span?

A lone word or sentence form is not enough. Multiple weak signals in one span
form one finding, not several duplicate findings.

### 4. Make the smallest sufficient edit

- Remove process-layer text while retaining any content in the same sentence.
- Normalize confirmed same-concept drift to the ledger's canonical term across
  every editable occurrence, including captions and tables. Preserve declared
  abbreviations and grammatical forms; do not replace protected mentions.
- Keep terms separate when they name distinct concepts. If identity is uncertain,
  preserve the text and ask or flag it outside the clean artifact.
- Prefer subtraction or direct wording when a phrase carries no proposition.
- Use concrete material only when it already exists in the source.
- Preserve both claims in additive forms such as `not only X but also Y` when X
  and Y are supported; removing the construction must not remove either claim.
- Preserve or flag concrete negative claims when evidence is insufficient to
  decide whether the contrast is real. Do not silently erase them.
- Leave already competent prose unchanged.

### 5. Run the whole-manuscript terminology gate

Scan all editable sections together after revision. Every scientific concept
must use its canonical term or a declared allowed form. Verify that coined names
are unchanged after their formal introduction, captions and tables match the
body, bilingual mappings are declared, and distinct concepts remain distinct.
Any unresolved identity is a stop/flag result, not an automatic normalization.

### 6. Run the second-pass semantic and style gate

Re-read source and output side by side. The output fails if any answer is no:

1. Does every output claim map to the source bundle?
2. Does every material source claim remain?
3. Are numbers, negation, modality, causal strength, baseline, attribution, and
   scope unchanged?
4. Are locked spans byte-for-byte unchanged?
5. Does the terminology ledger show one canonical term per concept, with only
   declared forms and intentional distinctions remaining?
6. Did the edit preserve academic register and logical relations?
7. Is the artifact free of process labels, editor narration, placeholders filled
   by guesswork, and tool residue?
8. Would a zero-edit result have been more accurate? If yes, restore the source.

Run metrics only as an optional residual scan. A metric never overrides this gate.

## Output contract

- **generate / rewrite**: return the clean artifact by default, with no routing
  line, score, checklist, leak line, or editor preface.
- **detect**: return findings grouped by severity. Each finding includes an exact
  source quote, rule ID, reason, and one of `change`, `keep`, or `uncertain`.
- **edit**: edit only the requested file, then summarize changes outside it.
- Provide diagnostics after the artifact only when the user explicitly asks for
  them. Clearly separate diagnostics from text intended for the manuscript.
- Use verified counts only. Never invent a count or aesthetic grade.

## Stop conditions

Stop and ask instead of guessing when:

- the requested rewrite requires a missing fact, citation, comparison, or source;
- a concrete contrast cannot be validated from the available context;
- two labels may refer to the same scientific concept but the manuscript does
  not establish their identity, or no canonical term can be grounded;
- the input is mostly a protected quotation, formula, or reference list;
- the requested language is neither English nor Chinese;
- the request seeks detector evasion or circumvention of a disclosure policy.

Do not invent specifics, personal experience, citations, data, mechanisms,
baselines, or limitations to make prose sound more human. Do not casualize
academic writing merely to make it look less generated.
