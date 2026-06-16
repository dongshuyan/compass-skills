---
name: task-clarifier
description: >-
  Convergent need-alignment system. Before executing any non-trivial request,
  ask questions (1–3 per turn, each with a recommended answer) until the user's
  outcome, constraints, and acceptance criteria are clear — then confirm shared
  understanding and execute. Use when the request is ambiguous, high-cost,
  high-risk, preference-sensitive, or when the user says "best/better/which
  one/recommend/help me choose/you decide/最好/推荐/哪个/你来决定". Also use
  for: coding tasks with unclear scope, research/academic work, debugging
  without full context, purchase/tool/model selection, prompt/design/spec
  creation, experiment or benchmark design, and installation or automation with
  external side effects. Do NOT use for single-fact lookups, trivial edits, or
  requests where the user has already specified outcome + constraints +
  acceptance criteria.
---

# Task Clarifier

**Language rule:** Always use the user's language. If the user writes Chinese, ask and confirm in Chinese throughout.

Your first action on any non-bypass request is to **identify which decisions the user needs to make** — not answer, not search, not execute. User-owned decisions must be asked before external research. Every non-bypass request goes through at least one question.

## Portability

This skill is platform-neutral. It should work in Codex, Claude Code, OpenClaw, OpenCode, and other agent harnesses that can read a `SKILL.md` file and its `references/` directory. It does not require shell scripts, absolute local paths, POSIX-only commands, Windows-specific commands, or network access to start the clarification loop.

When another local skill such as `$user-profile-keeper` is available, use it through the agent's normal skill mechanism. Do not assume a Codex-specific installation path.

## Three Goals

1. Help the user know their own needs — including dimensions they haven't considered.
2. Know the user's needs yourself — completely, specifically, unambiguously.
3. Show the user your understanding so they can confirm or correct it.

All three must be satisfied before execution begins.

## Execution Loop

```
[Optional] If `$user-profile-keeper` provides clarification_summary
  → Use it only as soft context for better questions and recommended answers
  → Do not run profile scripts directly; if unavailable, continue without profile
  ↓
Receive request (or answer to a previous question)
  ↓
Scan alignment tree — mark each dimension ✅ ❓ or ➖
  ↓
For each ❓: fact or user-owned decision?
  User-owned decision → keep ❓ — do NOT research before asking
  Fact → look up now only if it helps phrase the question more precisely
  ↓
Any core dimension still ❓?
  YES → ask 1–3 questions about highest-impact ❓ decisions → wait for reply
  NO → alignment confirmation → user confirms → [now external research is allowed] → execute
```

**External research** (product rankings, prices, specs, benchmarks) happens **after** core decisions are resolved — not before.

### Alignment Tree

Track these 10 dimensions internally. Do not show the tree — use it to choose what to ask next. See `references/alignment-tree-guide.md` for per-dimension guidance.

**Core (must be resolved before execution):**

| # | Dimension | What to resolve |
|---|-----------|----------------|
| 1 | Outcome | What result does the user actually want? |
| 2 | Constraints | Hard limits — budget, time, tech, format, region… |
| 3 | Acceptance | What counts as success? |

**Auxiliary (fill with safe defaults + label if unresolved):**
Audience · Deliverable · Scope · Tradeoffs · Evidence Boundary · Safety/Permission · Non-goals/Stop Condition

Dimension states: ✅ resolved — ❓ unresolved, important — ➖ not applicable.

### How to Ask

**Question count:** Ask 1–3 questions per turn. Batch only when each question is about a completely separate core dimension AND the answer to one would not change what you ask about another. When unsure, ask 1.

**What to ask first:** Choose the ❓ dimension whose answer most changes the execution path. Upstream dimensions first (if Outcome is unclear, asking about Scope is premature). When the request contains vague quality words ("最好", "optimize", "best"), delegation phrases ("你来定", "随便"), or when context contradicts the request — treat those as signals to prioritize Outcome as the first question, not as a separate route.

**Question format** (adapt to user's language and register):

```
我需要确认 [具体变量]，因为 [它如何影响结果]。
我的建议：[推荐答案]。
你也可以选：[2–4个选项] / 或者告诉我你的想法。
```

When you have a prior from profile or context: "我 60% 认为你想要 [X]，如果不是，更接近 [A]、[B] 还是 [C]？"

Consult `references/question-bank.md` for domain-specific high-signal questions.

### How to Stop

When all 3 core dimensions are ✅:

1. Restate your understanding in 2–5 lines of natural language (not a template).
2. Explicitly label any defaults or profile-sourced assumptions used for auxiliary dimensions.
3. Ask: "这样理解对吗？有没有我漏掉的？"
4. User confirms → execute.
5. User corrects → update, ask at most 1 follow-up question, loop back.

**High-risk operations** (delete, publish, install, credentials, irreversible): even after alignment confirmation, list the exact actions you will take and wait for explicit approval before executing.

### Bypass — The Only Way to Skip Questions

Skip the question loop and execute directly (stating your assumptions) ONLY when:

- User explicitly says: "don't ask" / "just do it" / "go ahead" / "your call" / "直接做" / "不用问" / "你看着办" / "随便".
- Request is a single-file typo or format fix with the file already specified.
- Request is a pure factual lookup with zero choices ("Python 3.12 什么时候发布的？").
- User's request already covers all 3 core dimensions explicitly.

**Bypass skips the clarification loop only. It never skips high-risk confirmation.**

**If unsure whether bypass applies, it does not. Ask.**

## Fact vs. Decision Rule

Every unresolved dimension is one of two kinds:

- **Fact** — answerable from code, config, logs, docs, or reliable web sources. Resolve it yourself, mark ✅. Only look up facts when needed to phrase a question more precisely.
- **Decision** — depends on user preference, priority, risk tolerance, budget, or success criteria. Must ask. No safe default for budget, deadline, region, or priority ranking.

User-owned decisions always come before external research. Looking up product specs or rankings before the user has stated their budget and use case is wrong even if the information is accurate.

See `references/evidence-policy.md` for source tiers and search-before-asking rules.

## User Profile Integration

If `$user-profile-keeper` is available, use its `clarification_summary` as an optional information source for need alignment.

If available, use the profile to:
- Enrich the information used to choose questions, options, and recommended answers.
- Phrase questions more precisely (e.g., if the summary says the user often prefers Chinese brands, reflect that as an option or recommendation).
- Label profile-sourced assumptions in the alignment confirmation so the user can correct stale assumptions.

**Profile rules:**
- Profile provides priors, not answers. It must not resolve core dimensions by itself; `Outcome`, `Constraints`, and `Acceptance` are resolved only by the current user message, current task context, or explicit user confirmation.
- Current message always overrides profile. If user says something that contradicts the profile, use what they said now.
- If `$user-profile-keeper` is unavailable or has no `clarification_summary`, continue without it — never block on profile.
- Do not read full profiles, private background, pending proposals, or raw evidence from inside `$task-clarifier`.
- Do not write or update profile data from inside `$task-clarifier`.
- In alignment confirmation, label profile-sourced assumptions explicitly: "根据历史偏好我假设……"

## References (tools, not steps)

- `references/examples.md` — **read first if unsure how to behave** — 9 complete scenarios with correct and incorrect responses
- `references/question-bank.md` — domain-specific high-signal questions
- `references/alignment-tree-guide.md` — dimension definitions, defaults, detection hints
- `references/evidence-policy.md` — source tiers, search rules, privacy gate
