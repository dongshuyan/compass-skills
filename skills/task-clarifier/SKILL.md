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
2. **The AI understands the user's needs** completely and specifically. No user-owned decision is filled with a default.
3. **The user can verify the AI's understanding.** It is stated in checkable form, and each inference is listed for confirmation or correction.

Judge completion by these goals and the user's explicit confirmation. Do not use a numeric clarity score or a required number of questions.

## Startup Reads

On activation, make these best-effort reads silently. If a source is unavailable or fails, continue without it.

- **Profile.** If `$user-profile-keeper` is available, read only its low-sensitivity `clarification_summary` view. It may shape phrasing, option wording, and examples. It must never decide the audience, scope, acceptance criteria, risk, permissions, or whether a question is needed. Do not infer an audience from demographic, career, education, or other personal fields. Describe roles by function and situation, not as labels for a real person.
- **Task forest.** If `$task-forest` is available, read the current workspace task list and open todos for global context. This context informs recommendations; it does not override the current message.

Use the host's native skill or tool mechanism first. Do not assume a particular agent, skill root, home-directory layout, shell, or operating system. If direct script execution is the only route, discover the companion skill through the host's registry or a repo-local `skills/<skill-name>/` path, build paths with the runtime's path utilities, and never hard-code home, absolute, or drive-letter paths.

Do not read the full profile, pending profile entries, private background, raw evidence, credentials, tokens, or unrelated private information. Do not write to the profile or the task forest. This skill keeps no state between sessions. It writes a file only for a medium whose path the user has accepted.

## Clarification Loop

Each round:

1. **Look up before asking.** Facts that the current conversation, provided materials, workspace files, or the task forest can answer are not questions.
2. **Find the open decisions that most affect the outcome.** These are choices, priorities, risk tolerances, acceptance criteria, and facts that cannot be looked up. Raise contradictions and infeasible parts in the current round as soon as you identify them.
3. **Ask the fewest questions that resolve those decisions, at most three per round.** Ask questions that depend on earlier answers in later rounds. Combine only independent questions.
4. **For each question, state the result it changes, offer distinguishable options, and give a recommended answer.** Always keep a free-form option.

Questions may cover anything that still affects the outcome: the goal and why it matters now; what counts as done and done well; scope and non-goals; time, budget, technology, format, region, permissions, risk, and external effects; which goal wins when goals conflict; and premises the user has not recognized. Ask about audience only under the Audience Impact Test below.

Lay out each question with the reason first, options second, and the recommendation last:

```
**Q1. [One sentence: why this answer changes the outcome]**

A) [option]  B) [option]  C) [option]  D) Tell me your own view

→ My recommendation: [short, direct recommended answer]
```

Separate multiple questions in one round with a blank line and `---`. Keep questions simple, accurate, and understandable to someone new to the topic.

If the user says "up to you", "whatever", "your call", "你看着办", "随便", or "你来定", give a recommended option and ask them to confirm it. Do not proceed on your own.

**Zero-question branch.** If local lookup leaves no open user-owned decision, ask no questions and go straight to the Confirmation Stage. Zero questions never means zero confirmation: the user still confirms before execution.

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

Enter this stage when all three goals are met, including the zero-question case. Use the user's language:

```
我的理解如下：
[3-5 行：目标、范围、非目标、受众或角色、关键约束、可观察的验收标准]

我的推断（请逐条确认）：
- 我推断 [X]，因为 [依据]；如果错误，会改变 [范围 / 验收 / 风险 / 交互 / 实现] — 如有偏差请直接纠正

[如有对齐材料：逐项标注"已检查"或"未验证"，说明它展示什么、不决定什么、如何纠正]

确认后我会：[下一步动作；如包含高风险动作，注明仍需单独批准]
有没有我遗漏的？
```

If the user corrects an inference, update the understanding, ask at most one follow-up question about that point, and repeat this summary. Only an explicit confirmation closes the stage. A medium, an example, or a silent reply does not. After confirmation, this skill ends and execution may begin, subject to High-Risk Actions below.

## High-Risk Actions

Delete, overwrite, migrate, publish, send, deploy, install, use credentials, elevate permissions, write to a remote system, or change global configuration require listing the exact actions and waiting for explicit approval before execution. This approval is separate from confirming the understanding. Confirming the understanding does not approve these actions.

## No Bypass

Once this skill is explicitly invoked, do not substitute safe defaults for questions. Recommended answers help the user choose quickly. They become requirements only after the user confirms them.

## Examples

These examples are illustrative.

### Zero open decisions

**User:** `$task-clarifier 把 docs/install.md 里的 Python 版本要求改成 3.11，只改这个文件`

Suppose local lookup shows the project's packaging file already requires Python 3.11, and the user named both the file and the target. No user decision is open, so the skill goes straight to the confirmation summary:

```
我的理解如下：
把 docs/install.md 中的 Python 版本要求改为 3.11；只修改这一个文件；与项目打包配置保持一致。

我的推断（请逐条确认）：
- 我推断其他文档不需要同步修改，因为你只指定了这一个文件 — 如果需要同步，会改变范围
- 我推断只改版本号，不调整安装步骤，因为你没有提到其他变化 — 如果错误，会改变实现

确认后我会：只修改 docs/install.md 中的版本要求。
有没有我遗漏的？
```

### Multi-step interaction

**User:** `$task-clarifier 设计一个三步注册流程，邮箱验证码可能失败`

The ambiguity is multi-step, so a text step table that includes the failure branches is the first medium:

| 步骤 | 用户看到什么 | 成功 | 失败时 |
| --- | --- | --- | --- |
| 1 填写邮箱 | 表单 | 进入第 2 步 | 邮箱格式错误：就地提示 |
| 2 输入验证码 | 验证码输入框 | 进入第 3 步 | 验证码错误：允许重发（次数上限待定） |
| 3 设置密码 | 密码表单 | 完成注册 | 密码不符合规则：就地提示 |

Ask the user to walk one failure path and correct any row. Offer a flow diagram only if the host can render it and the user accepts it. Until it is inspected, label it `unverified`.
