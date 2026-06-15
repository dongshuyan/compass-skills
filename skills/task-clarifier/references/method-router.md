# Task Clarifier Method Router

用于在多种澄清方式都可能适用时选择最小有效方法。

## Methods

| Method | 使用时机 | 交互方式 |
|---|---|---|
| Direct default | 任务足够清楚、低风险、可逆 | 说明假设并推进 |
| Research-first | 缺失事实可发现 | 先读代码/文件/资料，再只问残余决策 |
| Batch clarification | 1-5 个独立用户决策 | 紧凑编号问题 |
| Method picker | 多个流程合理 | 2-3 个模式、推荐项、取舍 |
| Intent interview | 真实目标、受众、动机或约束不清 | 假设 + 置信度，一次一问 |
| Spec gate | 复杂功能、实验、论文、设计、工作流需要稳定契约 | 收集目标、范围、边界、验收 |
| Risk gate | 安全、隐私、安装、破坏性、外部副作用 | 明确权限、边界、停止条件 |

## Route Transparency

当选择路线或交给其他 skill 时，简短说明：

- `route`: 选择的任务类型或 skill。
- `signals`: 触发依据，例如用户关键词、repo 证据、风险类型。
- `override`: 用户可如何改路线。

例：

```markdown
我会走 research-first + spec gate：这个请求涉及当前安装版 skill 和后续修改，先读真实文件，再只问会改变方案的问题。你也可以要求我改成只做审计不修改。
```

## Installed Skill Handoffs

当专门 skill 明显适用时，路由而不是复制它：

- `interview-me`: 隐藏意图、真实目标、成功标准不明。
- `idea-refine`: 原始想法需要扩展、比较、收敛。
- `spec-driven-development`: 新功能/系统需要冻结需求后实施。
- `source-driven-development`: API、框架、库行为依赖当前文档或源码。
- `doubt-driven-development`: 非平凡计划、claim 或实现需要反驳式检查。
- `user-profile-keeper`: 用户明确要求创建、更新、查询、纠错或删除本地长期用户画像。
- PM discovery 类 skill：产品发现、访谈、假设、PRD、优先级、验证实验。

如果 skill 未安装或未被请求，只借鉴模式，不声称已使用。

## Method Picker Pattern

当几种澄清方式都合理：

```markdown
有几种方式可选。我建议 1，因为 [原因]。

1. 快速澄清（推荐）：我问 1-3 个关键问题，然后开始。
2. 证据优先：我先读文件/搜索，再问剩余决策。
3. 深入对齐：一次问一个问题，直到目标、受众和验收稳定。
```

选项必须互斥。若选项超过 4 个或包含独立范围项，拆分成多轮，避免悄悄丢选项。

## Entry Modes For Guided Work

长交互任务可提供：

- `Guided`: 一次一个问题。
- `Context dump`: 用户一次性贴上下文，agent 跳过已回答部分。
- `Best guess`: agent 推断缺口、标注假设并推进。

适用：产品发现、skill 创建/升级、PRD、研究计划、复杂写作。不要用于常规代码修复或简单事实回答。

## Product Discovery Route

产品想法、功能请求、PRD、路线图、用户问题：

1. 先定义问题，不先跳到功能。
2. 明确用户、场景、痛点、现有替代方案、成功标准。
3. 暴露 value/usability/feasibility/viability/GTM 假设。
4. 按影响和不确定性排序。
5. 推荐最便宜的验证动作。

## Prompt Design Route

prompt、agent workflow、输出质量问题：

1. 识别意图：生成、转换、推理、批判、agentic workflow、澄清。
2. 先用简单结构，不堆命名框架。
3. 只有会改变 prompt 时才问受众、格式、约束、例子。
4. 明确评估标准：什么输出算好，什么输出算失败。

## During Execution

澄清不是只发生在开头。执行中如果发现新的高影响分叉：

1. 停止当前有风险动作。
2. 说明发现了什么证据。
3. 给出推荐默认值。
4. 只问会改变下一步的问题。

如果发现需要删除、覆盖、迁移、全局安装、使用 credential、发布、远程写入或公开共享，即使前面 verdict 是 `aligned`，也要切到 `Risk gate` 并确认具体动作。
