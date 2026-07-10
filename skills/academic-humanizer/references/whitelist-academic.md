# Cross-language academic whitelist

Load this file for both languages. Protected forms outrank style-repair rules.
When evidence is insufficient, keep the text or flag uncertainty.

## Contents

1. Locked content
2. Functional discourse relations
3. Evidence-calibrated hedging
4. Passive voice and impersonal constructions
5. Terminology and scholarly compression
6. Chinese scholarly morphology and mixed text
7. Legitimate contrast
8. Register conventions
9. Mention-versus-use escape

## 1. Locked content

Never rewrite:

- direct quotations, interview excerpts, epigraphs, and marked translations;
- formulas, equations, code, variables, units, and statistical notation;
- reference-list entries, citation keys, and citation markers;
- verbatim legal or policy text;
- proper nouns, model/dataset/instrument names, and user-locked text.

Suspected errors may be reported outside the clean artifact. Do not silently
repair them.

## 2. Functional discourse relations

Keep a discourse marker when it makes a real relation explicit:

- EN: Although, Whereas, However, In contrast, Therefore, Thus, Accordingly,
  Moreover, Furthermore, Specifically, Based on these results, Taken together.
- ZH: 然而、相比之下、因此、据此、此外、与此同时、具体而言、基于上述结果、综上。

Surface wording may change if addition, contrast, concession, cause, chronology,
or conclusion remains clear. Repetition alone justifies a local restructure, not
deletion of the relation.

## 3. Evidence-calibrated hedging

Preserve uncertainty that matches the evidence:

- EN: may, might, could, appears to, suggests, is associated with, is consistent with.
- ZH: 可能、或可、结果提示、与……有关、与……一致、尚不能排除。

Observational or exploratory claims must not become causal or certain. Simplify
stacked hedges only when one well-placed hedge preserves the original strength.

## 4. Passive voice and impersonal constructions

Passive voice is normal in Methods and Results when procedure or outcome matters
more than actor. Preserve examples such as `Samples were incubated`, `Participants
were randomized`, `样本被随机分组`, and `数据经清洗后用于分析`.

Only question a passive when it hides an actor whose identity is material to the
claim. Passive density alone is not a defect.

## 5. Terminology and scholarly compression

Field-standard terminology is precision, not jargon. Preserve terms such as
heteroskedasticity, calibration error, weighted interval score, ablation study,
鲁棒性、显著性、异质性、消融实验、倾向得分匹配.

Apply [the terminology contract](terminology-contract.md) to manuscript-owned
terms. Preserve declared full-name/abbreviation pairs, coined names, bilingual
mappings, and intentional distinctions. Do not create synonyms for variety, and
do not collapse separate concepts merely because their names overlap.

Moderate nominalization and anaphoric compression (`this reduction`, `the
observation that`) are normal. Repair only empty abstraction chains.

## 6. Chinese scholarly morphology and mixed text

Protect:

- `进行 + V` when it marks a procedure naturally;
- established `性` / `化` terms;
- necessary subjectless sentences and passives;
- functional adverbs such as 约、略、基本、相对、持续;
- English abbreviations, model names, variables, and formulas in Chinese prose.

In English prose, preserve occasional Chinese names, cited titles, and terms.
Cross-language equivalents count as the same allowed form only when the source
or user declares the mapping.

## 7. Legitimate contrast

Contrast is protected when it has a source and argumentative function:

- cited prior interpretation or misconception;
- competing hypothesis, baseline, or ablation attribution;
- negative versus positive result;
- technical definition or scope exclusion;
- reviewer-response clarification tied to an actual comment;
- additive findings where X and Y are both supported.

Use `contrast-logic.md`; never decide from `not X but Y` / `不是 X 而是 Y`
alone.

## 8. Register conventions

Preserve when appropriate to the venue or requested genre:

- Introduction signposting and contribution lists in fields that use them;
- structured abstract labels;
- explicit limitation and future-work statements with concrete content;
- grant or policy language required by a form or call;
- first person where the venue permits it;
- interrogative framing when it genuinely organizes the research question.

Ask when genre convention is outcome-determinative and context does not resolve it.

## 9. Mention-versus-use escape

A phrase is not a defect when quoted, cited, or analyzed as language. Do not flag
survey items such as `"To avoid sounding like AI"`, a paper discussing
AI-sounding prose, or a quoted `not X but Y` construction as process leakage or
false opposition in the surrounding paper.
