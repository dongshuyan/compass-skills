# Update Policy

画像更新必须保留证据链、置信度和可撤回性。不要把单次表达直接升级成永久人格判断。

## Auto Apply

只有同时满足下列条件时，才可自动写为 `active`：

- 用户明确自述其长期或默认协作偏好，或当前 session 中反复、直接、低歧义地观察到。
- `sensitivity` 是 `low`。
- `confidence >= 0.75`。
- 不与现有 active 断言冲突。
- 断言影响的是沟通、需求对齐、工作流、证据偏好或风险确认，不是敏感身份判断。
- 证据不是单纯的 AGENTS、系统/开发者指令、skill 操作步骤或当前任务约束。

用户主动提供的年龄段、学历、专业、职业/角色、经验阶段、长期目标等背景信息，即使是明确自述，默认也不自动写入 active；先生成 pending proposal，由用户确认后保存为 `private`。

## First-Run Adequacy

首次构建画像时，不得把“当前上下文足够”作为默认结论。agent 必须先做充分性判断：

- 如果用户明确要求 WebUI、问卷或首次初始化问卷，必须启动问卷。
- 如果本地没有 active profile，且当前 session 只包含任务执行规则、AGENTS 约束、隐私边界或 skill 使用说明，视为上下文不足。
- 只有用户明确拒绝问卷，或当前 session 提供了覆盖至少 4 个问卷模块的长期自述，才可跳过问卷。
- 跳过问卷时，必须输出覆盖模块、证据来源和未覆盖模块。

当前任务约束可以约束本次执行，但默认不升级为长期 active profile。若确实可能有长期价值，先生成 pending proposal，由用户确认。

## Session Inference

agent 可以从 session 中提出画像推断，但推断必须服务于协作，而不是给用户贴标签。

推断候选必须满足：

- `source_type=inferred`。
- 默认 `sensitivity=private`；涉及身份、健康、财务、法律、政治、宗教、家庭、亲密经历或真实定位时至少为 `sensitive`，多数情况下应避免生成。
- 默认进入 pending proposal，不得自动应用。
- `value` 包含 `summary`、`basis`、`reasoning`、`counter_evidence`、`usefulness`、`review_question`。
- 证据来自当前 session 的具体行为或明确文本，而不是模型常识、路径猜测、时区猜测或语言刻板印象。

置信度上限：

- 单一弱信号：`confidence <= 0.4`。
- 多个一致但仍可替代解释的 session 信号：`confidence <= 0.6`。
- 用户明确确认某个推断后，可作为 `self_report` 或 `correction` 重新写入，置信度可高于 `0.75`。

以下推断不得静默写入 active：

- 用户是哪里人、真实所在地、民族、政治/宗教倾向、健康、财务、法律风险、亲密关系。
- 用户能力、性格、价值观、心理状态或道德倾向的强标签。
- 任何可能影响系统如何限制、评价或区别对待用户的高影响判断。

## Pending Proposal

以下情况必须进入 pending：

- `source_type` 是 `inferred`。
- `sensitivity` 是 `private`、`sensitive`、`intimate` 或 `secret`。
- 用户自述背景信息默认 `private`，包括年龄段、学历、专业、职业/角色、经验阶段、长期目标。
- 与现有 active 断言冲突。
- 可能影响用户被如何对待、被如何判断，或可能形成不公平定型。
- 用户表达了“可能”“也许”“我不确定”等低确定性语气。
- 来源主要是当前任务约束、skill 操作规则或一次性上下文，但 agent 认为可能转化为长期协作偏好。

## Conflict Handling

如果新候选与同一 `category + claim + scope` 的 active 断言不同：

1. 不覆盖旧断言。
2. 生成 pending proposal。
3. 标注冲突对象。
4. 由用户确认后再 supersede 旧断言。

## Correction

用户纠正画像时，优先级最高：

- 原断言设为 `retracted` 或 `superseded`。
- 新断言 source_type 设为 `correction`。
- audit_log 记录纠错原因。

## Anti-Staleness

画像不是永久结论。能力边界、偏好、工作方式和风险容忍度可能变化。读取画像时应优先使用：

1. 当前 session 明确说法。
2. 用户最近纠正。
3. 高置信 active 断言。
4. 较旧或低置信观察。

不要用旧画像覆盖当前明确要求。
