# End-to-End Examples

Complete scenarios showing correct behavior. For each: why this mode triggers, what to ask (or why to bypass), and what NOT to do.

---

## 1. Purchase — "帮我看看哪个行李箱最好，我要买个行李箱"

**Why ask:** "最好" is a vague quality word. Outcome (type/size), Constraints (budget, region), and Acceptance are all unresolved. These are user-owned decisions — web search cannot resolve them.

**❌ Wrong:** Search for "best luggage 2026", recommend Travelpro, then ask "你还有什么问题吗?"
This skips all three core dimensions before asking a single decision question.

**❌ Also wrong:** Ask "你的使用场景是什么?" as Turn 1.
Use case is downstream of type/size. Ask the upstream decision first.

**✅ Correct — question sequence:**

Turn 1 (Outcome — type is the upstream decision, note 1–3 questions allowed when truly independent):
> 我需要确认**箱子类型和预算**，因为这两个是最影响推荐的决定。
>
> **类型**：A) 20寸登机箱（上飞机，免托运） B) 24/26寸托运箱（大容量，长途）C) 一大一小套装 D) 不确定，按推荐来
> 我的建议：A，大多数人用登机箱频率更高。
>
> **预算**：A) 500以内 B) 500–1500 C) 1500–3000 D) 不限
> 我的建议：1500–3000 元选择面最广。

Turn 2 (Constraints — region, if not already in context):
> 你在**哪里购买**？这影响品牌和保修渠道。
> 我的建议：国内购买，选国行渠道保修更方便。
> A) 中国大陆 B) 美国 C) 其他地区

Alignment confirmation:
> 你需要一个 20 寸登机箱，预算 1500–3000 元，在国内购买。
> 我假设：不限品牌、不特别在意重量、主要用于出差。
> 这样理解对吗？有没有我漏掉的？
>
> [确认后再搜索评测、比较品牌。]

---

## 2. Purchase — "帮我推荐个充电宝"

**Why ask:** Same pattern as luggage — "推荐" + no constraints stated. But charging banks have fewer dimensions, so convergence is faster.

**✅ Correct — question sequence:**

Turn 1 (Outcome — use case):
> 主要给**什么设备充电**？这决定了容量和功率要求。
> 我的建议：只给手机充选 10000mAh，给笔记本也充选 20000mAh+。
> A) 手机为主 B) 手机 + 平板 C) 包括笔记本 D) 户外/多设备

Turn 2 (Constraints — budget):
> **预算大概多少**？充电宝 50 到 500 差异很大。
> 我的建议：100–200 元区间性价比最好。
> A) 100 以内 B) 100–200 C) 200–500 D) 不限

Alignment confirmation (2 questions enough — remaining dimensions safe to default):
> 你要一个给手机充电的 10000mAh 充电宝，预算 100–200 元。
> 我假设：国内购买、不需要飞机特殊规格、品牌不限。
> 对吗？

---

## 3. Bypass — Clear bug fix with full context

**Request:** "src/auth.py 第 42 行的 `users` 应该是 `user`，帮我改一下"

**Why bypass:** Single-file typo fix, file specified, line specified, change specified. All 3 core dimensions are explicit (Outcome = fix typo, Constraints = specific file+line, Acceptance = correct spelling). Matches bypass rule 2 and 4.

**✅ Correct:** Fix the typo directly. State: "已将 `src/auth.py` 第 42 行的 `users` 改为 `user`。"

**❌ Wrong:** "请问你确定要改这个吗？这个修改会影响什么功能吗？"

---

## 4. Ask — Vague optimization

**Request:** "帮我优化一下这个系统的性能"

**Why ask:** "优化" and "性能" are vague quality words. No specific system, no metric, no acceptance criteria. All 3 core dimensions unresolved.

**✅ Correct — question sequence:**

Turn 1 (Outcome — what system, what kind of performance):
> 我需要确认你说的**"系统"和"性能"**具体指什么，因为优化 API 响应时间和优化构建速度是完全不同的工作。
> 我 60% 猜测你指的是当前项目的运行时性能。
> A) API/后端响应速度 B) 前端加载/渲染 C) 构建/CI 速度 D) 数据库查询 E) 其他

**❌ Wrong:** Start profiling random code paths without knowing what "performance" means to the user.

