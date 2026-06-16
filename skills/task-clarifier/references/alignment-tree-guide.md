# Alignment Tree Guide

10 dimensions for tracking shared understanding. Use this to decide what to ask next.

For each dimension: what it means, when it's critical, how to detect it from context, example questions, and safe defaults.

---

## Core Dimensions (must resolve before execution)

### 1. Outcome

**What it means:** The end state the user wants to reach. Not the task ("fix the bug") but the result ("login works again for OAuth users").

**When critical:** Always. No execution without a clear outcome.

**Detect from context:** User states a desired end state explicitly. Check if the request implies a clear result ("deploy to production" → outcome is running in production) or is ambiguous ("make it better" → unclear).

**Example questions:**
- What end result do you need from this?
- When this is done, what should be true that isn't true now?

**Safe default:** None. Always resolve, even if it means rephrasing what the user said back to them for confirmation.

---

### 2. Constraints

**What it means:** Hard limits that eliminate options. Budget, deadline, technology restrictions, compatibility requirements, regulatory rules, format mandates.

**When critical:** Always for non-trivial tasks. A solution that violates a constraint is worse than no solution.

**Constraints come in two kinds — treat them differently:**

| Kind | Examples | How to resolve |
|------|----------|---------------|
| **Fact-inferrable** | Tech stack, framework version, existing interfaces, file formats | Detect from code/config/docs → mark ✅ |
| **User-owned decision** | Budget, deadline, region, priority ranking, risk tolerance | Must ask the user — no safe default exists |

**Detect fact-inferrable constraints from context:**
- Project files (package.json, requirements.txt → technology constraints)
- Existing codebase patterns (already using React → likely a React constraint)
- Task type implies some constraints (academic paper → citation format)

**User-owned constraints — always ask if not stated:**
- Budget / price range
- Deadline / timeline
- Geographic region / market
- Priority ranking when goals conflict
- User's prior messages may already contain these ("we're on AWS", "budget is $500") — if so, mark ✅

**Example questions:**
- Are there hard limits I should know — budget, deadline, tech stack, format?
- Is there anything that would make an otherwise good solution unacceptable?

**Safe default:** For fact-inferrable constraints: use existing tech stack, preserve existing interfaces. For user-owned constraints (budget, deadline, region, priority): **none — ask.** Do not assume "no budget limit" or "no deadline."

---

### 3. Acceptance

**What it means:** How the user will judge success. The criteria that separate "done" from "not done" and "good" from "bad."

**When critical:** Always. Without acceptance criteria, you cannot self-verify before delivering, and the user cannot evaluate your output.

**Detect from context:**
- Explicit criteria ("tests must pass", "fits in 8 pages")
- Implied by task type (bug fix → bug no longer reproduces; recommendation → user can make a decision)
- Prior feedback in conversation ("last time it was too verbose")

**Example questions:**
- How will you judge whether this is done well?
- What would make the result feel like a miss, even if technically correct?

**Safe default:** "Works correctly, doesn't break existing behavior, and matches the style/quality of surrounding work."

---

## Auxiliary Dimensions (can use safe defaults + label)

### 4. Audience

**What it means:** Who will see, use, or be affected by the result.

**When critical:** Writing tasks, presentations, API design, documentation, recommendations. Less critical for internal bug fixes.

**Detect from context:** Document metadata, repo README (public vs. internal), stated recipients, paper venue/conference.

**Example question:** Who is the primary reader or user of this?

**Safe default:** "Same audience as the surrounding context (codebase contributors, paper reviewers, etc.)." Label this assumption.

---

### 5. Deliverable

**What it means:** The form factor of the output — code PR, document, verbal answer, prototype, deployed system, comparison table.

**When critical:** When the task could reasonably produce different forms (e.g., "optimize performance" could mean a report, a PR, or a benchmark).

**Detect from context:** User says "write a…", "build a…", "give me a…" — the object usually implies form. File types in the project hint at expected output.

**Example question:** What form should the result take — code, document, verbal answer, something else?

**Safe default:** Same form as the input or the existing artifact. Label this assumption.

---

### 6. Scope

**What it means:** Boundaries of what to include and exclude. How deep, how broad, where to stop.

**When critical:** Open-ended tasks ("improve the codebase"), research, refactoring, migration.

**Detect from context:** User specifies files, functions, sections. Task type implies scope (bug fix = narrow; refactor = ask).

**Example question:** How far should this go — just [specific area], or the whole [broader area]?

**Safe default:** Minimum scope that achieves the outcome. Label: "I'll keep this to [X] unless you want broader."

---

### 7. Tradeoffs

**What it means:** When goals conflict, which one wins. Speed vs. quality, cost vs. features, simplicity vs. completeness.

**When critical:** Design decisions, architecture, purchasing, any task with competing objectives.

**Detect from context:** User emphasizes one quality ("fast", "cheap", "thorough"), or the problem inherently has tensions.

**Example question:** When [X] and [Y] conflict, which matters more to you?

**Safe default:** Quality > speed, correctness > completeness, simplicity > features. Label the tradeoff you chose.

---

### 8. Evidence Boundary

**What it means:** How reliable the information needs to be. Verified facts only, professional reviews OK, anecdotal fine, rough estimates acceptable.

**When critical:** Research, recommendations, fact-sensitive tasks, anything that will be published or shared.

**Detect from context:** Academic context = high evidence bar. Casual chat = lower bar. Medical/legal/financial = highest bar.

**Example question:** How certain does the information need to be — verified sources only, or rough estimates fine?

**Safe default:** "Use reliable sources; flag anything uncertain." Label this.

---

### 9. Safety / Permission

**What it means:** Irreversible actions, external side effects, credential use, data exposure, publication, deletion.

**When critical:** Any action that is hard to undo or affects external systems/people.

**Detect from context:** Task involves delete, publish, send, install, deploy, share, or credential. Check if staging vs. production is specified.

**Example question:** This involves [irreversible action]. Confirm you want to proceed, and in which environment?

**Safe default:** Do not proceed with irreversible or externally-visible actions without explicit confirmation. No default can substitute for user approval here.

---

### 10. Non-goals / Stop Condition

**What it means:** What is explicitly out of scope, and when to consider the task done.

**When critical:** Open-ended tasks, iterative work, tasks that could expand indefinitely (research, optimization, refactoring).

**Detect from context:** User says "don't worry about…", "just the…", "stop at…". Prior conversation may reveal past scope creep.

**Example question:** Is there anything I should explicitly NOT do, or a point where I should stop and check in?

**Safe default:** "Stop when the outcome is achieved and acceptance criteria are met. Don't expand scope beyond what was asked." Label this.
