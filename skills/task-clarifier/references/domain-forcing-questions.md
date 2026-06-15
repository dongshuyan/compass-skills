# Domain Forcing Questions

这些是高信号问题包，不是必问题清单。先读上下文，只问会改变执行路径的问题。

## 目录

- Coding Change
- Debugging
- CS Research / Literature
- Experiment / Benchmark
- Academic Writing
- Security / Privacy / Installation
- Automation / External Side Effect

## Coding Change

优先自查：目标文件、现有测试、调用方、public API、配置、README、错误日志。

高信号变量：

- 预期行为是什么，当前行为是什么。
- 验收标准是最小 patch、可维护 refactor、性能优化，还是兼容性优先。
- 哪些边界不能变：public API、CLI、文件格式、checkpoint、输出 schema、依赖栈。
- 是否允许迁移、网络调用、依赖升级、全局配置或跨模块改动。
- 测试范围：只覆盖变更，还是补邻近脆弱边界。
- 失败时回滚或降级策略是什么。

默认：先做最小连贯改动，保持公开行为，运行窄验证。

## Debugging

先收集/复现：

- exact failing command/input。
- expected vs observed。
- 最近改动。
- logs/artifacts/checkpoints。
- 是否可重跑，以及时间/API/数据成本。

高信号变量：

- 用户要 root-cause proof、最快 workaround，还是 durable fix。
- 哪个行为是 canonical：测试、文档、线上行为、历史输出。
- 连续 3 次修复失败或假设被否定时，停止局部 patch，重新审视架构/边界。

默认：不在没有 root cause 或明确 workaround 目标时反复试补丁。

## CS Research / Literature

先确认：

- research question 或比较对象。
- 输出物：方向梳理、source-grounded summary、系统综述、citation audit、论文段落、实验计划。
- 证据标准：官方/primary repo、peer-reviewed papers、benchmark、arXiv、博客、实现代码。
- 时间边界：latest/current、历史某日期、last 30 days、稳定背景。
- inclusion/exclusion：领域、venue、年份、方法族、语言、开源/闭源。
- 不确定 claim 如何处理：排除、标低置信、或单独列为待验证。

默认：研究结论区分事实、推断和证据缺口；不可编造 citation 或 claim。

## Experiment / Benchmark

必须明确或查证：

- primary metric 和不能回退的 secondary/guardrail metrics。
- dataset、split、seed、baseline、protocol。
- 成功/失败/无效结果标准。
- compute/API/runtime 预算。
- 统计或复现实验要求。
- 数据泄漏、缺 baseline、wrong split、non-determinism、failed run 的处理。

默认：不把 exploratory run 包装成 publication-grade evidence。

## Academic Writing

先判阶段：

- story selection: 选择叙事和 claim。
- drafting: 在冻结故事和证据上写。
- polishing: 不重选故事，只改善表达。

高信号变量：

- 目标 venue、读者、页数/字数。
- 已锁定 claim、实验、baseline、限制。
- 禁用 framing、术语、比较对象。
- 是否需要 reviewer defensibility、novelty framing、mechanism clarity、concision。

默认：不新增无证据 claim，不虚构引用，不把假设写成结果。

## Security / Privacy / Installation

确认：

- 目标是推荐、审计、试安装、本地安装、全局安装，还是修改后安装。
- 允许权限：只读 clone、本地写入、shell 执行、网络、依赖安装、credential、全局配置。
- 是否假设 hostile intent。
- 触碰 secret、私有 repo、浏览器 session、SSH key、token 是否禁止。
- 哪些动作需要二次确认：复制文件、运行脚本、改配置、安装依赖、更新 dashboard。

默认：先读源码和静态扫描；不运行不可信脚本；不做全局写入。

## Automation / External Side Effect

确认：

- 外部系统：GitHub、email、calendar、社交平台、cloud API、支付、发布端点。
- 执行方式：一次、定时、人工确认后、dry run。
- 失败策略：立即停止、best effort、限次重试、只通知。
- audit trail：日志、报告、diff、artifact folder、通知摘要。
- 最终确认点：发送、发布、删除、远程写入前必须确认。

默认：优先生成本地 preview/dry run。
