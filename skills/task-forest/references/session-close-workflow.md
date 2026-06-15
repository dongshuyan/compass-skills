# session 关闭工作流

## 目录

- 目标
- 判断流程
- 何时询问用户
- 偏差检测
- 进度和估时
- 推荐回答格式

## 目标

session 关闭时，目标是把本轮对话对任务结构的影响准确写入 task-forest。不要把完整聊天记录无筛选地保存进去；只保留对任务图有长期价值的结构化信息。

## 判断流程

1. 读取当前状态：

```bash
python3 scripts/task_forest.py list --json
python3 scripts/task_forest.py todo --json
```

2. 从本轮对话提取候选事实：

- 用户明确提出的新目标；
- 用户真实目的、受众、成功标准或非目标；
- 对旧目标的要求修正；
- 已完成、部分完成、废止或阻塞的任务；
- 新发现的依赖关系；
- 设计决策；
- 风险和偏差；
- 需要用户回答的问题；
- session 结束后的 follow-up。

3. 与已有节点对齐：

- 标题近似但要求不同：更新旧节点并记录新要求，不要重复创建。
- 新工作服务于旧目标：建子任务并加 `child_of`。
- 一个工作服务多个目标：选择一个主父节点，再加 `contributes_to`。
- 前置关系：加 `depends_on`，不要误用 `child_of`。
- 讨论产物只是解释旧任务：建 `clarifies` 或直接更新旧节点。
- 用户说的动作不能达成用户目的：不要直接建 ready 任务；先生成候选方案或记录 risk/deviation。

4. 生成 proposal，先预校验，再让用户确认。

5. 应用 proposal 后运行：

```bash
python3 scripts/task_forest.py validate
python3 scripts/task_forest.py export
```

6. 如果本轮影响了节点、边、状态、历史或 HTML 模板，按 `html-visualization-contract.md` 抽查导出 HTML。至少确认：

- `树视图` 可展示主层级，节点卡片短小且点击后显示详情；
- `DAG 视图` 可展示多种关系边，边标签为中文且可点击；
- `child_of` 在界面中显示为 `子任务`；
- DAG 节点可拖拽，拖动时边和边标签跟随，`重置布局` 可恢复；
- 顶部 `待复核`、`阻塞`、`未完成` 等统计可筛选并可取消；
- `review_needed` 节点详情解释“待复核要看什么”；
- 历史变化支持滑块和播放；
- 左右侧栏收起后，页面向下滚动仍能看到展开按钮。

如果应用 proposal 时提示当前图已经变化，不要直接加 `--allow-stale`。先重新读取 `list --json` 和 `todo --json`，重新判断本轮变更是否仍然成立。只有用户明确确认无冲突时，才允许使用 `--allow-stale`。

## 何时询问用户

必须询问：

- 无法判断本轮对话服务哪个目标；
- 新任务可能成为 global task，也可能是旧任务子任务；
- 一个节点看似有多个主父节点；
- 更新会把任务标为 done、deprecated 或 archived；
- 发现高严重度偏差，需要用户决定是否接受；
- 估时、完成度或难度会影响其他插件推荐。
- 任务是否真的能达成用户目的存在实质不确定性。

可以先提出确认：

- 能基本判断关系，但存在低到中等不确定性；
- 只是新增子任务、补充要求、更新进度；
- 用户已经明确说“按你的判断更新”。

不用询问但仍要说明：

- 初始化空 task-forest；
- 导出 HTML；
- 只读查询 todo/list/show；
- 保存未确认 proposal，不应用正式变更。

## 目标对齐和方案生成

当本轮对话涉及“应该做什么任务”“这个任务的意义是什么”“它是否能达到用户目的”时，读取 `goal-alignment.md`。

先用 task-clarifier 的问题质量规则确认真实目的。然后生成 2-3 个候选任务方案，比较可行性、有效性、准确性、完整性、稳定性、鲁棒性、复杂度和代价。用户选择后再写入 proposal。

每个被写入的重要任务应补充 `purpose`、`desired_outcomes`、`success_metrics`、`non_goals`、`assumptions` 和 `alignment` 字段。需要保留本次选择过程时，使用 `record_alignment`。

## 偏差检测

比较三类信息：

- 用户原始要求和验收标准；
- 本轮实际执行或产物；
- 现有任务节点的状态和进度。

发现偏差时，proposal 中加入 `record_deviation`：

```json
{
  "action": "record_deviation",
  "deviation": {
    "related_task_ids": ["TF-0001"],
    "severity": "medium",
    "expected_requirement": "数据应保留在 repo 内",
    "observed_action_or_result": "实现方案仍依赖全局 SQLite 保存完整任务",
    "evidence": "本轮设计中提到完整任务写入全局 SQLite",
    "recommendation": "改为 repo-local graph 文件，全局 SQLite 只保留 registry",
    "status": "open",
    "confidence": 0.8
  }
}
```

严重度建议：

- `low`：描述或文档不够精确，但不影响执行。
- `medium`：实现方向可能偏离用户要求，需要修正。
- `high`：会导致错误交付、数据丢失、隐私问题或明显违反用户要求。

## 进度和估时

进度来源优先级：

1. 用户明确说明；
2. 验收标准完成比例；
3. 子任务加权平均；
4. agent 基于证据的低置信度估计。

估时必须保留不确定性：

- 有明确范围时写 `remaining_minutes_min/max`。
- 只有粗略判断时使用宽范围，并降低 `confidence`。
- 没有依据时写 `difficulty: unknown`，不要编造精确分钟数。

## 推荐回答格式

确认前：

```text
我准备这样更新 task-forest：

新增：
- TF-????：<标题>，作为 <父节点> 的子任务，因为 ...

更新：
- TF-0001：把状态从 ready 改为 in_progress；新增要求 ...

关系：
- <新节点> child_of TF-0001
- <新节点> contributes_to TF-0003

偏差：
- 发现 ...，建议记录为 medium deviation。

确认后我会应用 proposal、运行 validate，并重新导出 HTML。
```

应用后：

```text
已应用 proposal <id>。
校验结果：通过。
HTML：<absolute path>/task-forest.html
HTML 抽查：通过 / 未运行（原因：...）。
未完成任务：N 个，其中 ready X 个、blocked Y 个、review_needed Z 个。
```