---

## 5. Ask — Research topic

**Request:** "我想研究一下大模型的幻觉问题"

**Why ask:** Research is open-ended. Outcome (what deliverable?), Constraints (methodology, scope), and Acceptance (depth, audience) are all unresolved.

**✅ Correct — question sequence:**

Turn 1 (Outcome):
> 你需要的是什么形式的产出？这决定了研究的深度和结构。
> 我的建议：如果是为了写论文，需要系统性文献综述；如果是了解现状，一份简报就够。
> A) 论文/文献综述 B) 研究简报/概述 C) 技术方案（如何减少幻觉）D) 只是探索方向

Turn 2 (Constraints — scope):
> 你关注幻觉问题的**哪个层面**？
> 我的建议：检测方法是当前最活跃的子领域。
> A) 幻觉的成因机制 B) 检测/评估方法 C) 缓解策略 D) 特定领域（医疗/法律/…）的幻觉

---

## 6. High-risk — External publish

**Request:** "帮我把这篇文章发到我的博客上"

**Why ask:** Publishing is irreversible and externally visible. Even if Outcome seems clear, Safety/Permission is critical.

**✅ Correct — question sequence:**

Turn 1 (Safety — confirm intent and scope):
> 发布是不可撤回的公开操作，我需要确认几个点。
> 这是发到**哪个博客**？以及是草稿还是直接公开发布？
> 我的建议：先发草稿预览，确认无误再公开。
> A) 草稿/预览模式 B) 直接公开发布

Even after alignment confirmation, list exact actions:
> 我将要执行：1) 连接 [blog platform] 2) 以 [标题] 创建草稿 3) 等你预览后再公开。确认执行？

---

## 7. Bypass — User says "just do it"

**Request:** "帮我重构一下这个函数，不用问了直接改"

**Why bypass:** User explicitly said "不用问了直接改" — matches bypass rule 1. Even though "重构" could mean many things, user has waived the clarification loop.

**✅ Correct:** Execute with stated assumptions. After completion:
> 已重构完成。我的做法是 [简述]。假设：保持函数签名不变、保持现有测试通过。如果这不是你要的方向，可以撤回。

**❌ Wrong:** Ignore the user's bypass request and ask "你希望重构到什么程度？"

---

## 8. Bypass — Pure factual lookup

**Request:** "Python 3.12 是什么时候发布的？"

**Why bypass:** Pure factual query, zero choices, zero user-owned decisions. Matches bypass rule 3.

**✅ Correct:** Look up and answer directly: "Python 3.12.0 于 2023 年 10 月 2 日发布。"

**❌ Wrong:** "我需要确认你问的是正式版还是 beta 版的发布日期？"

---

## 9. Profile integration — "帮我推荐个充电宝" (with profile)

**Context:** Profile clarification_summary contains: `prefers_chinese_brands: true`, `primary_devices: [iPhone, MacBook]`, `budget_sensitivity: medium`.

**How profile changes the loop:**

Turn 1 (profile enriches options and recommendations, but does not replace Outcome+Constraints questions):
> 根据你的历史偏好，我知道你主要用 iPhone 和 MacBook，偏向国产品牌。
>
> 我需要确认**容量需求和预算**，这两个决定型号选择。
>
> **容量**：A) 10000mAh（仅手机，轻便） B) 20000mAh（手机+MacBook，重一点）
> 我的建议：如果 MacBook 也要充，选 B。
>
> **预算**：A) 100以内 B) 100–200 C) 200+ D) 不限
> 我的建议：100–200 区间国产品牌（Anker/紫米）性价比最好。

Alignment confirmation:
> 你需要一个 20000mAh 充电宝，预算 100–200 元，偏向安克或紫米。
> 根据历史偏好我假设：国内购买、不需要航空特殊规格。
> 对吗？

**Key difference from no-profile scenario:**
- Without profile: Turn 1 asks use case first, Turn 2 asks budget, Turn 3 might ask brand preference → 3 turns.
- With profile: profile narrows the likely device context and brand preference → 1 turn can ask sharper remaining decisions → 1 turn.
- But: profile never silently resolves a decision. The alignment confirmation still shows profile-sourced assumptions explicitly so the user can correct them.
