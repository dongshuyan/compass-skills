---
name: task-forest
description: 维护当前任务目录的 repo-local 任务森林或任务 DAG。Use when the user asks to initialize, update, close a session, summarize evolving project tasks, decide whether a new request is a global task or subtask, track task progress/history/deviations/todos, export a task graph HTML, or provide task data for gap-router/local-agent-control-room. Do not use for executing the tasks themselves.
---

# Task Forest

本 skill 只维护任务结构，不替用户执行任务。它把当前 repo 的长期目标、子任务、依赖、完成度、偏差、待办和 session 历史保存到 repo-local 数据目录，并导出可离线查看的 HTML。

## 核心原则

1. 不直接手写 `.agent-workbench/task-forest/` 下的数据文件；所有写入必须通过 `scripts/task_forest.py`。
2. 任务模型内部是 DAG，但默认展示成森林：每个节点最多一个 `child_of` 主父节点，多归属用 `contributes_to`，执行前置关系用 `depends_on`。
3. 不确定用户意图时先询问。基本能判断时也要先给出变更提案，让用户确认后再应用。
4. 不把未确认的猜测写入正式任务图；只保存为 proposal。
5. 发现执行结果偏离用户要求时，记录 deviation，并把相关任务改为 `review_needed` 或等待用户确认。
6. 数据默认保存在当前 repo 的 `.agent-workbench/task-forest/`，不要把完整任务图放进全局 SQLite；全局 SQLite 只允许保存 task-forest 的轻量索引和运行留痕。
7. 同一目录下多个 session 并发运行时，只允许通过 CLI 串行读写；不要绕过锁直接修改 JSON。
8. HTML 导出是本 skill 的正式产品面，不是附属调试页面；从零构建时也必须满足 `references/html-visualization-contract.md` 的交互和可读性契约。

## CLI

从任意目录执行时，使用本 skill 目录下的脚本。下列示例里的 `<skill-dir>` 表示当前 `SKILL.md` 所在目录；在 Codex 中应先按 skill 路径解析到真实目录，再执行脚本：

```bash
python3 <skill-dir>/scripts/task_forest.py --help
```

默认 workspace 是当前工作目录。需要指定任务目录时传入：

```bash
python3 <skill-dir>/scripts/task_forest.py init \
  --workspace /path/to/repo
```

常用命令：

```bash
# 初始化
python3 <skill-dir>/scripts/task_forest.py init

# 新增顶层任务
python3 <skill-dir>/scripts/task_forest.py add-node \
  --kind global_task \
  --title "构建本地 agent 工作台" \
  --requirement "任务数据保存在 repo 内" \
  --acceptance "可以导出 HTML 查看任务图"

# 新增子任务
python3 <skill-dir>/scripts/task_forest.py add-node \
  --title "实现任务图 HTML 导出" \
  --parent TF-0001 \
  --estimate 120 \
  --difficulty medium

# 查看未完成事项
python3 <skill-dir>/scripts/task_forest.py todo

# 导出 HTML
python3 <skill-dir>/scripts/task_forest.py export

# 校验 DAG、边、状态和字段
python3 <skill-dir>/scripts/task_forest.py validate
```

## Session 关闭更新流程

当用户要求“更新任务森林”“关闭本次 session”“根据本轮对话维护任务 list”时：

1. 运行 `init`，确保数据目录存在。
2. 运行 `list --json` 和 `todo --json`，读取当前节点和未完成项。
3. 分析本轮对话，只生成候选变更：新增节点、更新节点、增加边、废止节点、记录偏差。
4. 如果无法判断本轮目的，询问用户“这次对话主要服务哪个目标”。不要猜完直接写入。
5. 如果可以基本判断，向用户展示准备应用的变更，包括每个新增节点放在哪里、与已有任务是什么关系、哪些字段会更新。
6. 将候选变更保存为 proposal；用户确认后再 `proposal-apply --yes`。
7. 应用后运行 `validate` 和 `export`，并按 `references/html-visualization-contract.md` 抽查 HTML，最后把 HTML 路径告诉用户。

