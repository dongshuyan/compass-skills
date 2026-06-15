---
name: user-profile-keeper
description: 本地用户画像维护 skill。用于用户明确调用本 skill，要求创建、初始化、更新、查询、纠错、删除、导出或审计自己的本地持久化用户画像；也用于从当前 session 上下文中提取沟通偏好、需求表达习惯、能力边界、常见遗漏、风险偏好和典型事件，并以可审计、可确认、可撤回的方式写入本地画像。不要自动调用；不要上传画像；不要替代 task-clarifier 的正常澄清流程。
---

# User Profile Keeper

维护一个只保存在本机的用户画像。默认只有一个用户 `default`；只有用户明确说明“不是默认用户，是 XXX”时，才创建或切换到新的用户。

## Core Contract

- 只在用户显式调用 `$user-profile-keeper` 或明确要求维护画像时使用。
- 画像默认写入本机用户目录下的 `.compass-skills/user-profiles/v1`；可用 `COMPASS_USER_PROFILE_HOME` 指定其他本地目录。不联网、不上传、不读取浏览器 cookie、token 或 credential。
- 每条画像都必须有来源类型、置信度、敏感级别、状态和证据事件；不要写入无法追溯的结论。
- 低敏、显式、无冲突信息可以自动应用；推断性、敏感、高影响、冲突信息进入 pending proposal。
- 画像范围可以覆盖沟通偏好、需求表达习惯、能力边界、风险确认、隐私边界、反茧房规则、典型事件，以及用户主动提供的年龄段、教育、专业、职业/角色、经验阶段和长期目标等背景信息。
- 背景信息默认按 `private` 处理，除非用户明确要求降为低敏摘要；不得自动暴露给其他 skill。
- 用户可以随时查看、纠错、撤回、删除、导出画像。
- 完整画像只在本 skill 中读取。其他 skill 只能读取 `clarification_summary` 这类低敏摘要。
- 首次初始化必须先做上下文充分性判断；不要把本次任务指令、AGENTS 约束或本 skill 的操作规则误当成完整用户画像。
- 如果用户明确要求启动初始化问卷，必须启动 `scripts/onboarding_webui.py --user <id>`，不能用“当前上下文足够”替代问卷。

## Context Adequacy Gate

画像证据分三类：

- `durable_profile_evidence`: 用户明确表达的长期或默认协作偏好、风险边界、隐私边界、能力边界、常见遗漏或反茧房规则。
- `operational_instruction`: 当前任务、当前仓库、AGENTS、skill 执行步骤、隐私安全规则、工具使用约束等操作性指令。它们应优先约束当前任务，但默认不证明长期画像。
- `agent_observation`: agent 对当前 session 的行为观察。除非反复、直接、低歧义，并且只影响协作流程，否则默认 pending。

首次构建画像时，只有满足以下任一条件，才可说“当前上下文足够初始化而不启动问卷”：

- 用户明确说不需要问卷，且当前 session 已提供覆盖至少 4 个问卷模块的 `durable_profile_evidence`。
- 本地已有 active profile，当前任务只是增量更新，不是首次画像初始化。

以下情况必须视为上下文不足，并启动或建议启动问卷：

- 用户明确要求 WebUI、问卷、初始化问卷或首次构建画像。
- 当前证据主要来自 AGENTS、系统/开发者指令、skill 操作规则或“请如何执行本任务”的约束。
- 只能提取出语言、格式、隐私规则等少数 task-local 偏好，无法覆盖基本协作、沟通澄清、风险确认、隐私边界、能力边界和反茧房等核心模块。

如果跳过问卷，输出必须列明：

- 采用了哪些 `durable_profile_evidence`。
- 覆盖了哪些问卷模块。
- 为什么没有启动问卷。
- 哪些内容只是当前任务约束，未写入长期 active profile。

## Session Inference Policy

从 session 更新画像时，可以基于逻辑推理生成候选画像细节，但必须区分事实、自述、观察和假设：

