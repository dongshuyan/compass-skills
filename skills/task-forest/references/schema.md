# task-forest 数据模型

## 目录

- 存储位置
- 节点
- 边
- 状态
- DAG 与树形视图
- HTML 可视化契约
- 事件和快照
- Proposal 格式
- 校验规则

## 存储位置

默认目录：

```text
<workspace>/.agent-workbench/task-forest/
```

核心文件：

```text
config.json
graph/nodes.json
graph/edges.json
graph/forest.json
events/events.jsonl
proposals/<proposal_id>.json
deviations/deviations.jsonl
alignments/alignments.jsonl
todos/todos.json
snapshots/<sequence>.json
exports/task-forest.graph.json
exports/task-forest.todos.json
exports/task-forest.timeline.json
exports/task-forest.html
lock
```

`nodes.json` 和 `edges.json` 是当前状态的权威来源。`events.jsonl` 是历史审计日志。`exports/` 和 `todos/` 是派生产物，可以通过 `export` 重建。

并发写入规则见 `concurrency.md`。任何 session 都不能绕过 CLI 直接编辑这些文件。

## 节点

节点是任务、要求、决策、风险或待办。字段：

```json
{
  "id": "TF-0001",
  "title": "实现任务森林 skill",
  "kind": "global_task",
  "status": "in_progress",
  "summary": "repo-local 维护任务 DAG、历史和 HTML。",
  "purpose": "让用户长期看清当前 repo 的真实任务结构和进展",
  "desired_outcomes": ["用户能看到任务森林和历史变化"],
  "requirements": ["数据留在 repo 内"],
  "acceptance_criteria": ["可以导出 HTML", "可以校验 DAG 无环"],
  "success_metrics": ["HTML 能展示任务图、历史和未完成事项"],
  "non_goals": ["不直接执行用户任务"],
  "assumptions": ["用户愿意在 session 结束时显式调用 skill"],
  "alignment": {
    "user_goal": "准确维护当前任务目录的全局任务结构",
    "fit": "aligned",
    "fit_confidence": 0.85,
    "why_this_task": "该任务提供 repo-local 任务图和历史导出，能支撑用户长期追踪全局目标",
    "why_not_enough": "不能保证自动在每个 session 结束时运行",
    "validation_plan": ["运行 validate", "打开 HTML 检查节点详情"]
  },
  "alignment_records": [],
  "progress": 40,
  "progress_source": "manual",
  "priority": 3,
  "difficulty": "medium",
  "estimated_total_minutes": 180,
  "remaining_minutes_min": 60,
  "remaining_minutes_max": 90,
  "confidence": 0.8,
  "context_tags": ["agent-workbench"],
  "execution_hints": ["先运行 validate"],
  "source_sessions": ["session-2026-06-13"],
  "evidence": ["用户明确要求做成 skill"],
  "deviations": [],
  "created_at": "2026-06-13T00:00:00.000000Z",
  "updated_at": "2026-06-13T00:00:00.000000Z",
  "deprecated_at": null
}
```

允许的 `kind`：

```text
global_task, milestone, task, subtask, requirement, decision, risk, question, follow_up
```

允许的 `status`：

```text
proposed, ready, in_progress, blocked, review_needed, done, deprecated, archived
```

允许的 `difficulty`：

```text
low, medium, high, very_high, unknown
```

## 边

边表达任务之间的关系。字段：

```json
{
  "id": "TFE-0001",
  "from": "TF-0002",
  "to": "TF-0001",
  "type": "child_of",
  "blocking": true,
  "reason": "TF-0002 是 TF-0001 的实现子任务",
  "confidence": 0.85,
  "created_from_session": "session-2026-06-13",
  "created_at": "2026-06-13T00:00:00.000000Z",
  "updated_at": "2026-06-13T00:00:00.000000Z"
}
```

允许的 `type`：

```text
child_of, depends_on, contributes_to, related_to, duplicates, supersedes, clarifies, derived_from
```

语义：

- `child_of`：结构分解关系，`from` 是 `to` 的主子任务。每个节点最多一个 `child_of` 父节点。HTML 用户界面中显示为“子任务”。
- `depends_on`：执行依赖，`from` 必须等 `to` 完成后才算 ready。
- `contributes_to`：一个任务同时贡献给另一个目标，不改变主树位置。
- `related_to`：弱相关，不影响进度或 ready 判断。
- `duplicates`：语义重复，应合并或废止其中之一。
- `supersedes`：`from` 替代 `to`。
- `clarifies`：`from` 澄清 `to` 的要求或问题。
- `derived_from`：`from` 来源于 `to`，常用于将讨论拆成任务。

## DAG 与树形视图

task-forest 的权威数据模型是有向无环图（DAG），不是纯树。原因是一个任务可能既属于一个主分解路径，又依赖、贡献、澄清或替代另一个任务。

为了让用户容易理解层级，HTML 默认使用 `child_of` 边生成竖向树形主视图：

- `child_of` 是唯一主父边：每个节点最多只能有一个 `child_of` 父节点。
- 非 `child_of` 边是跨边：用于表达依赖、贡献、澄清、替代、重复、来源等关系，不改变节点在主树中的位置。
- 所有边仍然保留在 DAG 中，HTML 的 `DAG 视图` 和节点详情会展示这些边的方向、类型、原因和置信度。

