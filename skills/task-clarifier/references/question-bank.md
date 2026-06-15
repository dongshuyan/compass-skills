# Task Clarifier Question Bank

选择性使用。只问会改变下一步的问题。能从本地文件、repo、日志、primary source 或当前 web 查到的，不问用户。

## 目录

- Question Shape
- Universal High-Signal Questions
- Method Choice
- Adaptive Phrasing Examples
- Research-First Filtering
- Hidden Intent And Audience
- Coding Changes
- Debugging
- Research Facts And Literature
- Academic Story And Writing
- Experiments And Benchmarks
- Figures, Tables, Posters, Diagrams
- Security, Installation, Supply Chain
- Automation And External Side Effects

## Question Shape

高影响或难回答的问题优先写成：

```markdown
我需要确认 [变量]。
为什么重要：[它会改变什么]。
我的当前猜测：[默认值/推荐值]。
你可以回答：[选项或示例答案]。
```

低风险问题可以直接问。不要为了模板牺牲简洁。

## Universal High-Signal Questions

- 你要的交付物是什么：直接答案、代码 patch、报告、Markdown、slides、figure、table、script、runnable app？
- 验收标准是什么：正确性、速度、美观、复现性、publication readiness、安全、最小改动？
- 证据边界是什么：只用本地文件、只用提供来源、允许 web、只用官方来源、完整文献搜索？
- 什么不能变：API、文件名、数据格式、叙事 claim、视觉风格、依赖栈、运行环境？
- 风险容忍度是什么：探索草稿、production-safe、publication-safe、security-sensitive、无外部副作用？
- 为了确认我们完全对齐，我当前会按 [X] 执行；有没有一个关键目标、非目标或验收标准我漏掉了？

## Method Choice

- 你希望快速澄清、证据优先，还是一问一答深度对齐？
- 你想用 guided、context dump，还是 best-guess with assumptions？
- 如果速度、严谨性、低打扰、用户控制不能同时满足，优先哪个？
- 是否允许我路由到更专门的 skill/workflow？如果不允许，我会保留轻量澄清。

## Adaptive Phrasing Examples

专业版：

- "范围是最小 patch 还是允许同模块重构？"

通俗版：

- "我需要确认改动范围。比如只修眼前 bug 会更快；顺手重构会更稳但可能碰到更多文件。你更想要哪种？"

推荐默认版：

- "我建议先做最小 patch，因为当前风险来自单一路径。除非你明确授权，我不会改 public API。"

## Research-First Filtering

- 是否完全排除弱来源，还是保留但标低置信？
- 需要 current/latest，还是稳定背景知识足够？
- 优先官方文档、primary repo、peer-reviewed papers、benchmark，还是 practitioner examples？
- 如果来源冲突，我应该暂停确认，还是给出 alternatives + confidence？

## Hidden Intent And Audience

- 我当前假设是 [X]，置信度 [N]%。如果错了，真实目标更接近 A、B 还是 C？
- 真正受众是谁：你、合作者、reviewer、用户、评估者、未来 agent？
- 即使技术上正确，什么会让结果感觉不对？
- 什么应排除，因为会制造社交、政治、隐私或维护风险？
- 如果你不需要向任何人解释选择，你真正想要的结果是什么？

## Coding Changes

- 应优先最小 patch、可维护 refactor，还是更广的 cleanup？
- 如果测试、文档和当前代码冲突，哪个是 canonical？
- 需要守住什么兼容边界：CLI、public API、file format、checkpoint、saved output、downstream script？
- 测试只覆盖改动行为，还是顺带覆盖附近脆弱边界？
- 是否允许网络调用、依赖升级、migration、全局配置变更？

## Debugging

- exact failing command、input、expected output、observed output 是什么？
- 这是最近 regression 吗？开始失败前改了什么？
- 你要 root-cause proof、最快 workaround，还是 durable fix with tests？
- 我能重跑失败流程吗？有没有时间、API、数据或费用限制？
- 哪些 logs/artifacts/checkpoints/prior runs 应视为 ground truth？

## Research Facts And Literature

- 证据标准是什么：快速定位、source-grounded summary、systematic search、citation audit、publication-grade verification？
- 哪些来源算数：官方文档、论文、GitHub repo、benchmark、新闻、博客、社交帖、专利？
- 时间边界是什么：当前最新、某历史日期、last 30 days、稳定背景？
- 比较维度是什么：能力、安全、采用度、成本、可复现性、与你 workflow 的适配？
- 不确定或弱证据 claim 是排除，还是显式标置信度？

## Academic Story And Writing

- 当前阶段是 story selection、drafting from frozen story，还是 polishing？
- 目标 venue、读者、页数/字数限制是什么？
- 哪些 claim 已由现有证据锁定，哪些仍是假设或待实验？
- 写作应优先 novelty framing、mechanism clarity、reviewer defensibility，还是 concision？
- 有哪些 forbidden framing、term、baseline、comparison 会造成 overclaim？

## Experiments And Benchmarks

- primary metric 是什么，哪些 secondary/guardrail metrics 不能退化？
- dataset split、seed policy、baseline set、evaluation protocol 哪个权威？
- 目标是 diagnosis、rerun planning、result aggregation、figure generation，还是 claim validation？
- compute/API budget 和最大 runtime 是多少？
- 什么会让结果无效：leakage、missing baseline、wrong split、non-determinism、failed run、sample size 不足？

## Figures, Tables, Posters, Diagrams

- artifact 类型和最终媒介是什么：manuscript figure、statistical plot、workflow diagram、architecture diagram、table、poster、slide、webpage？
- 它必须让读者第一眼看懂的单一信息是什么？
- 哪些 source data/text 是权威？我能转换数据，还是只能重排/重绘？
- 输出格式需要 SVG、PDF、PNG、PPTX、HTML、LaTeX table、CSV，还是 editable source？
- 风格约束是什么：venue template、brand、colorblind-safe、grayscale print、journal aesthetics、existing project style？

## Security, Installation, Supply Chain

- 目标是 recommendation、pre-install audit、local install、global install，还是 modify before install？
- 允许权限是什么：read-only clone、本地写、shell、network、package install、credential、global config？
- 审计要假设 hostile intent，还是只报告确认漏洞？
- 安装范围是 project-local、Codex-local、user-global，还是 system-wide？
- secrets、private repo、browser session、SSH key、token 是否全部 out of scope？
- 哪些动作需要最终确认：copy files、run scripts、update dashboard、edit config、install dependencies？
- 是否允许删除、覆盖或迁移现有文件？如果允许，范围和回滚点是什么？

## Automation And External Side Effects

- 哪些外部系统可触碰：GitHub、email、calendar、social platform、cloud API、payment、publishing endpoint？
- workflow 运行一次、定时、还是只在人工确认后运行？
- 失败行为是什么：立即停止、best effort、限次 retry、只通知？
- audit trail 需要 logs、generated report、diff、artifact folder，还是 notification summary？
- 哪些动作执行前必须 final confirmation？
