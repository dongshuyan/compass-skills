# Worked examples

Read these examples on first use, after rule changes, and for uncertain semantic
boundaries. Expected rewrites use only information present in the displayed input.

## Contents

1. English fact-safe rewrite
2. Chinese fact-safe rewrite
3. Process-leak removal
4. Zero-edit academic control
5. False-opposition triage
6. Generation without invented contrast
7. Manuscript-wide terminology control

## 1. English fact-safe rewrite

**Input**

> Heart failure represents a pivotal challenge in the evolving landscape of diabetes care, underscoring the critical importance of addressing cardiovascular comorbidities. Our groundbreaking findings showcase a remarkable 34% reduction in hospitalization—a testament to the transformative potential of this intervention—highlighting the need for a paradigm shift in clinical practice. Moreover, it is worth noting that these results may suggest that the treatment could potentially have the possibility of conferring benefits in select populations. Despite these challenges, the future looks bright for patients worldwide.

**Findings**

- E1: importance and novelty inflation;
- E2: promotional metaphor;
- E3: generic `-ing` tails;
- E7: stacked hedging;
- E9: unsupported ceremonial conclusion;
- E13: decorative dash insertion.

`Moreover` is not a defect. Its sentence is restructured because the surrounding
wording changes.

**Fact-safe rewrite**

> Heart failure is a challenge in diabetes care, particularly when cardiovascular comorbidities are present. Our findings show a 34% reduction in hospitalization. The results suggest that the treatment may benefit selected populations.

**Claim map**

| Source claim | Output |
|---|---|
| heart failure is a challenge in diabetes care | sentence 1 |
| cardiovascular comorbidities matter to that challenge | sentence 1 |
| the findings report a 34% reduction in hospitalization | sentence 2 |
| the treatment may benefit selected populations | sentence 3, with one hedge |

The rewrite does not add a trial, comparator, absolute/relative interpretation,
mechanism, prognosis claim, confirmatory study, or limitation.

## 2. Chinese fact-safe rewrite

**输入**

> 随着人工智能技术的不断发展，机器学习方法在医学影像领域的应用具有重要意义，为疾病诊断开启了新篇章。本研究不仅是一次方法上的改进，更是一场诊断范式的深刻变革。我们对模型进行了全面的、多维度的评估，结果极大地证明了该框架的先进性。综上所述，本方法赋能临床诊断，未来可期。

**发现**

- Z1：模板化开场；
- Z2：空泛拔高；
- Z3：无来源的修辞性对立；
- Z5：装饰性强调；
- Z6：商业黑话；
- Z9：万能结尾。

**事实安全改写**

> 机器学习方法已应用于医学影像诊断。本研究改进了现有方法，并对模型进行了多方面评估。评估结果支持该框架的改进效果。

**命题映射**

| 原文命题 | 输出位置 |
|---|---|
| 机器学习用于医学影像诊断 | 第一句 |
| 本研究包含方法改进 | 第二句 |
| 对模型进行了多方面评估 | 第二句 |
| 评估结果支持方法改进 | 第三句 |

改写没有增加准确率、鲁棒性、推理效率、baseline、外部验证、临床适用
范围或未来工作。原文没有提供这些内容，不能用它们替换空话。

## 3. Process-leak removal

**Input**

> As requested, this section avoids AI-sounding phrasing and passive constructions. We examined the association between sleep duration and cognitive decline in 4,821 adults. Per the 200-word constraint, details of the sensitivity analyses appear in Appendix B. Shorter sleep duration was associated with faster decline in episodic memory (β = −0.14, p = 0.006).

**Clean artifact**

> We examined the association between sleep duration and cognitive decline in 4,821 adults. Details of the sensitivity analyses appear in Appendix B. Shorter sleep duration was associated with faster decline in episodic memory (β = −0.14, p = 0.006).

The first sentence is process-only. In the third source sentence, only the word-
limit preface is process text; the Appendix B claim remains. All quantities and
the association wording remain unchanged. No leak-check line is added to the
clean artifact.

If the user requested diagnostics, report the two removed spans after the clean
artifact and clearly label that report as editor notes.

## 4. Zero-edit academic control

**Input**

> Although the sample was drawn from a single province, the direction of the association was consistent across all six sensitivity analyses. Participants were followed for a median of 8.2 years; loss to follow-up was 4.7%. Based on these results, we examined whether the association differed by baseline education. However, the interaction term was not statistically significant (p = 0.31), and the stratified estimates were similar. These findings should therefore be interpreted as exploratory, and they may not generalize to urban populations.

