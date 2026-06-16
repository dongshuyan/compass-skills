# Question Bank

High-signal questions by domain. Each entry: **variable** — why it matters — recommended default.

Use these to pick the right question for an unresolved dimension. Do not ask all of them — pick the one that most changes the execution path.

---

## 1. Universal

**Outcome** — Determines everything downstream. — Default: ask; no safe assumption.
> What end result do you need? (e.g., a working fix / a recommendation list / a written report / a deployed change)

**Acceptance criteria** — Without this you cannot verify success. — Default: "works correctly and doesn't break existing behavior."
> How will you judge whether this is done well? (e.g., tests pass / looks right visually / approved by reviewer / fits in N pages)

**Deliverable format** — Affects scope and effort. — Default: same format as the existing artifact.
> What form should the result take? (e.g., code PR / document / verbal answer / prototype / production-ready)

**Hard constraints** — Prevents wasted work on infeasible paths. — Default: infer tech/format constraints from context; **ask about budget, deadline, region** (user-owned, no safe default).
> Are there hard limits I should know about? (budget, deadline, word count, framework, compatibility…)

**Evidence boundary** — Determines research depth. — Default: "use reliable sources; flag uncertainty."
> How certain does the information need to be? (verified primary sources only / reputable secondary OK / rough estimate fine)

**What did I miss?** — Catches blind spots. — No default.
> Is there anything else that would change what "good" looks like?

---

## 2. Coding

**Acceptance scope** — Minimum patch vs. refactor vs. performance overhaul produce very different PRs. — Default: minimum coherent change that passes tests.
> Should this be the smallest fix, a clean refactor, or a deeper improvement?

**Immutable boundaries** — Breaking public API / CLI / file format is usually not acceptable. — Default: preserve all public interfaces.
> Are there interfaces, contracts, or formats I must not change?

**Test scope** — Determines verification effort. — Default: run existing tests; add a test for the changed behavior.
> What testing do you expect — existing tests pass, new tests added, or manual verification?

**Rollback strategy** — Affects how cautious the change should be. — Default: changes should be easily revertible.
> If this goes wrong, how do we undo it? (git revert / feature flag / manual rollback)

---

## 3. Debugging

**Reproduction** — Cannot debug what you cannot reproduce. — Default: ask.
> Can you describe the steps to reproduce, or share the error output?

**Environment** — Same code behaves differently across environments. — Default: check from context (package.json, Dockerfile, CI config).
> What environment are you seeing this in? (OS, runtime version, local/CI/production)

**Recent changes** — Most bugs come from recent changes. — Default: check git log.
> Did anything change recently before this started happening? (deploy, dependency update, config change)

**Urgency** — Determines depth vs. speed tradeoff. — Default: thorough fix.
> Is this blocking something right now, or can we take time to fix it properly?

---

## 4. Recommendation / Selection

**Primary use case** — "Best" is meaningless without context. — Default: ask.

Anti-pattern — ❌ "What does 'best' mean to you?"
✅ Instead, offer concrete scenarios:
> Which scenario fits you best?
> A) Everyday portable use — light, compact
> B) Heavy-duty / professional — durability and capacity first
> C) Travel-specific — airline/regulation compliant
> D) Best value — good enough at lowest cost
> My recommendation: [A/B/C/D based on any context clues].

**Hard constraints** — Budget, region, compatibility narrow the field fast. — Default: **none — always ask.** Budget and region are user-owned decisions with no safe assumption.
> Are there hard constraints? (max budget, must ship to [region], must work with [existing thing])

**Ranking criteria** — What to optimize for when tradeoffs arise. — Default: reliability > usability > price.
> When two options are close, what matters more to you? (price / durability / features / brand / aesthetics)

**Output format** — A ranked list vs. a single pick vs. a comparison table. — Default: single top pick + 2 alternatives with tradeoffs.
> Do you want one recommendation, a shortlist, or a detailed comparison?

**Evidence standard** — Professional review vs. crowd opinion vs. your own testing. — Default: cite professional reviews and specs; flag anecdotal sources.
> Should I stick to verified specs and professional reviews, or include community opinions too?

---

## 5. Research / Academic

**Research question clarity** — Vague question = unfocused output. — Default: ask for refinement.
> Can you state the specific question you want answered — who/what/where/when/why/how?

**Methodology constraints** — Qualitative, quantitative, mixed, systematic review, etc. — Default: whatever fits the question best.
> Do you have a required methodology, or should I choose based on the question?

**Literature scope** — Time range, disciplines, languages. — Default: last 10 years, English, core discipline + adjacent fields.
> How far back should I search, and should I include adjacent fields?

**Audience level** — Expert peers vs. general readers vs. funding body. — Default: expert peers in the same field.
> Who is the primary reader — peers, students, reviewers, or a general audience?

---

## 6. Design / Architecture

**Scale requirements** — Orders-of-magnitude differences in scale change everything. — Default: ask.
> What scale do you expect? (users, requests/sec, data volume, team size)

**Tradeoffs** — Consistency vs. availability, speed vs. correctness, simplicity vs. flexibility. — Default: start simple, make it easy to change later.
> When forced to choose, which matters more — [X] or [Y]?

**Migration constraints** — Greenfield vs. brownfield changes scope dramatically. — Default: assume existing system unless stated.
> Is this greenfield, or does it need to integrate with / replace something existing?

**Team familiarity** — Choosing tools the team doesn't know adds hidden cost. — Default: prefer tools already in the stack.
> Are there technologies the team already knows well, or is anything off-limits?

---

## 7. Security / Installation

**Scope of access** — Determines what is being trusted. — Default: minimal necessary access.
> What level of access does this need? (read-only / read-write / admin / root)

**Reversibility** — Installation and permission changes can be hard to undo. — Default: prefer reversible approaches.
> If something goes wrong, can this be cleanly uninstalled or reverted?

**Credential handling** — Determines security posture. — Default: never store in code; use env vars or secret manager.
> How should credentials be stored and passed? (env vars / secret manager / config file)

**Environment isolation** — Production vs. staging vs. local sandbox. — Default: ask; never assume production.
> Where will this run — local dev, staging, or production?

---

## 8. Automation / External Effects

**Trigger conditions** — When should this run? — Default: manual trigger; escalate to automatic only if user confirms.
> Should this run automatically (on schedule / on event) or only when you trigger it?

**Failure handling** — What happens when it goes wrong. — Default: stop and notify; do not retry automatically.
> If this fails, should it retry, skip, or stop and alert you?

**Notification preferences** — Over-notification is as bad as under-notification. — Default: notify on failure only.
> When should you be notified? (every run / only failures / never)

**Rollback strategy** — Automation mistakes compound fast. — Default: keep last-known-good state; require manual approval to proceed after failure.
> If the automation produces a bad result, how do we undo it?
