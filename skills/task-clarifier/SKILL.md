---
name: task-clarifier
description: >-
  Deep need-clarification skill. Activates only on explicit invocation: direct
  reference to $task-clarifier, or trigger phrases "帮我理清需求" / "需求澄清" /
  "clarify" / "clarify my needs" / "help me clarify". Once activated, keeps
  asking until all three goals are met: the user fully understands their own
  needs, the AI fully understands the user's needs, and the user confirms the
  AI's understanding is correct. Does not auto-activate; does not intervene in
  task execution unless explicitly invoked.
---

# Task Clarifier

## Language Rule

**All output directed at the user — questions, options, recommendations, confirmations, summaries — must be written in the user's language.** Detect the user's language from their message. Default to Chinese when unknown. If the user writes Chinese, every word of output must be Chinese. Do not use English in any user-facing output unless the user writes in English.

## Three Goals (all must be met before ending)

1. **Help the user fully understand their own needs** — including dimensions the user has not yet considered, latent contradictions, and implicit assumptions that materially affect the outcome
2. **Help the AI fully understand the user's needs** — completely, specifically, unambiguously; no unconfirmed dimension is filled with a default value
3. **Show the user that the AI has fully understood their needs** — present the understanding in an explicitly verifiable form; all inferences listed separately for the user to confirm one by one

## Startup Reads

On activation, silently attempt the following best-effort reads. If any source is unavailable, unsupported, or fails, continue without it — do not block the clarification loop.

Use the current agent or harness's native skill mechanism first. This skill must work in Codex, Claude Code, OpenClaw, OpenCode, and other agents that can read a `SKILL.md` file. Do not assume a specific agent name, skill root, home directory layout, shell, or operating system.

**User profile summary** — If `$user-profile-keeper` is available, read its `clarification_summary` view (low-sensitivity, need-alignment-related preference data only). Prefer the agent's built-in skill invocation, MCP/tool bridge, or documented companion-skill API.

**Task forest** — If `$task-forest` is available, read the current workspace task list and open todos. Prefer the agent's built-in skill invocation, MCP/tool bridge, or documented companion-skill API.

If direct script execution is the only available integration path, first discover the companion skill directory through the current harness's skill registry or by resolving the repo-local `skills/<skill-name>/` directory from this `SKILL.md` location. Construct file paths by joining path segments with the host language or runtime path utilities so the same logic works on macOS, Linux, and Windows. Use the operating system's available Python launcher (`python3`, `python`, or `py -3`) only after discovery succeeds. Never hard-code paths such as `~/.codex/...`, `~/.agents/...`, absolute POSIX paths, or Windows drive paths.

The profile summary enriches the phrasing of question options and recommendations to better match the user's communication style and domain background.  
The task forest provides context for the global purpose and evolution of the current request, so recommendations align with the real overall goal.  
The current user message overrides all profile information. Neither source replaces asking about any dimension.  
Do not read the full profile, pending profile, private background, raw evidence, credentials, cookies, tokens, keys, or unrelated private information. Do not write to the profile or task forest.

## Clarification Loop

Each round executes the same action:

From the current conversation and readable context, extract the part that most affects the current outcome. Break it into as few questions as possible — covering what is needed for complete and accurate understanding, as few as possible, at most 3 — and provide a recommended answer and options for each question.

Questions cover whichever of the following still affects the outcome:

- What the user ultimately wants to achieve
- Why now, and which global purpose this serves
- What counts as done and done well
- What is in scope and what is not
- Time, budget, technology, format, region, permissions, risks, and external effects
- Which goal wins when multiple goals conflict
- Who uses, reviews, or is affected by the result
- Implicit premises the user has not yet recognized that would change the outcome
- Contradictions, conflicts between goals and constraints, and parts that are infeasible in practice or technically — highest priority, include in the current round as soon as identified

When a fact can be obtained from local evidence, look it up before asking. User decisions must be confirmed by the user; never substitute a default value for a question.

When the user says "up to you / whatever / your call / 你看着办 / 随便 / 你来定", provide a recommended option and ask the user to confirm — do not proceed to execution automatically.

When all three goals are met, enter the confirmation stage. Otherwise keep asking.

High-risk actions — including delete, overwrite, migrate, publish, send, deploy, install, use credentials, elevate permissions, write to remote systems, or change global configuration — require listing the exact actions and waiting for explicit approval before execution, even after the confirmation summary is accepted.

## Question Format

Generate questions and recommended answers that are simple, clear, accurate, complete, and understandable to anyone. Output in the user's language (default Chinese).

Each question follows this layout — reason first, options second, recommendation last:

```
**Q1. [一句话：这个问题为什么影响结果]**

A) [选项]　B) [选项]　C) [选项]　D) 告诉我你的想法

→ 我的建议：[推荐答案，简洁直接]
```

