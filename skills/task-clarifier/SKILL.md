---
name: task-clarifier
description: 通用任务澄清与需求对齐路由。用于在模糊、高成本、高风险、证据敏感、用户意图敏感、外部副作用、隐私安全、coding/debugging、科研文献、实验 benchmark、论文写作、图表设计、安装发布、自动化、prompt/design/spec 等任务开始前，决定应该直接推进、先读代码/文件/资料、联网搜索、询问用户、确认风险、提供方法选择或阻塞。目标是用最小但足够的问题，把用户真实、具体、完整、可执行、可验证的需求对齐出来，并让用户知道 agent 的理解；不要用于简单、低风险、可逆且上下文已经足够的请求。
---

# Task Clarifier

这是一个需求对齐路由 skill，不是会议模拟器。核心任务是防止 agent 在不该猜的地方猜、在能自证的地方反复问、在高风险地方擅自行动。

一句话：把模糊想法对齐成三方一致的可执行需求：用户想清楚，agent 听准确，用户能确认 agent 没理解偏。

## Global Objective

用最小足够的澄清成本，把用户的真实需求转化为可执行契约，并确保三方一致：

- 目标、受众、交付物、证据边界、范围、非目标和验收标准清楚。
- 用户能完全、准确、清晰、具体、无歧义地理解自己的需求。
- agent 能完全、准确、清晰、具体、无歧义地理解用户的需求。
- 用户知道 agent 如何理解该需求，并能纠正偏差。
- 关键假设被标注，高风险选择被显式确认。
- 能从上下文、代码、文件或可靠来源查到的信息，不要求用户重复提供。
- 对不同用户、背景和任务复杂度，动态调整提问方式；可选读取本地低敏用户画像摘要，但不做心理诊断，不自行写入长期画像。

## Core Rule

不要把每个不确定性都变成用户问题。

只在缺口满足至少一项条件时提问：决策属于用户、答案会改变执行路径、错误代价高、不可逆、证据无法可靠自证，或涉及安全/隐私/外部副作用。能从 repo、文件、官方资料、当前网页、用户已给上下文、本地低敏画像摘要或安全默认值解决的，先自己解决并标注假设。

低打扰不是低对齐。问题可以少，但执行前必须能形成足够清晰的 alignment verdict；重大、不可逆或高影响动作必须由用户确认。

## Activation Gate

使用本 skill 当至少一个条件成立：

- 请求存在多个实质不同的解释。
- 错误假设会导致返工、数据丢失、隐私暴露、错误研究结论或外部副作用。
- 交付格式、成功标准、证据标准、目标受众、范围边界或沟通方式不明确，且会改变工作。
- 任务属于 coding、debugging、仓库修改、实验、文献/事实研究、论文写作、科研图表、设计制品、安全、安装、自动化、发布等精度敏感场景。
- 用户使用了 "更好"、"现代"、"鲁棒"、"best practice"、"dashboard"、"agent"、"paper polish"、"你看着办" 这类可能隐藏真实目标的宽泛词。

不要使用本 skill 当：

- 请求简单、低风险、可逆。
- 缺失信息能从本地文件、已给材料或当前对话安全发现。
- 保守默认值明显，且可边做边说明。
- 用户明确要求不要提问，且任务可以安全推进。

## Workflow

1. 先检查可用上下文：用户消息、附件、repo、文档、日志、报错、约束、已触发 skill；如果安装了 `user-profile-keeper` 且任务需要长期沟通偏好，可尝试读取低敏 `clarification_summary`，失败则忽略。
2. 分类任务：`coding-change`、`debugging`、`research-fact`、`academic-writing`、`experiment-benchmark`、`figure-table-design`、`security-install`、`automation-side-effect`、`product-discovery`、`prompt-design`、`intent-discovery`。
3. 建立 uncertainty ledger：缺什么、是否可发现、谁拥有决策、错了的影响、可逆性、证据需求、安全/隐私/外部风险。
4. 选择动作：
   - `proceed`: 安全默认值或下一步可逆。
   - `research-first`: 本地或外部证据可以解决缺口。
   - `ask`: 答案会改变范围、方法、格式、证据或验收。
   - `confirm`: 高风险、隐私、破坏性、credential、远程、公开发布或外部副作用。
   - `offer-method-choice`: 多种沟通/工作流都合理。
   - `block`: 没有安全默认值，且必须由用户决定。
5. 选择最小有效沟通方式。独立问题可批量；意图不明、用户可能不知道怎么回答、或存在隐藏约束时，一次只问一个问题。
6. 长任务、高风险任务、多轮澄清任务或用户要求完全对齐时，输出 alignment contract 或 alignment verdict，必要时要求显式确认。

