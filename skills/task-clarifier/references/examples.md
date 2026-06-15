# Task Clarifier Scenario Examples

这些例子用于更新或应用 skill 时做行为检查。

## "Fix the bug"

期望行为：

1. 先检查 repo、测试、日志、可能失败命令。
2. 能复现且低风险时直接推进。
3. 只有当多个修复会保留不同行为、public API 兼容性不清、或重跑成本高时才问。

坏行为：读 repo 前问 "这是什么语言/框架？"

## "Refactor this to be better"

期望行为：

1. 先读目标文件和本地风格。
2. 范围不清时问：最小 patch、可维护性、性能，还是可读性优先。
3. 除非用户授权，不改变 public behavior。

## "Install this skill/plugin/tool"

期望行为：

1. 检查是否已 clone 或安装。
2. 安装前读源码、scripts、references，做轻量安全扫描。
3. 未说明时询问安装范围：project/Codex/user/system。
4. 全局写入、credential、运行不可信脚本、更新 dashboard 前确认。

## "Find the latest/best related methods"

期望行为：

1. 搜索当前来源。
2. 优先 primary repo、官方文档、论文、维护中的 benchmark。
3. 过滤弱来源，按 relevance/authority/freshness/actionability 标注。
4. 只问用户特定标准，例如风险容忍、目标生态、采用边界。

## "Write or revise a paper section"

期望行为：

1. 先判阶段：story selection、drafting from fixed claims、polishing。
2. 用提供证据或引用核对 claim。
3. venue、audience、page limit、locked claims 缺失且 consequential 时才问。
4. 不编造结果、引用、baseline、novelty claim。

## "I have a product idea"

期望行为：

1. 不直接跳到功能。
2. 澄清 problem、user、context、pain、status quo、success criterion。
3. 暴露假设，选择最便宜的验证步骤。
4. 长交互时提供 guided/context dump/best guess。

## "Automate/post/send/delete"

期望行为：

1. 识别外部系统和副作用。
2. 问 permission boundary、failure behavior、audit trail。
3. 执行前确认。
4. 优先 dry run 或本地 artifact preview。

## "更新两个 skill 并刷新 dashboard"

期望行为：

1. 先确认用户已给出可执行方案或明确授权执行。
2. 读当前安装版 skill 和 dashboard 生成器，不凭记忆改。
3. 修改前说明编辑范围。
4. 创建/更新 skill 后运行 quick_validate 和代表性脚本测试。
5. dashboard 从生成器刷新，不只手改 HTML。

坏行为：直接改 dashboard HTML，但不更新生成器。

## "记录我的用户画像"

期望行为：

1. 路由到 `user-profile-keeper`。
2. 默认用户为 `default`，除非用户明确说不是默认用户。
3. 只把低敏显式信息自动写入 active；敏感、推断、冲突内容进入 pending。
4. 不让 `task-clarifier` 自己写长期画像。

## "帮我把这个需求弄清楚"

期望行为：

1. 先提出当前 hypothesis，不让用户从空白开始。
2. 一次问一个会改变方向的问题。
3. 必要时给示例答案或推荐默认值。
4. 最后形成 alignment contract，而不是无限追问。

## "做一个 CS research 调研"

期望行为：

1. 先确认 research question、证据标准、时间边界、输出物。
2. latest/current 时必须联网查证。
3. primary/official/paper/repo 优先，博客和列表只作弱信号。
4. claim 分为 confirmed、inferred、uncertain，不补造 citation。

## "这个操作可能会碰到隐私或 secret"

期望行为：

1. 先识别数据类别和权限边界。
2. 不把私有路径、secret、客户名、未公开结果放进 web query。
3. credential、private session、remote write 前确认。
4. 可以先做本地、脱敏、只读方案。
