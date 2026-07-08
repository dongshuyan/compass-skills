# 并发与多 session 稳定性

## 目录

- 问题
- 设计原则
- 锁
- 原子写入
- Proposal 乐观并发控制
- 多 session 推荐流程
- 故障恢复

## 问题

同一个任务目录可能同时有多个 Codex、Claude 或其他 agent session 调用 `$task-forest`。如果它们同时读旧状态、各自写回，就可能出现：

- 节点 ID 重复；
- 后写入覆盖先写入；
- `nodes.json` 和 `edges.json` 读到不一致版本；
- proposal 基于旧图，应用后覆盖新 session 的更新；
- HTML 或导出 JSON 被半写入时读取。

## 设计原则

1. 所有正式写入必须通过 `scripts/task_forest.py`。
2. 所有读 canonical graph 的命令也要短暂持锁，保证读取的是同一版本。
3. 写入使用临时文件 + `os.replace` 原子替换。
4. proposal 保存时记录 `base_graph_hash`，应用时默认检查当前图是否仍是同一版本。
5. 多 session 可以并行生成 proposal，但正式应用必须串行。
6. 不用“最后写入者获胜”策略；这会静默丢失任务信息。

## 锁

CLI 使用 repo-local 锁文件：

```text
.agent-workbench/task-forest/lock
```

锁文件包含：

```json
{
  "token": "<random-token>",
  "pid": 12345,
  "started_at": "2026-06-13T00:00:00.000000Z",
  "path": "<lock-path>"
}
```

规则：

- 每个命令进入 canonical graph 读写区前获取锁。
- 默认等待 30 秒，可用 `--lock-timeout` 或 `TASK_FOREST_LOCK_TIMEOUT` 调整。
- 锁龄优先由 `started_at` 计算；如果锁文件半写入、内容损坏、不是 dict JSON，或 `started_at` 缺失/不可解析，则退化为文件系统 `mtime`，避免坏锁永久残留。
- POSIX 用 `os.kill(pid, 0)` 探活；Windows 用 `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE) + WaitForSingleObject(handle, 0)` 探活，避免 `GenerateConsoleCtrlEvent` 的语义偏差。
- 如果能明确确认持锁进程已死，且锁龄超过 `DEAD_PID_GRACE_SECONDS`，CLI 会快速清理陈旧锁。
- 如果锁龄超过 `TASK_FOREST_STALE_LOCK_SECONDS`，CLI 会按租约过期处理，即使 PID 无法解析、无法可靠探活，或持锁进程长时间挂起，默认阈值为 6 小时。
- 释放锁时只删除自己 token 对应的锁；如果锁文件已消失或被文件系统暂时占用，清理按 best-effort 处理，后续命令会继续尝试恢复。

## 原子写入

JSON、JSONL 和 HTML 写入策略：

- JSON 和 HTML 先写到同目录隐藏临时文件；
- flush + fsync 后使用 `os.replace` 替换目标文件；
- JSONL 事件追加发生在锁内，并 fsync；
- 派生产物 `exports/*.json` 和 `task-forest.html` 也使用原子替换。

这样读者不会看到半个 JSON 或半个 HTML。

## Proposal 乐观并发控制

保存 proposal 时，CLI 记录当前图 hash：

```json
{
  "base_graph_hash": "<sha256>",
  "base_summary": {
    "node_count": 10,
    "edge_count": 12,
    "workspace_path": "/path/to/repo"
  }
}
```

应用 proposal 时：

- 当前图 hash 与 `base_graph_hash` 一致：允许应用。
- 当前图 hash 已变化：默认拒绝应用，提示重新生成 proposal。
- 用户人工确认无冲突后，可以传入 `--allow-stale`。

不要默认使用 `--allow-stale`。它只适合用户明确确认“虽然图变了，但这个 proposal 仍然可以应用”的场景。

## 多 session 推荐流程

每个 session 结束时：

1. 读取当前图。
2. 生成独立 proposal，`proposal_id` 使用唯一 ID 或包含 session 标识。
3. 保存 proposal，不直接应用。
4. 给用户展示变更摘要。
5. 用户确认后应用。
6. 如果应用时提示 stale，重新读取当前图并重新生成 proposal。

多个 session 同时保存 proposal 是允许的；多个 session 同时应用 proposal 会被锁串行化，且 stale 检查会防止旧 proposal 覆盖新状态。

## 故障恢复

如果命令异常退出：

- 首先运行 `validate` 检查当前图；
- 如果提示锁被占用，查看锁文件里的 pid 和 `started_at`；
- 如果锁文件内容异常或 pid 无法可靠判断，不要手动改 canonical 文件；重新运行命令，CLI 会先按 `started_at`，再按文件 `mtime` 判断是否应回收；
- 不要手动编辑 `nodes.json`、`edges.json` 或 `config.json`；
- 需要修正错误时，生成新的 proposal 或使用 CLI 的更新命令。
