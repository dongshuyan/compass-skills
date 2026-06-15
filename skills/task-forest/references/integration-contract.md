# task-forest 集成契约

## 目录

- 固定导出文件
- gap-router 读取方式
- local-agent-control-room 读取方式
- 写入边界
- 全局 SQLite 边界

## 固定导出文件

每次 `export` 后生成：

```text
.agent-workbench/task-forest/exports/task-forest.graph.json
.agent-workbench/task-forest/exports/task-forest.todos.json
.agent-workbench/task-forest/exports/task-forest.timeline.json
.agent-workbench/task-forest/exports/task-forest.html
```

消费者应读取 `exports/`，不要读取 `graph/nodes.json` 和 `graph/edges.json`，更不要直接写它们。

## gap-router 读取方式

`gap-router` 的任务池来源应优先使用 `task-forest.todos.json`。推荐候选条件：

- `status` 属于 `proposed`、`ready`、`in_progress`、`review_needed`；
- `ready == true`；
- 排除 `done`、`deprecated`、`archived`；
- 排除 `blocked_by` 非空的任务，除非用户明确想处理阻塞。

可用字段：

```text
id
title
purpose
kind
status
progress
priority
difficulty
remaining_minutes_min
remaining_minutes_max
ready
blocked_by
next_action
confidence
context_tags
desired_outcomes
success_metrics
alignment
```

推荐逻辑可以结合 gap-router 自己的等待时间、切入成本、切回成本和精力参数。若需要记录用户执行结果，gap-router 应写入 task-forest proposal，而不是直接改 task-forest 图。

推荐给用户时，优先使用 `purpose` 和 `alignment.why_this_task` 解释“为什么这件事符合当前 global 目的”；如果这些字段为空，应降低推荐置信度或提示需要先做目标对齐。

如果需要更快获得候选队列，也可以读取 `task-forest.graph.json` 中的派生字段：

```text
status_queues.actionable_todos
status_queues.ready
status_queues.review_needed
status_queues.evergreen_open_goals
```

其中 `evergreen_open_goals` 代表长期持续目标，不能简单按剩余分钟推荐给用户；应只作为当前上下文和目的解释来源。真正适合碎片时间推荐的是 `actionable_todos` 和 `ready` 中具备估时、低切换成本、低阻塞风险的节点。

## local-agent-control-room 读取方式

`local-agent-control-room` 应读取 `task-forest.graph.json`，把 agent/session 状态叠加到任务节点上：

```text
session_id -> source_sessions 或 proposal.session_id
waiting_human -> question / review_needed
risk finding -> risk / deviation proposal
completed session -> review_needed 或 done proposal
```

控制室可以展示：

- 哪个 session 正在处理哪个任务节点；
- 哪些节点完成但待 review；
- 哪些节点被风险事件影响；
- 哪些任务等待用户回答；
- 哪些任务长时间无进展。

新版 `task-forest.graph.json` 提供了便于控制室展示的派生字段：

```text
status_queues.blocked
status_queues.review_needed
status_queues.open
edge_index.<node_id>.incoming
edge_index.<node_id>.outgoing
edge_index.<node_id>.blocking_edges
edge_index.<node_id>.cross_edges
edge_type_counts
tree_edges
cross_edges
```

控制室应使用这些字段定位“谁卡住、谁待复核、谁有跨任务依赖”。展示层可以默认使用 `child_of` 作为层级树，把 `depends_on`、`contributes_to`、`clarifies` 等边作为可点击关系边展示，避免把 DAG 误读成纯树。

如果控制室复用 `task-forest.html` 的交互经验，应遵守 `html-visualization-contract.md` 的用户语义：`child_of` 面向用户显示为 `子任务`，DAG 节点拖拽只是展示层布局，不是任务事实，不能把拖拽后的坐标写回 task-forest graph。

控制室不应直接修改 task-forest 的正式状态。它可以生成 proposal：

```text
.agent-workbench/task-forest/proposals/<proposal_id>.json
```

然后由 `$task-forest` 读取、解释、请求用户确认并应用。

## 写入边界

唯一允许正式写入 task-forest 的程序是：

```bash
scripts/task_forest.py
```

其他插件只允许：

- 读取 `exports/`；
- 写入未确认 proposal；
- 写入外部观察日志，再由 task-forest 转成 proposal。

HTML 中的按钮、搜索、筛选、播放、缩放、平移、DAG 节点拖拽和侧栏折叠都属于浏览器本地视图状态。其他插件不应把这些 UI 状态当成任务状态，也不应从 HTML 反向解析任务事实；需要任务数据时读取 JSON export。

## 全局 SQLite 边界

全局 SQLite 可以保留轻量 registry：

```text
workspace_path
task_forest_path
exports_dir
graph_export_path
todos_export_path
timeline_export_path
html_export_path
last_seen_at
last_export_at
last_export_hash
node_count
edge_count
ready_count
review_needed_count
blocked_count
evergreen_count
status
last_error
```

推荐表名：

```text
aw_task_forests
aw_task_forest_runs
```

`task_forest.py` 会在 `init`、`export`、`validate`、`proposal-save`、`proposal-apply` 后尽力更新该 registry。`gap-router` 和 `local-agent-control-room` 也可以在读取某个 workspace 的导出文件时刷新该 registry，以便下一次能够发现这个 workspace。

不要把节点、边、事件、快照、HTML、proposal 内容或完整对话摘要保存到全局 SQLite。完整数据必须留在 repo-local task-forest 目录。全局 registry 只是发现入口和健康状态摘要，不是任务事实源。
