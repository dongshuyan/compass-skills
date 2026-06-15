# Hidden Intent Interview

当用户话语过宽、过常规、或为了安全表达而隐藏真实目标时使用。把 hidden intent 当成缺失需求，不要心理分析。

## Signals

考虑 intent interview 当请求包含：

- 宽泛质量词："更好"、"专业"、"现代"、"鲁棒"、"best practice"。
- 委托式模糊："你看着办"、"make it good"、"whatever you think"。
- 低估工作量："只是 polish"、"小改一下"、"简单 review"。
- 多个可能受众或成功标准。
- 用户真正需要方法、决策或诊断，而不是单一输出。
- 当前上下文和表面请求有张力。

## Protocol

1. 先检查上下文，不要开局深挖动机。
2. 给出具体假设和置信度。
3. 点名哪个不确定性会改变工作。
4. 一次只问一个问题。
5. 可给推荐猜测或选项，降低用户回答成本。
6. 用用户自己的词复述答案。
7. 当下一步和可能反对点可预测时停止。

## Useful Question Forms

- "我当前假设是 [X]，置信度 [N]%。如果这个判断错了，输出应该会变。真实目标更接近 A、B 还是 C？"
- "如果不需要向任何人解释，你真正想要的结果是什么？"
- "即使技术上正确，什么会让这个结果感觉像 miss？"
- "真正受众是谁：你、合作者、reviewer、用户、评估者，还是未来 agent？"
- "什么要避免，因为它会制造社交、政治、隐私或维护风险？"
- "什么看起来像自然改进，但其实必须 out of scope？"

## Restatement Contract

intent interview 后执行前复述：

- Outcome。
- Audience。
- Why now。
- Success criterion。
- Constraints。
- Out of scope。

高风险或长任务要求显式确认。普通可逆任务可标注假设后推进。

## Anti-Patterns

- 没读上下文就问多个深层问题。
- 让用户解释个人动机。
- 高返工/高风险任务中把 "sounds good" 当作足够确认。
- 把有边界的技术任务变成 coaching session。
- 执行路径已经清楚后继续追问。
