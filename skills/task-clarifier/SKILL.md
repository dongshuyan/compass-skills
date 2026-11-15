---
name: task-clarifier
description: >-
  Deep need-clarification skill. Use only when the user explicitly invokes
  $task-clarifier. Once activated, keep clarifying until three goals are met:
  the user understands their own needs, the AI understands the user's needs,
  and the user confirms the AI's understanding is correct. Do not intervene in
  task execution unless explicitly invoked.
---

# Task Clarifier

This skill clarifies a request. It does not execute the task. Execution may begin only after the user confirms the understanding and, for high-risk actions, approves them separately.

## Language Rule

Write user-facing output (questions, options, recommendations, alignment material, confirmation summaries) in the user's language. Detect it from the user's latest message; default to Chinese when unknown. The Chinese templates in this file are output forms, not a requirement to write in Chinese. When the user writes in another language, keep the same structure in that language. Keep code, paths, commands, identifiers, and quoted user text exactly as they are.

## Three Goals

All three must be met before this skill ends:

1. **The user understands their own needs**, including considerations they have not raised, latent contradictions, and implicit premises that would change the outcome.
2. **The AI understands the user's needs** completely and specifically, with sufficient support for understandings that affect the outcome. Identify both missing information and interpretations that already exist but lack support. No user-owned decision is filled with a default.
3. **The user can verify the AI's understanding.** It is stated in checkable form, and each inference is listed for confirmation or correction.

Focus on understandings that affect the goal, scope and non-goals, constraints, priorities, acceptance criteria, or execution direction; do not ask extra questions about irrelevant details. Sufficient support comes from the user's explicit statements about intent and choices, inspected materials that directly support the relevant facts, or valid inferences whose necessary premises are supported. User-owned decisions still require the user's statement or confirmation. For objective facts only the user can supply, use their explicit report to align the request and label it in the summary as "user-provided, not independently verified." This establishes the source and the understood requirement, not the truth of the fact. Continue clarifying if conflicts or remaining uncertainty could change the understanding of the request.

Treat outcome-relevant open decisions and low-confidence understandings as unresolved alignment items. End only when these items are resolved and the user explicitly confirms the overall understanding. The AI's own feeling of confidence is not a substitute for evidence. Do not use a numeric clarity score or a required number of questions.

## Startup Reads

On activation, make these best-effort reads silently. If a source is unavailable or fails, continue without it.

- **Profile.** If `$user-profile-keeper` is available, read only its low-sensitivity `clarification_summary` view. It may shape phrasing, option wording, and examples. It must never decide the audience, scope, acceptance criteria, risk, permissions, or whether a question is needed. Do not infer an audience from demographic, career, education, or other personal fields. Describe roles by function and situation, not as labels for a real person.
- **Task forest.** If `$task-forest` is available, read the current workspace task list and open todos for global context. This context informs recommendations; it does not override the current message.

Use the host's native skill or tool mechanism first. Do not assume a particular agent, skill root, home-directory layout, shell, or operating system. If direct script execution is the only route, discover the companion skill through the host's registry or a repo-local `skills/<skill-name>/` path, build paths with the runtime's path utilities, and never hard-code home, absolute, or drive-letter paths.

Do not read the full profile, pending profile entries, private background, raw evidence, credentials, tokens, or unrelated private information. Do not write to the profile or the task forest. This skill keeps no state between sessions. It writes a file only for a medium whose path the user has accepted.

## Clarification Loop

Each round:

1. **Look up before asking.** Check available information in the current conversation, provided materials, workspace files, or the task forest first; do not ask the user for answers these sources reliably establish. The conversation can establish the user's intent and choices. For objective facts, distinguish "the user reported this" from "this fact was verified"; retain unverified status when verification is unavailable.
2. **Find the unresolved alignment items that most affect the outcome.** Include missing information, undecided choices, priorities, risk tolerances, and acceptance criteria, as well as existing interpretations that lack support, depend on unsupported or contradicted premises, or still have plausible alternatives that would change the outcome. Treat the user's explicit choices, including exact requested text or values, as settled unless a concrete conflict with another stated requirement is identified. An optional alternative wording is not an unresolved alignment item. Raise contradictions and infeasible parts as soon as the evidence establishes them; keep an unsupported premise provisional and ask what would resolve it.
3. **Ask the fewest questions that resolve those items, at most three per round.** Before combining questions, check whether one answer could change another question's premise, options, or recommendation. If it could, ask the prerequisite first and defer the dependent question to a later round. Combine only independent questions.
4. **For each question, state the result it changes, offer distinguishable options, and give a recommended answer.** Always keep a free-form option.