proposal 的 JSON 格式、字段含义和不变量见 `references/schema.md`。复杂 session 的判断规则见 `references/session-close-workflow.md`。

HTML 可视化的视图、交互、中文标签、待复核说明、DAG 节点拖拽、历史播放、折叠侧栏和从零回归要求见 `references/html-visualization-contract.md`。修改 `scripts/task_forest.py` 的 HTML 模板时必须同步更新该契约，并运行 `scripts/validate_task_forest_export.py`。

当需要判断任务在全局中的意义、用户真实目的、任务是否真的能达成目的，或需要生成多个候选任务方案供用户选择时，读取 `references/goal-alignment.md`。澄清方法使用 `$task-clarifier` 的规则，任务图和候选方案写入使用 task-forest。

并发和多 session 规则见 `references/concurrency.md`。proposal 保存时会记录 `base_graph_hash`；应用时如果任务图已经被其他 session 修改，默认拒绝应用。只有人工确认无冲突时才允许使用 `--allow-stale`。

## 任务节点判断

新增内容通常按以下顺序归类：

- `global_task`：用户提出一个长期目标，且不能自然归入已有 global task。
- `task` / `subtask`：为了完成某个已有任务而产生的具体工作。
- `requirement`：用户新增或修正了验收要求，但它不是独立工作。
- `decision`：本轮确定了设计选择、边界或取舍。
- `risk`：发现阻塞、安全、数据、准确性或执行偏差风险。
- `question`：需要用户回答才能继续。
- `follow_up`：本轮结束后需要处理的小事项。

同一个工作服务多个目标时，不要创建多个 `child_of` 父节点；保留一个主父节点，再用 `contributes_to` 连接其他目标。

每个重要任务都应尽量记录：

- `purpose`：这个任务服务的用户真实目标；
- `desired_outcomes`：用户期望得到的具体结果；
- `success_metrics`：如何判断目的达成；
- `non_goals`：明确不做什么；
- `assumptions`：当前方案成立所需假设；
- `alignment`：为什么这个任务符合目标、哪里仍不够、如何验证。

## 输出和集成

导出文件固定在：

```text
.agent-workbench/task-forest/exports/task-forest.graph.json
.agent-workbench/task-forest/exports/task-forest.todos.json
.agent-workbench/task-forest/exports/task-forest.timeline.json
.agent-workbench/task-forest/exports/task-forest.html
```

`gap-router` 和 `local-agent-control-room` 应只读这些导出文件，不要直接修改 task-forest 数据。具体字段契约见 `references/integration-contract.md`。

为方便跨 session 和插件发现已有任务森林，`init`、`export`、`validate`、`proposal-save`、`proposal-apply` 会尽力更新全局轻量 registry：

```text
~/.agent-workbench/agent-workbench.sqlite3
```

该 registry 只保存 workspace 路径、task-forest 路径、导出文件路径、导出 hash、节点/边/状态计数、命令运行状态和错误摘要。它不保存节点正文、边正文、历史快照、HTML、proposal 内容或完整对话摘要。可用 `AGENT_WORKBENCH_DB` 指定数据库位置；若需要完全禁用全局索引，可设置 `TASK_FOREST_DISABLE_GLOBAL_REGISTRY=1`。

从零构建回归：

```bash
python3 <skill-dir>/scripts/validate_task_forest_export.py --skill-dir <skill-dir>
```

该脚本会在临时 workspace 中初始化 task-forest、创建覆盖多状态和多边类型的样例 DAG、运行 `validate/export`，并检查导出 JSON 和 HTML 是否具备当前约定的可视化能力。

## 边界

- 该 skill 不能保证自动在每个 session 结束时运行；可靠方式是显式调用。
- 该 skill 不能百分百推断用户真实目标；低置信度变更必须询问或停留在 proposal。
- 删除任务应优先改为 `deprecated`，不要硬删除历史。
- 估时必须给出置信度；依据不足时标为 `unknown` 或低置信度。