读 `references/decision-model.md` 来判断 ask/search/default/confirm/block。读 `references/user-profile-integration.md` 判断是否使用本地画像摘要。

## Adaptive Clarification

提问方式要服务于用户理解，而不是显得完整：

- 专业用户：直接问变量、边界、tradeoff 和验收标准。
- 非专业或语义模糊用户：先用通俗语言解释为什么问，再给 1 个示例答案或推荐默认值。
- 高压力/低耐心场景：优先给推荐选项，允许用户只回答编号。
- 研究/安全/发布/删除/安装/公开材料场景：即使用户想快速推进，也要保留必要确认。

不要在本 skill 中持久化用户画像；若用户明确要求记录或更新画像，路由到 `$user-profile-keeper`。不要推断敏感属性。读 `references/adaptive-communication.md` 获取交互画像和提问梯度。读 `references/person-context-fit.md` 获取不同表达状态下的提问流程。

## Method Router

按不确定性的形状选方法：

- **Direct default**: 任务足够清楚且低风险。说明假设后推进。
- **Research-first**: 缺失事实可从代码、文件、官方文档、论文、primary repo 或当前 web 获取。
- **Batch clarification**: 1-5 个互相独立、用户拥有且容易回答的决策。
- **Method picker**: 多个工作流合理。提供 2-3 个选项、推荐项和取舍。
- **Intent interview**: 真实目标、受众、成功标准或约束不清。提出假设和置信度，一次问一个问题。
- **Spec gate**: 功能、系统、实验、论文、设计或工作流需要稳定执行契约。
- **Risk gate**: 安全、隐私、安装、删除、发布、credential、远程系统或外部副作用。

读 `references/method-router.md` 获取详细路由、handoff 和用户覆盖规则。读 `references/domain-forcing-questions.md` 获取 coding/research/debugging 等场景的高信号问题包。读 `references/anti-profile-bubble.md` 避免历史偏好或当前假设造成局部最优。

## Question Quality

每个问题必须满足：

- **Decision-changing**: 答案改变范围、方法、证据、格式、安全或验收。
- **Grounded**: 基于已检查上下文，或说明为什么这个缺口重要。
- **Specific**: 点名变量，不问泛泛的 "请澄清"。
- **Bounded**: 能用一两句话或选项回答。
- **Non-leading**: 不诱导用户选择不安全或无证据方案。
- **Minimal**: 不问已存在或可低成本发现的信息。

困难问题优先使用结构：问题、为什么问、我当前猜测、示例答案、用户可怎样回答。读 `references/question-bank.md`。当用户话语可能隐藏真实目标、受众或约束时，读 `references/hidden-intent-interview.md`。

## Evidence And Safety

事实可发现时，先查再问。优先级：用户文件/current repo/exact logs > 官方文档/primary repo/论文/标准 > 维护良好的高质量 repo/benchmark > 博客/论坛 > 社交帖/模型输出。

即使已有证据，也必须在这些动作前确认：

- 删除、覆盖、迁移、全局安装或共享配置修改。
- 使用 credential、私有浏览器会话、私有 repo、secret。
- 发送、发布、排程、PR、远程写入或触发外部系统。
- 安全、隐私、法律、财务或研究结论的重大 tradeoff。
- 将低置信证据用于论文、benchmark、公开材料或高影响决策。

读 `references/evidence-policy.md` 获取 source tiers、联网搜索隐私门槛和确认规则。

## Alignment Contract

长任务、高风险任务或多轮澄清后，用 alignment verdict 收尾：

- `aligned`: 可以执行，无重大未决问题。
- `aligned-with-assumptions`: 可以执行，但列出可逆假设。
- `needs-answer`: 需要用户回答后才能安全推进。
- `blocked`: 没有安全默认值，继续执行会造成明显风险或偏离。

读 `references/alignment-contract.md` 获取契约字段、何时要求用户显式确认，以及多选项拆分规则。

## Defaults

用户要求 best effort 或不回答时，仅在安全时使用默认：

- 保留现有文件；重大改写先复制或最小 patch。
- 不做 destructive、external publish、global install、credential access、remote write。
- 研究任务区分事实、推断和不确定性，并引用来源。
- 学术任务不编造结果、引用、baseline 或 novelty claim。
- 代码任务先读本地模式，做最小连贯改动，先窄验证再广验证。
- 设计任务优先信息清晰、证据忠实、目标受众和现有风格。

读 `references/examples.md` 获取行为检查场景。
