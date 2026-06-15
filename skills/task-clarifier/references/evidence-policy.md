# Task Clarifier Evidence Policy

用于 research-first clarification 和风险敏感决策。

## Source Tiers

| Tier | 来源 | 默认处理 |
|---|---|---|
| S0 | 用户文件、current repo、本地配置、exact logs、运行输出 | 本地真相最高；必要时验证 freshness |
| S1 | 官方文档、primary repo、标准、论文、API reference | 技术和研究事实优先来源 |
| S2 | 维护良好的高质量 repo、benchmark、vendor example | primary source 不完整时使用 |
| S3 | 博客、教程、论坛、社区示例 | 只作为模式参考，不作权威结论 |
| S4 | 社交帖、prompt dump、模型输出、未验证列表 | 弱信号；不得单独依赖 |

## Filtering Criteria

使用证据前检查：

- `relevance`: 是否回答精确缺口。
- `authority`: 是否 primary、官方、维护中。
- `freshness`: 是否可能近期变化。
- `consistency`: 独立来源是否一致。
- `actionability`: 是否改变下一步。
- `risk`: 是否可能暴露数据、credential、用户或组织信息。

低相关证据直接丢弃，不把筛选责任转给用户。

## Search Privacy Gate

联网前先判断是否会泄漏专有信息：

- 可搜索通用技术名、公开错误码、公开库/API、论文题目、公开 repo。
- 不搜索私有路径、内部项目名、secret、客户名、未公开实验结果、私有论文草稿内容。
- 需要搜索敏感上下文时，先泛化 query；仍不够时向用户确认。
- 对 latest/current、法律/医疗/财务/安全、API 行为和开源项目状态，必须查当前来源。

## Confidence Labels

- `high`: local/primary evidence 直接回答，且无实质冲突。
- `medium`: 证据相关但间接、不完整或轻微过时。
- `low`: 证据弱、冲突、旧、非权威。
- `needs confirmation`: 证据合理，但决策属于用户或安全敏感。

## When To Search Before Asking

先搜索/读取而不是问用户：

- 用户要求最新、当前、真实、本机、本地 repo、当前安装版。
- API、库、工具、平台行为可能变化。
- repo、文件树、日志、配置可能回答问题。
- 用户会被迫重复可发现上下文。
- 外部成熟方法会影响方案质量。

技术、法律、医疗、财务、安全和研究 claim 优先使用 official/primary source。

## When To Confirm Despite Evidence

即使证据充分，也要确认：

- 全局安装、共享配置、依赖升级、迁移。
- credential、secret、私有浏览器会话、私有 repo。
- 删除、覆盖、发布、发送、排程、远程写入。
- 安全、隐私、法律、财务、研究结论 tradeoff。
- 将不确定证据用于论文、benchmark、公开材料、高影响决策。

确认语言必须点名具体动作、范围和停止条件。
