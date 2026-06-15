# Task Clarifier Decision Model

用于判断应该 `proceed`、`research-first`、`ask`、`confirm`、`offer-method-choice` 还是 `block`。

## Uncertainty Ledger

对每个会改变工作的缺口记录：

- `gap`: 缺失变量是什么。
- `task impact`: 不同答案会怎样改变执行路径。
- `discoverable`: 能否从本地文件、repo、日志、官方文档、primary repo、论文或当前 web 查到。
- `owner`: `agent`、`user`、`external fact`、`shared`。
- `impact if wrong`: `low`、`medium`、`high`、`critical`。
- `reversibility`: `easy`、`moderate`、`hard`、`irreversible`。
- `safety class`: `normal`、`privacy`、`credential`、`destructive`、`external-side-effect`、`security`、`publication`。
- `confidence`: `high`、`medium`、`low`。

不通过 task-impact 测试的缺口不要问。

## EVPI-Lite Rule

提问价值上升：

- 答案改变范围、方法、证据、格式、安全姿态或验收标准。
- 决策权属于用户，而不是 agent 或外部事实。
- 错误代价高，或动作难以撤销。
- 结果会被安装、引用、发布、发送、排程、提交或公开共享。
- 证据冲突、过时、低置信，且会影响结论。
- 如果不问，无法证明用户、agent 和用户可见复述三者已经对齐。

提问价值下降：

- 下一步可逆，错误可低成本修正。
- 保守默认值明显。
- 答案可从本地或 primary source 查到。
- 用户已经给出清晰约束。
- 问题只是低风险风格偏好，可后续迭代。

## Action Matrix

| 缺口类型 | 优先动作 |
|---|---|
| 本地文件、repo、日志可能回答 | 先 inspect/read/run，不问用户 |
| 当前外部事实重要 | 查 primary/current source |
| 低风险偏好缺失 | 用保守默认值并标注 |
| 验收标准缺失且返工风险高 | `ask` |
| 目标、受众或真实约束不清 | `intent interview` |
| 多个合理工作流 | `offer-method-choice` |
| 删除、全局安装、credential、发布、远程写入 | `confirm` |
| 覆盖、迁移、公开共享、高影响设计或研究结论 | `confirm` |
| 用户拥有决策且无安全默认值 | `block` |

## Alignment Completeness Gate

长任务、高风险任务、用户要求完整对齐、或需求包含多层约束时，执行前检查：

- `user understands`: 用户是否已经能用具体目标、范围、交付物和验收标准理解自己的需求。
- `agent understands`: agent 是否能把需求转成可执行步骤、证据边界和停止条件。
- `user can verify agent understanding`: 用户是否看到了足够短但具体的复述，并能指出偏差。
- `risk confirmed`: 删除、覆盖、安装、发布、credential、远程写入、公开材料或高影响决策是否已确认。

如果任一项为否，选择 `ask`、`confirm` 或 `aligned-with-assumptions`，不要把“用户没继续追问”当作对齐完成。

## Alignment Verdict

在长任务、高风险任务、或多轮澄清后给出 verdict：

- `aligned`: 目标、范围、证据、交付物、验收、安全边界足够明确。
- `aligned-with-assumptions`: 可执行，但存在已标注且可逆的假设。
- `needs-answer`: 存在用户拥有的高影响缺口，回答后才能安全执行。
- `blocked`: 继续执行会明显偏离目标、制造风险，或没有安全默认值。

## Question Budget

- 简单可逆任务：0 个问题，直接默认推进。
- 普通 coding/research：通常 1-3 个高信号问题。
- spec gate、实验、论文、发布、安全：可问 3-5 个，但必须都是 decision-changing。
- intent interview：一次只问 1 个问题，直到下一步和可能反对点可预测。
- 如果超过 5 个独立决策，拆成多轮或用方法选择，不要一次塞满。
- 用户明确要求“完整对齐”时，可以超过普通预算，但每个问题仍必须 decision-changing；优先用 contract 暴露已知部分，避免从空白开始问卷式追问。

## Stop Conditions

停止提问当：

- 可以预测用户对下一步最可能的反对点。
- 剩余不确定性可通过可逆迭代处理。
- 继续提问不会改变当前执行路径。
- 用户选择 best-guess/autonomous 模式，且风险边界允许。

只有新答案暴露新的高影响分叉时，才继续问。
