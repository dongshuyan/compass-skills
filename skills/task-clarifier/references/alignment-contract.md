# Alignment Contract

用于把澄清结果收敛成可执行、可验证、可纠错的契约。

## Verdicts

- `aligned`: 已可执行，无重大未决问题。
- `aligned-with-assumptions`: 可执行，但有明确、可逆、低/中风险假设。
- `needs-answer`: 需要用户回答，否则会改变范围、方法、证据、验收或风险。
- `blocked`: 没有安全默认值；继续会明显偏离目标或制造风险。

## Contract Fields

按任务复杂度选择字段，不要机械全部输出：

- `Outcome`: 用户真正要得到什么。
- `Audience`: 给谁看、谁使用、谁评审。
- `Scope`: 做什么。
- `Non-goals`: 明确不做什么。
- `Evidence boundary`: 用哪些来源，排除哪些来源。
- `Deliverable`: 交付格式和文件/界面形态。
- `Acceptance`: 怎样算完成。
- `Constraints`: 时间、预算、工具、依赖、格式、风格、兼容性。
- `Safety boundary`: 隐私、security、credential、外部副作用。
- `Assumptions`: agent 将采用的默认值。
- `User-understanding check`: 用户是否已经清楚自己的目标、范围、交付物和验收。
- `Agent-understanding check`: agent 如何理解需求，以及这个理解会怎样改变执行路径。
- `User-visible restatement`: 给用户看的短复述，便于用户纠偏。
- `Profile influence`: 是否读取了本地低敏画像摘要；若没有，写 `none` 或不展示。
- `Out-of-profile check`: 当前任务是否可能不符合历史偏好或常规模式。
- `Stop condition`: 何时暂停并回问用户。

## Confirmation Rules

仅当下列任一情况成立时，要求用户显式确认 contract：

- 长时间或高成本任务。
- destructive、global、credential、remote、publishing、external-side-effect。
- 删除、覆盖、迁移、安装、公开共享、高影响设计选择或不可逆文件操作。
- 论文、benchmark、公开材料或影响他人的决策。
- 用户答案和可观察证据冲突。
- contract 中存在不可逆或高风险假设。

普通可逆任务可直接说：

```markdown
我会按这个 contract 执行；如果我遇到会改变范围或风险的新证据，会停下来确认。
```

## Option Preservation

当用户给出多个独立范围项或 UI/工具限制导致不能一次展示全部选项：

1. 不要静默删选项。
2. 把独立决策拆成多轮。
3. 标出依赖关系和互斥关系。
4. 最后复述 assembled choice。

例：

```markdown
这里有 7 个独立决策，一次问会混淆。我先确认交付范围，再确认证据标准，最后确认风险边界。
```

## Minimal Contract Examples

低风险代码修复：

```markdown
Verdict: aligned-with-assumptions
- Scope: 只修复复现失败路径。
- Non-goals: 不重构相邻模块，不改 public API。
- Acceptance: 相关测试通过。
- Assumption: 如果文档和测试冲突，以测试表现为准；若发现 public API 分歧会暂停确认。
```

高风险发布：

```markdown
Verdict: needs-answer
- Outcome: 发布到外部平台。
- Safety boundary: 会触发公开可见副作用。
- Needed answer: 是否允许我在最终预览后点击发布。
```

完整对齐但可执行：

```markdown
Verdict: aligned-with-assumptions
- Outcome: 更新两个 skill 并刷新 dashboard。
- User-visible restatement: 我会先改可选画像 skill，再让 task-clarifier 只读低敏摘要；未安装画像 skill 时 task-clarifier 仍独立工作。
- Safety boundary: 不上传画像，不读取 credential；删除/覆盖/发布类动作前停下确认。
- Profile influence: none。
- Out-of-profile check: 本次用户明确要求完整执行，所以可直接实施已确认方案。
- Stop condition: 如果发现需要全局安装依赖、删除现有 skill 或写入远程，会暂停确认。
```
