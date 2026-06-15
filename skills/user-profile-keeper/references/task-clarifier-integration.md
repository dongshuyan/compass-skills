# Task Clarifier Integration

`user-profile-keeper` 是可选 skill。未安装或无画像时，`task-clarifier` 必须按自身规则正常运行。画像摘要只提升提问贴合度，不是 task-clarifier 可用性的前置条件。

## Boundary

- `task-clarifier` 不写画像。
- `task-clarifier` 不读取完整画像。
- `task-clarifier` 只可读取 `clarification_summary`。
- `task-clarifier` 读取摘要失败时，应静默回退到当前 session 内的临时交互判断。
- 当前用户消息优先于历史画像。
- 年龄段、教育、专业、职业/角色、经验阶段、长期目标、所在地和身份推断等背景信息不属于默认 `task-clarifier` 输入。

## Clarification Summary

摘要只应包含低敏、active、与需求对齐有关的信息：

- 沟通偏好。
- 澄清方式偏好。
- 决策方式。
- 领域熟悉度和能力边界。
- 常见遗漏。
- 风险确认偏好。
- 反茧房规则。

不得包含：

- intimate/raw evidence。
- secret。
- 未确认敏感推断。
- `background_context`、`education_background`、`career_context`、`learning_context` 中的 private 背景信息。
- `inference_hypothesis` 中未被用户确认的推断。
- 对用户人格、道德、心理状态的诊断式标签。

## Usage Pattern

当 `$task-clarifier` 面对高成本或长任务时，可先尝试：

```bash
# macOS / Linux
python3 <user-profile-keeper-dir>/scripts/profile_store.py read --user default --view clarification_summary

# Windows
py -3 <user-profile-keeper-dir>\scripts\profile_store.py read --user default --view clarification_summary
```

`<user-profile-keeper-dir>` 是当前安装的 `user-profile-keeper` skill 目录。不要假设 skill 一定安装在某个固定路径。

如果命令失败、skill 不存在、数据库未初始化或摘要为空，则忽略画像，继续按当前上下文澄清。`clarification_summary` 读取在无画像时必须零写入。

如果需要用户背景信息帮助任务澄清，应在当前对话中直接询问用户，或由用户明确调用 `$user-profile-keeper` 查看/维护 `profile_overview` 或 `full`；不要让 `task-clarifier` 自行读取完整画像。

## Anti-Bubble Requirement

即使摘要存在，也必须至少做一次当前上下文校正：

- 画像是否被用户当前话语覆盖？
- 当前任务是否在用户熟悉领域外？
- 是否存在新风险、新受众、新验收标准？
- 是否需要问一个跳出画像的反向问题？