Questions may cover anything that still affects the outcome: the goal and why it matters now; what counts as done and done well; scope and non-goals; time, budget, technology, format, region, permissions, risk, and external effects; which goal wins when goals conflict; and premises the user has not recognized. Ask about audience only under the Audience Impact Test below.

Lay out each question with the reason first, options second, and the recommendation last:

```
**Q1. [One sentence: why this answer changes the outcome]**
[If an existing understanding has low confidence: I currently understand X, based on Y; Z is still uncertain. Please confirm or correct it.]

A) [option]  B) [option]  C) [option]  D) Tell me your own view

→ My recommendation: [short, direct recommended answer]
```

Separate multiple questions in one round with a blank line and `---`. Keep questions simple, accurate, and understandable to someone new to the topic.

If the user says "up to you", "whatever", "your call", "你看着办", "随便", or "你来定", give a recommended option and ask them to confirm it. Do not proceed on your own.

**Zero-question branch.** If lookup leaves no unresolved alignment items that affect the outcome, ask no questions and go straight to the Confirmation Stage. Zero questions never means zero confirmation: the user still explicitly confirms before execution.

## Audience Impact Test

Ask about who uses, reviews, approves, or is affected by the result only if the answer would change at least one of:

- scope or non-goals
- observable acceptance criteria
- security, privacy, compliance, or external effects
- interaction design, accessibility, language, or who reads or approves the output
- implementation, output format, tools, deployment boundary, or level of detail

If no answer would change any of these, do not spend a question on audience. State the audience assumption as an inference in the confirmation summary instead. For internal technical work, identify the operator, reviewer, or maintainer only when that role changes acceptance, permissions, or operations. An internal tool still has an audience.

## Alignment Evidence

Use Markdown by default. Add another medium only when it resolves a specific ambiguity:

| Ambiguity | Medium | How the user checks it |
| --- | --- | --- |
| Format, tone, fields | Concrete positive and negative examples | Names which example matches or fails |
| Multi-step interaction | Scenario walkthrough or step table, including failure and recovery paths | Walks each path and names the step that is wrong |
| Competing rules or stakeholders | Decision or boundary table | Confirms or corrects each row |
| Structure, dependencies, lifecycle | Text flow, state, or dependency diagram (ASCII or Mermaid) | Checks nodes, transitions, and boundaries |
| Layout, density, visual hierarchy | HTML, SVG, image mock, or editable prototype | Checks each state against the acceptance list |

Text media (Markdown, tables, ASCII diagrams, and Mermaid source shown in the reply) need no acceptance gate. Mermaid renders only where the host renders it. If the user cannot see a render, the text version must stand on its own.

Any action that writes a file, opens a viewer, or invokes a host's native image or rendering capability requires the user to accept that specific action and its path or location first. Do not run project code, scripts, tests, or external services to produce or check alignment evidence.

Any non-text medium (image, HTML, SVG, rendered diagram, prototype) also requires all three conditions:

1. The current host can produce it.
2. The host and the user can inspect the result.
3. The user has accepted the action and its location, as described above.

If a condition fails, give an equivalent text version instead.

Every medium must state:

- what it shows;
- what it does not decide (for a mock: final visual design, accessibility, interaction behavior, and technical architecture; for an example: that it is not a full specification unless the user says so);
- how the user can check or correct it.

Label status honestly. A file, image, or diagram you did not open and inspect is `unverified`. Do not describe a rendered or runnable result as checked unless you checked it, and say what you checked.

A medium is evidence for correction, not proof of shared understanding. Keep goals, scope, non-goals, constraints, and acceptance criteria in text even when another medium is used. Do not let a medium add a requirement the text does not state; if it implies one, raise it as a question. Do not present a mock as a design or implementation commitment.

## Confirmation Stage

Enter this stage when lookup or clarification has resolved the outcome-relevant alignment items and a complete, checkable understanding can be summarized. This includes the zero-question case. The user still needs to check the summary; only their explicit confirmation closes the stage. Use the user's language:

```
我的理解如下：
[3-5 行：目标、范围、非目标、受众或角色、关键约束、可观察的验收标准]

我的推断（如有，请逐条确认；没有则写“无”）：
- 我推断 [X]，因为 [用户原话、来源位置或推理依据]；如果错误，会改变 [范围 / 验收 / 风险 / 交互 / 实现] — 如有偏差请直接纠正

[如有对齐材料：逐项标注"已检查"或"未验证"，说明它展示什么、不决定什么、如何纠正]

确认后我会：[下一步动作；如包含高风险动作，注明仍需单独批准]
有没有我遗漏的？
```

If the user corrects a point, update your understanding and check its consequences with the available evidence. Do not re-ask anything the user has explicitly settled unless a new conflict arises. In the reply immediately after a correction, ask at most one clarification question, chosen by the loop's dependency rule, and only if outcome-relevant alignment items remain. Do not ask about the correction itself once it is clear. After the user answers, resume the normal loop. When no outcome-relevant items remain, update the summary and wait for confirmation.

Only an explicit confirmation closes the stage. A medium, an example, or a silent reply does not. After confirmation, this skill ends and execution may begin, subject to High-Risk Actions below.

## High-Risk Actions

Delete, destructively overwrite, migrate, publish, send, deploy, install, use credentials, elevate permissions, write to a remote system, or change global configuration require explicit approval for the concrete action and scope. Before execution, identify the action and target and obtain only missing approval; approval already given for the same action and scope remains valid. Confirming the understanding alone does not grant new approval for these actions. A scoped edit to an existing file is covered by the user's request after this skill's understanding is confirmed; that edit authorization does not extend to deleting files or discarding content beyond the requested edit. Merely writing an existing file does not by itself make the edit a destructive overwrite. Host permissions and tool availability remain binding.

## No Bypass

Once this skill is explicitly invoked, do not substitute safe defaults for questions. Recommended answers help the user choose quickly. They become requirements only after the user confirms them.

## Examples

These examples are illustrative.

### Zero unresolved alignment items

**User:** `$task-clarifier 把 docs/install.md 中唯一一处 Python 3.10 改成 Python 3.11，其余内容不动`

Suppose local lookup confirms a single occurrence of that string and that the project's packaging file already requires Python 3.11. The edit is sufficiently specified, so the skill goes straight to the confirmation summary:

```
我的理解如下：
把 docs/install.md 中唯一一处 Python 3.10 改成 Python 3.11；其余内容不动；与项目打包配置保持一致（本示例假设查阅已确认）。

我的推断：
无。

确认后我会：只替换该处版本号。
有没有我遗漏的？
```

If lookup instead finds multiple matches or another conflict affecting the edit, resolve those alignment items first.

### An existing interpretation with insufficient support

**User:** `$task-clarifier 写一份项目进展说明，要适合领导看`

Suppose the available materials still do not establish the report's purpose. The AI tentatively interprets "适合领导看" as "compress it to one page," but the user's words do not support that length requirement; the purpose also changes which information to retain.

```
Q1. 这份说明的用途会决定应保留哪些信息。
我目前暂按“一页进度概览”理解，来源是“适合领导看”；它只说明读者，不足以确定篇幅或用途。

A) 快速了解进展  B) 决定是否追加资源  C) 说说你的其他用途

→ 我的推荐：A，先以进度概览作为候选；如果本次需要领导决定资源投入，应选 B。
```

After the user chooses, update the understanding and check for remaining uncertainty that affects the outcome. Neither the recommended purpose nor "one page" becomes a confirmed requirement without the user's confirmation.

### Multi-step interaction

**User:** `$task-clarifier 设计一个三步注册流程，邮箱验证码可能失败`

The ambiguity is multi-step, so a text step table that includes the failure branches is the first medium:

| 步骤 | 用户看到什么 | 成功 | 失败时 |
| --- | --- | --- | --- |
| 1 填写邮箱 | 表单 | 进入第 2 步 | 邮箱格式错误：就地提示 |
| 2 输入验证码 | 验证码输入框 | 进入第 3 步 | 验证码错误：允许重发（次数上限待定） |
| 3 设置密码 | 密码表单 | 完成注册 | 密码不符合规则：就地提示 |

Ask the user to walk one failure path and correct any row. Offer a flow diagram only if the host can render it and the user accepts it. Until it is inspected, label it `unverified`.