**Decision: keep unchanged.**

- `Although`, `Based on these results`, `However`, and `therefore` carry logic.
- Method/Results passives are conventional.
- `may not generalize` is evidence-calibrated hedging.
- `statistically significant` is tied to a reported test.

Zero edits are a successful result. Do not vary sentence length or remove a
connective merely to demonstrate that the skill ran.

## 5. False-opposition triage

### 5.1 Unsupported rhetorical contrast: rewrite

**English input**

> The proposed cache is not merely an implementation detail; it is a paradigm shift in memory management.

No prior claim, definition, or evidence establishes `implementation detail` as an
alternative, and `paradigm shift` only escalates category. A fact-safe repair is:

> The proposed cache changes the memory-management procedure.

Do not add performance numbers, deployment claims, or an ablation.

**中文输入**

> 这不仅是一次参数压缩，更是一场推理范式的深刻变革。

X 被无来源地降格，Y 使用抽象拔高。若这句话是可用的全部来源，可改为：

> 该方法压缩了参数，并改变了推理流程。

两个原有内容点仍在；没有增加准确率、延迟或部署效果。

### 5.2 Supported experimental contrast: keep

> Prior work attributed the gain to larger batches [12]. With batch size fixed, the ablation retained a 2.1-point gain. The gain therefore reflects the normalization term rather than batch size.

Keep the contrast. X comes from cited prior work, and the fixed-batch ablation
supports the distinction. Removing `rather than batch size` would lose the result.

> 已有工作将增益归因于更大的批量[12]。在批量固定的消融实验中，模型仍提升2.1个百分点。因此，增益来自归一化项，而非批量变化。

同样保留。句式表面命中不能覆盖实验逻辑。

### 5.3 Concrete but unsupported contrast: flag

> The improvement is not due to augmentation but to calibration.

> 性能提升并非来自数据增强，而是来自校准策略。

Both sides are concrete causal-attribution claims, but the displayed context has
no evidence. Do not delete X, assert Y, or invent an ablation. In detect mode,
flag and request support. In rewrite/edit mode, preserve or ask before changing.

### 5.4 Additive form with two supported claims: keep both

> The method not only reduces memory use by 18% but also cuts latency by 9 ms.

> 该方法不仅将显存占用降低18%，还将延迟减少9毫秒。

Both clauses carry quantified findings. The construction may remain. A neutral
addition is also possible, but any rewrite must preserve both values and claims.

## 6. Generation without invented contrast

**Supplied facts**

- latency decreased from 41 ms to 33 ms;
- accuracy was unchanged.

**Acceptable draft**

> Latency decreased from 41 ms to 33 ms, while accuracy remained unchanged.

Do not generate `This is not merely a speed improvement but a new efficiency
paradigm`. That sentence invents a downgraded X and an unsupported Y.

## 7. Manuscript-wide terminology control

### 7.1 Coined-name drift: normalize

**Definition in Methods**

> We call this component the Adaptive Evidence Router.

**Later caption**

> The adaptive evidence routing module selects two passages.

The definition establishes `Adaptive Evidence Router` as the canonical coined
name. If no abbreviation was declared, revise the caption to:

> The Adaptive Evidence Router selects two passages.

The replacement changes no claim. Capitalization and wording remain stable
across Methods, Results, and captions.

### 7.2 Declared abbreviation: keep

> We introduce the Adaptive Evidence Router (AER). AER selects two passages.

Keep both forms and record `AER` as allowed. The full name introduces the mapping;
later use of the abbreviation is controlled variation, not drift.

### 7.3 Distinct concepts: keep separate

> The evidence encoder embeds passages, whereas the Adaptive Evidence Router selects them.

Do not normalize `evidence encoder` to `Adaptive Evidence Router`. Their reported
functions differ, so the terminology ledger records an intentional distinction.

### 7.4 Uncertain identity: flag

> 该框架生成候选证据。随后，该方法对候选证据进行排序。

The excerpt does not establish whether `该框架` and `该方法` denote the same
technical object. Preserve the text and ask the author; frequency or proximity
cannot resolve identity.

### 7.5 Protected prior-work term: keep

> Prior work calls this component the "confidence layer" [12]. We define our component as the calibration layer.

The quoted historical term belongs to prior work and remains unchanged. The
manuscript-owned component uses `calibration layer` elsewhere.