When asking multiple questions in one turn, separate each with a blank line and `---`:

```
**Q1. [原因]**

A) …　B) …　C) …　D) 告诉我你的想法

→ 我的建议：…

---

**Q2. [原因]**

A) …　B) …　C) …　D) 告诉我你的想法

→ 我的建议：…
```

Draw on the communication preferences and domain familiarity in the profile summary (if read), and the global goal context in the task forest (if read), to make options and recommendations more relevant to this user and this task.

## Confirmation Stage

Once all three goals are met, output in the user's language (default Chinese):

```
我的理解如下：
[用自然语言陈述用户的完整需求，3-5 行，具体、准确、不遗漏关键约束]

我的推断（请逐条确认）：
- 我推断 [X]，因为 [具体原因] — 如有偏差请直接纠正
- 我推断 [Y]，因为 [具体原因] — 如有偏差请直接纠正

确认后我会：[下一步动作]
有没有我遗漏的？
```

If the user corrects any inference → update the understanding, ask at most 1 follow-up question on the corrected point, and output the confirmation summary again.  
If the user confirms everything is correct → this skill ends; execution can begin.

## No Bypass After Activation

Once this skill is explicitly invoked, no bypass is used, and no safe defaults substitute for asking. Recommended answers help the user choose quickly; they are not automatically written into the requirements.

## Examples

### Example 1: Unformed needs + contradiction detection

**User:** `$task-clarifier 帮我写个爬虫，要快，把100万条历史数据全抓完`

**Round 1 (identify contradiction + highest-impact decision):**

**Q1. "快"和"100万条全部抓完"之间存在冲突：完整抓取百万级数据通常耗时较长，且可能触发速率限制或封禁。你更看重哪个？这决定了整体技术策略。**

A) 完整性优先（接受耗时，分批完成）　B) 速度优先（接受部分数据缺失）　C) 有具体 deadline（请告诉我时间）　D) 告诉我你的想法

→ 我的建议：完整性优先，用分批 + 限速策略保证全量，避免封禁。

**User:** `完整性优先，3天内跑完`

**Round 2 (acceptance criteria):**

**Q1. 你如何判断"抓完了"？这决定了数据完整性的验收方式和补抓策略。**

A) 条数达到100万即可　B) 需要与某个基准数据对比验证　C) 告诉我你的想法

→ 我的建议：以实际抓取条数为主标准，同时记录失败条目以便补抓。

**[All three goals met → enter confirmation stage]**

---

### Example 2: Profile-assisted phrasing

**Context:** Profile summary shows the user prefers Chinese, structured expression, and evidence-first reasoning.

**User:** `$task-clarifier 帮我研究这个工具值不值得用`

**Round 1 (evaluation criteria + output form):**

**Q1. "值不值得用"需要先确定判断标准；成本、稳定性、安全性、迁移成本会导向不同结论。这决定了评估的维度和深度。**

A) 快速判断能不能用　B) 深度评估长期采用成本　C) 和替代方案对比　D) 告诉我你的想法

→ 我的建议：按"是否解决当前问题、迁移成本、可验证风险"三项评估，优先使用官方文档和本地证据，输出结构化对比。

---

### Example 3: Task forest global context

**Context:** Task forest shows global task is "Python 2→3 full migration"; current subtask is "auth module migration".

**User:** `$task-clarifier 帮我把 auth.py 的 print 语句改成 print 函数`

**Round 1 (scope + global goal context):**

**Q1. 这个修改属于 Python 2→3 迁移任务的一部分。auth.py 中还可能存在其他兼容性问题（unicode 字符串、整数除法、异常语法等）。这次范围如何定？这决定是否需要反复修改同一个文件。**

A) 只改 print 语句　B) 一并处理 auth.py 所有 Python 2→3 差异　C) 告诉我你的想法

→ 我的建议：选 B，一并处理，加快整体迁移进度。

---

### Example 4: Confirmation summary format

```
我的理解如下：
你需要用 Python 编写一个爬虫，抓取目标网站的100万条历史数据。
完整性优先，接受分批 + 限速策略，3天内完成。
验收标准：实际抓取条数达到100万条，记录失败条目以便补抓。

我的推断（请逐条确认）：
- 我推断目标网站公开可访问（无需登录），因为你未提及账号或认证信息 — 如有偏差请直接纠正
- 我推断数据存储在本地数据库，因为百万级数据量通常不适合纯文件存储 — 如有偏差请直接纠正
- 我推断这是一次性历史全量抓取，不需要实时增量更新 — 如有偏差请直接纠正

确认后我会：生成爬虫代码框架（含分批 + 限速逻辑、失败条目记录）。
有没有我遗漏的？
```
