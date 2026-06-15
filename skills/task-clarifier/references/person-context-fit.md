# Person Context Fit

按用户当前表达状态、任务领域和可选画像摘要选择澄清方式。不要做心理诊断；只处理需求表达和执行风险。

## Clear Expert

信号：目标、范围、交付物、验收、约束多数已给出。

方式：做遗漏审计，不重复问已给信息。

高信号检查：

- 是否有非目标。
- 是否有验收标准。
- 是否有风险边界。
- 是否有证据边界。
- 是否有外部副作用或不可逆动作。

## Clear Thinking, Weak Expression

信号：用户似乎知道自己要什么，但表达跳跃、术语不稳或缺结构。

方式：槽位化追问，给选项和示例答案。

结构：

```markdown
我先把需求拆成 4 个槽位：目标、交付物、范围、验收。
目前我已确定 X 和 Y；还缺 Z。你可以直接选 A/B/C。
```

## Not Yet Clear

信号：用户还在探索、目标/受众/成功标准不稳定。

方式：intent interview，一次只问一个最能改变方向的问题。

先问：

- 真正受众是谁？
- 成功时用户会拿到什么？
- 什么结果看似正确但会让你觉得 miss？

## Sensitive Or Avoidant Expression

信号：用户明显回避、用含混词替代关键行为、涉及隐私/安全/羞耻/法律/公开后果。

方式：非评判、解释为什么问、允许不回答、明确安全边界。

不要追问个人动机。只问执行所需变量：

- 目标动作是什么。
- 是否涉及第三方、隐私、credential、外部副作用。
- 哪些内容不能保存、搜索、发送或公开。

## Cross-Domain Drop

信号：用户在熟悉领域表达清楚，但当前任务跨到陌生领域。

方式：教学支架。降低术语密度，提供示例答案；如果用户回答很具体，再提升问题精度。

## Always Preserve Agency

用户可以选择：

- 快速澄清。
- 证据优先。
- 一问一答。
- best guess with assumptions。

但 destructive、credential、remote、publishing、privacy-sensitive 场景不能被 best guess 覆盖。
