# 目标对齐与候选任务生成

## 目录

- 与 task-clarifier 的边界
- 目标对齐流程
- 任务是否能达成目的
- 候选方案格式
- 写入 task-forest
- 反例和降级策略

## 与 task-clarifier 的边界

`task-clarifier` 负责判断：

- 是否需要问用户；
- 该问一个问题、批量问题、方法选择还是 intent interview；
- 是否需要先研究、确认或阻塞。

`task-forest` 负责判断：

- 当前任务在全局任务图中的意义；
- 它服务哪个 global 目的；
- 它是否真的能达成用户预想目的；
- 若不能，应该拆出哪些更有效的候选任务；
- 多个候选任务方案各自的可行性、有效性、准确性、完整性、稳定性和复杂度。

不要把 task-clarifier 改成项目管理工具。task-forest 调用它的澄清方法，但专门的任务图、候选方案和目的-任务对齐逻辑保留在 task-forest。

## 目标对齐流程

当用户提出新任务、修改任务、要求生成任务，或当前 session 的目的不清晰时：

1. 先读取当前任务图：

```bash
python3 scripts/task_forest.py list --json
python3 scripts/task_forest.py todo --json
```

2. 用 task-clarifier 的规则判断是否需要问用户：

- 如果真实目的、受众、成功标准、风险边界不清楚，做 intent interview。
- 如果可从当前图、用户消息或本地文件推断，先推断并标注置信度。
- 如果多个工作流都合理，给出 2-3 个方法选择。
- 如果更新会产生高成本或长期影响，先确认。

3. 把用户目的拆成结构化字段：

```text
user_goal: 用户真正想达到的结果
why_now: 为什么现在要做
success_metrics: 如何判断目的达成
constraints: 必须满足的边界
non_goals: 明确不做什么
risk_tolerance: 对复杂度、准确性、速度、稳定性的偏好
```

4. 与任务森林对齐：

- 能挂到已有 global task：用 `child_of` 或更新旧节点。
- 同时服务多个目标：选一个主父节点，再用 `contributes_to`。
- 目的不属于任何现有 global task：新增 `global_task`。
- 现有任务不能达成目的：不要硬挂；生成替代任务方案。

## 任务是否能达成目的

评估每个候选任务时至少回答：

```text
fit: aligned | partial | weak | misaligned | unknown
why_this_task: 为什么它能服务用户目的
why_not_enough: 它无法覆盖哪些需求或风险
feasibility: low | medium | high
effectiveness: low | medium | high
accuracy: low | medium | high
completeness: low | medium | high
stability: low | medium | high
robustness: low | medium | high
complexity: low | medium | high
confidence: 0.0-1.0
validation_plan: 如何验证它确实达成目的
```

如果 `fit` 是 `weak`、`misaligned` 或 `unknown`，不要把任务直接标为 ready。应提出澄清问题、记录风险，或生成更合适的候选方案。

## 候选方案格式

当用户需要选择任务方案时，给出 2-3 个方案，避免无差异堆砌。

```text
我把你的真实目标理解为：...

方案 A：低复杂度快速版
- 任务：
- 为什么符合目标：
- 能覆盖：
- 覆盖不了：
- 可行性：
- 有效性：
- 准确性：
- 完整性：
- 稳定性/鲁棒性：
- 代价：
- 验证方式：

方案 B：平衡版（推荐）
...

方案 C：高完整度版
...

我的推荐：B，因为 ...
需要你选择的是：速度优先、平衡优先，还是完整度优先。
```

方案必须真实可执行。不要为了凑数量生成明显低质量方案。

## 写入 task-forest

确认后，生成 proposal。节点字段应尽量包含：

```json
{
  "purpose": "用户真实目标",
  "desired_outcomes": ["期望结果"],
  "success_metrics": ["判断目标达成的指标"],
  "non_goals": ["不做什么"],
  "assumptions": ["关键假设"],
  "alignment": {
    "user_goal": "用户真实目标",
    "fit": "aligned",
    "fit_confidence": 0.85,
    "why_this_task": "为什么这个任务能达成目的",
    "why_not_enough": "仍然不足的部分",
    "validation_plan": ["验证步骤"]
  }
}
```

需要保留一次对齐审计时，在 proposal 中加入：

```json
{
  "action": "record_alignment",
  "alignment": {
    "related_task_ids": ["TF-0001"],
    "user_goal": "用户真实目标",
    "candidate_summary": "本轮生成的候选任务方案摘要",
    "selected_option": "B",
    "rejected_options": ["A", "C"],
    "reason": "选择 B 的理由",
    "node_alignment": {
      "user_goal": "用户真实目标",
      "fit": "aligned",
      "fit_confidence": 0.85,
      "why_this_task": "为什么符合目标",
      "why_not_enough": "尚未覆盖的边界",
      "validation_plan": ["如何验证"]
    },
    "confidence": 0.85
  }
}
```

## 反例和降级策略

不要这样做：

- 用户目的不清楚时直接创建任务。
- 把“用户说要做的动作”当成“用户真正要达成的目的”。
- 为了给用户选择而生成不可行或明显劣质方案。
- 只解释任务本身，不解释它如何服务 global 目的。
- 忽略任务可能无法达成目的的风险。

降级策略：

- 目的不清楚：问一个 task-clarifier 风格的问题。
- 方案都不可靠：明确说当前信息不足，只保存 question 节点或 proposal。
- 任务与目的冲突：记录 `record_deviation` 或新增 `risk` 节点。
- 用户要快速推进：给一个推荐方案和两个备选摘要，并标注假设。