- 用户直接自述的背景、偏好和边界按 `self_report` 处理；年龄段、教育、专业、职业、长期目标等默认 `private`，先进入 proposal。
- agent 推断的所在地、年龄、专业背景、职业身份、能力层级、性格或价值观等，必须使用 `source_type=inferred`，默认进入 pending proposal。
- 推断候选的 `value` 必须包含 `summary`、`basis`、`reasoning`、`counter_evidence`、`usefulness` 和 `review_question`；证据不足时不要生成。
- 单一弱信号推断置信度不得高于 `0.4`；多个一致信号通常不得高于 `0.6`；只有用户确认后才可升高置信度并进入 active。
- 不得仅凭语言、时区、设备路径、文件名、IP、模型猜测或一次性任务内容推断真实所在地、民族、政治、宗教、健康、财务、法律风险或亲密经历。
- 推断的目的只能是改善协作和追问，不得用于诊断、定型、评价人格或限制用户选择。

## Workflow

1. 识别用户：默认 `default`；用户明确指定新身份时用 `scripts/profile_store.py init --user <id>`。
2. 读取当前状态：`scripts/profile_store.py read --user <id> --view clarification_summary`。
3. 对首次初始化或空画像运行 Context Adequacy Gate；如果用户要求问卷或上下文不足，启动本地 WebUI 初始化问卷。
4. 从当前 session 提取候选更新：提取与协作、需求对齐、沟通、能力边界、风险确认、隐私边界、背景上下文和长期帮助方向有关的信息，并区分长期画像证据和当前操作指令。
5. 分类候选更新：
   - 显式自述、低敏、无冲突：可用 `update-from-session --auto-apply-safe`。
   - 用户自述但属于 `private` 的背景信息：生成 proposal，等待用户确认后进入 active。
   - 推断、敏感、亲密经历、冲突、高影响：只生成 proposal，等待用户确认。
   - 仅由当前任务/skill 操作指令支持的内容：默认不作为长期 active profile；如有必要，生成 pending proposal 或只在本次任务中使用。
6. 写入或生成 proposal 后，输出本次新增、更新、跳过、待确认和隐私处理结果。
7. 若用户要求初始化问卷，运行 `scripts/onboarding_webui.py --user <id>`，提交结果仍先进入 proposal。

读 `references/update-policy.md` 判断自动应用、pending、冲突和勘误规则。读 `references/privacy-boundary.md` 判断敏感信息和安全边界。

## Storage And Tools

主存储由 `scripts/profile_store.py` 管理：

- `init`: 创建 registry、用户目录和 SQLite 数据库。
- `read`: 读取 `clarification_summary`、`full` 或 `pending` 视图。
- `read --view profile_overview`: 读取 low/private active 概览，省略更敏感内容和证据原文。
- `update-from-session`: 用 agent 提取的候选 JSON 更新画像或生成 proposal。
- `proposal-list` / `proposal-apply` / `proposal-reject`: 审核和应用候选更新。
- `assertion-add` / `correct` / `delete` / `search` / `export`: 手动增删改查。
- `validate`: 检查 schema、权限、WAL、孤儿证据和 pending 冲突。

读 `references/profile-schema.md` 获取数据结构和 JSON 输入格式。需要问卷时读 `references/questionnaire.md`。

## Read Views

- `clarification_summary`: 只包含低敏、活跃、与需求对齐相关的摘要，供 `task-clarifier` 这类 skill 可选读取。
- `profile_overview`: 本 skill 内部使用的 low/private 活跃概览，适合用户日常查看；不含 sensitive、intimate、secret，也不含证据原文。
- `full`: 完整画像，仅在用户明确调用本 skill 并需要查看/维护时读取。
- `pending`: 待确认 proposal，不作为稳定画像使用。

读 `references/task-clarifier-integration.md` 获取与 `$task-clarifier` 的边界。读 `references/examples.md` 获取典型调用样例。

## Safety Defaults

- 不保存 secret、token、密码、私钥、验证码或可直接滥用的 credential。
- 不把敏感经历、创伤、羞耻主题、健康、宗教、政治、财务、身份等推断静默写为 active。
- 不因为长期画像覆盖当前对话中的明确新信息；用户当前说法优先。
- 不把画像当诊断、道德判断或人格定型。画像只是协作偏好和需求对齐辅助证据。