因此，“树”只是默认可读视图；“DAG”才是完整任务关系。

## HTML 可视化契约

HTML 导出不是数据模型本身，但它是 task-forest 的主要用户界面。`task-forest.html` 必须遵守 `references/html-visualization-contract.md`：

- 树视图用 `child_of` 展示主层级；
- DAG 视图展示所有可见边，不应叫“DAG 边”；
- `child_of` 对用户显示为 `子任务`；
- 边标签可点击并跟随对应边移动；
- DAG 节点拖拽只改变当前页面运行态布局，不写回 `nodes.json` 或 `edges.json`；
- `review_needed` 必须能定位到具体节点，并解释复核对象和下一步；
- 历史快照必须支持手动查看和播放；
- 左右侧栏收起后，滚动页面时仍应保留可展开按钮。

## 导出视图模型

`exports/task-forest.graph.json` 除了节点、边、根节点和统计信息外，还包含面向下游工具和 HTML 的派生字段：

```json
{
  "tree_edges": ["TFE-0001"],
  "cross_edges": ["TFE-0002"],
  "edge_index": {
    "TF-0001": {
      "incoming": ["TFE-0001"],
      "outgoing": ["TFE-0002"]
    }
  },
  "edge_type_counts": {
    "child_of": 5,
    "depends_on": 1
  },
  "status_queues": {
    "open": ["TF-0001", "TF-0002"],
    "blocked": [],
    "review_needed": ["TF-0002"],
    "ready": ["TF-0005"],
    "evergreen_open_goals": ["TF-0001"],
    "actionable_todos": ["TF-0002", "TF-0005"]
  },
  "status_legend": {
    "review_needed": "已经基本完成，但需要用户或执行者复核后才能转为 done。"
  },
  "edge_type_legend": {
    "depends_on": "执行依赖：from 必须等 to 完成后才算 ready。"
  }
}
```

这些字段都是派生视图，不是新的权威状态。下游工具应该优先读取 `nodes` 和 `edges`，用派生字段减少重复计算：

- gap-router 可以读取 `status_queues.actionable_todos`、`evergreen_open_goals` 和节点的 `remaining_minutes_*`，给用户推荐等待间隙可做事项。
- local-agent-control-room 可以读取 `status_queues.blocked`、`review_needed`、`edge_index` 和 `edge_type_counts`，展示谁卡住、谁待复核、哪些任务存在依赖或跨任务关系。
- HTML 可以读取 `status_legend` 和 `edge_type_legend`，把“待复核”等统计数字解释清楚，并让用户点到具体节点或边。

## 事件和快照

每次正式写入都追加 `events/events.jsonl`，并生成一个 `snapshots/<sequence>.json`。HTML 的历史滑块使用 snapshots 展示任务图如何随 session 变化。

不要编辑历史事件。需要修正时追加新事件。

## Proposal 格式

AI 对 session 的归纳必须先保存为 proposal：

```json
{
  "proposal_id": "TFP-example",
  "session_id": "session-2026-06-13",
  "rationale": "本轮对话要求实现 task-forest skill。",
  "status": "proposed",
  "changes": [
    {
      "action": "add_node",
      "alias": "new-global",
      "node": {
        "title": "实现 task-forest skill",
        "kind": "global_task",
        "status": "in_progress",
        "requirements": ["repo-local 存储", "HTML 可视化"],
        "acceptance_criteria": ["validate 通过", "HTML 导出成功"],
        "confidence": 0.9
      }
    },
    {
      "action": "add_node",
      "alias": "html-export",
      "node": {
        "title": "导出历史任务图 HTML",
        "kind": "subtask",
        "status": "ready"
      }
    },
    {
      "action": "add_edge",
      "from": "html-export",
      "to": "new-global",
      "type": "child_of",
      "edge": {
        "reason": "HTML 导出是该 global task 的验收子任务"
      }
    }
  ]
}
```

保存并预校验：

```bash
python3 scripts/task_forest.py proposal-save --proposal-file proposal.json
```

用户确认后应用：

```bash
python3 scripts/task_forest.py proposal-apply TFP-example --yes
```

保存 proposal 时 CLI 会自动加入 `base_graph_hash`。应用时如果当前任务图已经被其他 session 更新，默认拒绝应用；只有人工确认无冲突时才使用 `--allow-stale`。

支持的 action：

```text
add_node, update_node, set_status, deprecate_node, add_edge, remove_edge, record_deviation, record_alignment
```

`record_alignment` 用于审计“为什么当前任务符合用户真实目的、为什么选择某个候选方案、如何验证”。详细工作流见 `goal-alignment.md`。

## 校验规则

CLI 必须拒绝：

- 不存在的节点引用；
- 自指边；
- 重复边；
- 非法 `kind`、`status`、`type`；
- 多个 `child_of` 主父节点；
- `child_of` 环；
- `depends_on` 环。

低置信度、估时缺失、difficulty 不规范等问题可以作为 warning。
