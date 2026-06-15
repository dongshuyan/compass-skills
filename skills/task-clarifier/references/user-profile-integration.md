# User Profile Integration

`user-profile-keeper` 是可选 skill。`task-clarifier` 不能依赖它存在；未安装、数据库不存在、读取失败或摘要为空时，按当前上下文继续工作。读取摘要不得为了探测画像而创建新画像数据库。

## Allowed Read

只允许读取低敏摘要：

```bash
# macOS / Linux
python3 <user-profile-keeper-dir>/scripts/profile_store.py read --user default --view clarification_summary

# Windows
py -3 <user-profile-keeper-dir>\scripts\profile_store.py read --user default --view clarification_summary
```

`<user-profile-keeper-dir>` 是当前安装的 `user-profile-keeper` skill 目录。不要假设 skill 一定安装在某个固定路径。

允许使用的信息：

- 沟通偏好。
- 澄清方式偏好。
- 决策方式。
- 领域熟悉度和能力边界。
- 常见遗漏。
- 风险确认偏好。
- 反茧房规则。

禁止读取或使用：

- 完整画像。
- pending proposal。
- sensitive/intimate/raw evidence。
- secret、credential、token。
- 未确认的敏感推断。

## Failure Fallback

读取失败时不要打断用户，也不要要求用户安装画像 skill。直接回退到：

1. 当前用户消息。
2. 当前 session 约束。
3. 本地文件、repo、日志、官方来源。
4. `adaptive-communication.md` 的当前任务临时估计。

## Use In Clarification

画像摘要只影响“怎样问”，不替代“是否需要问”。例如：

- 用户偏好结构化回答：问题可以编号。
- 用户常漏验收标准：在 contract 中显式列 Acceptance。
- 用户对高风险操作敏感：删除、覆盖、发布前加强确认。

如果画像与当前消息冲突，当前消息优先。

## No Writes

`task-clarifier` 不写画像。用户要求记录、更新或纠错画像时，明确路由到 `$user-profile-keeper`。
