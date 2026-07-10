<p align="center">
  <img src="assets/compass-logo.png" alt="COMPASS Skills logo" width="760">
</p>

<h1 align="center">司南 COMPASS</h1>

<p align="center">
  <a href="https://github.com/dongshuyan/compass-skills/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/dongshuyan/compass-skills?style=for-the-badge&logo=github"></a>
  <a href="https://github.com/dongshuyan/compass-skills/forks"><img alt="GitHub forks" src="https://img.shields.io/github/forks/dongshuyan/compass-skills?style=for-the-badge&logo=github"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/dongshuyan/compass-skills?style=for-the-badge"></a>
  <img alt="Status alpha" src="https://img.shields.io/badge/status-alpha-orange?style=for-the-badge">
  <a href="https://linux.do/"><img alt="Linux.do" src="https://img.shields.io/badge/Linux.do-open--source-F59E0B?style=for-the-badge"></a>
</p>

<p align="center">
  <a href="README.md">English</a>
</p>

**司南：个性化 AI 任务总控 Skills 系统**  
**COMPASS: Personal Alignment Skills OS for AI Agents**

> **推荐先读：[使用 & 开发自己的 Skill 生态教程](https://dongshuyan.com/compass-skills/skill-writing-tutorial.html)**
>
> 从使用 `SKILL.md` 到搭建本地 Skill 系统，讲清楚最小结构、渐进披露、复用审计、AI 生成草稿、真实链路提炼和迭代验证。

COMPASS 当前公开 7 个本地 skills：4 个运行时协作 skills、2 个 run-history skill 工程 skills，以及 1 个用于避免和去除学术论文 AI 语气的学术润色 skill。核心协作层围绕用户画像、任务图谱、AI 对话续接和需求对齐；`run-history` 双 skill 负责把真实运行经验沉淀成新 skill，或根据 session 证据推动已有 skill 受控自我进化；`academic-humanizer` 负责在不改变事实、证据强度和论证关系的前提下，使中英文学术文本呈现更自然、可信的作者声音。

当前公开版技能一览：

| Skill | 作用 |
| --- | --- |
| [`task-clarifier`](skills/task-clarifier/) | 在高成本、高歧义或高风险任务前，把目标、范围、证据、验收标准和风险边界对齐清楚。 |
| [`task-forest`](skills/task-forest/) | 在当前 repo 内维护任务森林 / DAG，记录长期目标、依赖、进度、偏差、todo 和历史。 |
| [`session-handoff-prompt`](skills/session-handoff-prompt/) | 把当前 AI 对话压缩成可直接贴给新 AI 对话的续接 prompt。 |
| [`user-profile-keeper`](skills/user-profile-keeper/) | 在本地维护可审计、可纠错、可撤回的协作画像。 |
| [`run-history-skill-builder`](skills/run-history-skill-builder/) | 把已经跑通或反复打磨过的真实流程，打包成新的可复用 skill 或可审查设计方案。 |
| [`run-history-skill-upgrader`](skills/run-history-skill-upgrader/) | 自动根据真实执行、遇到困难、解决困难、验证结果和用户反馈等 session 信息，为已有 skill 先产出升级方案，并把这个过程组织成最简单的 skill 受控自我进化闭环；只有在明确批准后才执行修改。 |
| [`academic-humanizer`](skills/academic-humanizer/) | 帮助撰写或修改中英文学术论文，去除公式化、空泛、机械重复和暴露生成过程的 AI 式表达，在保留事实、证据强度和论证逻辑的同时恢复自然的学术作者声音。 |

多 skill 仓库建议按需安装；`run-history` 双 skill 面向其他 skills 的设计和维护，`academic-humanizer` 面向学术论文撰写过程中 AI 语气的预防，以及已有学术文本中 AI 语气的去除。

## 快速理解

**场景 1：任务开始前，先避免做错。**
当需求模糊、成本高或有安全风险时，用 `$task-clarifier` 把模糊想法整理成可执行需求：目标、范围、证据、验收标准和风险边界都写清楚。它会先识别哪些决策必须由用户决定，只在关键分叉上提问或要求确认；可查事实由 agent 自己从材料中补足。

这个 skill 的验收标准：

1. 用户能说清自己的目标和约束。
2. agent 能复述可执行的范围和下一步。
3. 用户能确认 agent 的理解没有偏离。

<details>
<summary>查看箱包购买需求对齐示例</summary>

整理自一次真实终端测试，省略 model 和运行状态行。

### 第 1 轮：模糊请求

**用户**

> 我要买个旅行箱，你告诉我一下哪个最好？

**$task-clarifier**

先把“最好”拆成能决策的条件：

1. **主要用途** — 这个旅行箱主要用来做什么，使用频率怎样？
   - 选项：短途出差、度假旅游、长期出行、日常频繁使用，或补充自己的情况。
   - 建议：先确认主要场景，因为它决定轻便度、尺寸和耐用性的取舍。
2. **预算范围** — 旅行箱从几百到几千元，预算会直接限制品牌和功能。
   - 选项：500 元以内、500-1500 元、1500-3000 元、3000 元以上，或补充预算。
   - 建议：1000-2000 元通常能兼顾耐用性和轻便性。
3. **“最好”的含义** — 最在乎轻便、耐用、容量、价格、品牌/外观，还是别的？
   - 建议：根据场景选择；短途出差偏轻便，长期出行偏耐用。

**用户回答**

> 商务出差，预算 1000-1500 元，优先耐用。

### 第 2 轮：缩小产品类型

**$task-clarifier**

前面的回答已经确定方向，但还有两个选择会改变推荐：

1. **出差地点和尺寸** — 国内还是国际，箱子是否需要能上飞机？
   - 建议：如果有上飞机的可能，20 寸更灵活。
2. **箱子材质** — 硬壳还是软壳？
   - 建议：既然耐用优先，硬壳更符合需求。

**用户回答**

> 国际国内通用，28 寸；硬壳。

### 第 3 轮：发现矛盾并澄清

**$task-clarifier**

这里有一个矛盾：用户说主要用于短途出差（1-3 天），但又选择 28 寸大箱子。28 寸通常用于长期出行或一次装很多东西；短途出差一般 20-24 寸就够了。

1. **28 寸的真实原因** — 是出差时间更长、想一箱多用，还是只是想买大的备用？
   - 建议：如果是一箱多用，28 寸合理；如果只是 1-3 天短途，20-24 寸更轻便。
2. **其他功能要求** — 是否需要防盗拉链、可扩展隔层等？
   - 建议：耐用优先时，基础功能达标即可。

**用户回答**

> 一箱多用，基础功能就行。

### 确认后的需求

**$task-clarifier**

> 你需要一个 28 寸硬壳旅行箱，预算 1000-1500 元。主要用于短途出差，但偶尔需要装更多东西做长期出行，希望一箱多用。优先级是耐用性，基础功能满足即可，国内国际都能用。

**待确认推断**

- 轮子顺滑度和拉杆手感重要，因为出差会反复推拉。
- 用户想一次买到位，所以耐用性是核心评估标准。
- 知名品牌更合适，因为这个价位段的质量和售后更稳定。

确认后，agent 再给出 3-4 个具体产品推荐。

</details>

**场景 2：任务进行中和结束后，维护任务树 / 任务森林。**
用 `$task-forest` 把当前对话分解成各个任务，并把每个任务的目标、进度、偏差、依赖、待办和决策写成 proposal。确认后生成树视图、DAG 视图、任务详情卡和推荐队列，让下一个 agent 或新 AI 对话继续时知道“这件事为什么做、做到哪、下一步做什么”。

**场景 3：上下文变长时，生成新 AI 对话续接 prompt。**
用 `$session-handoff-prompt` 把当前这轮对话里真正需要延续的目标、进展、约束和下一步，压缩成一段可直接复制给新 AI 对话的提示词，让新对话像接着原来的对话继续做事。它可以结合显式 transcript、workspace 证据和 `$task-forest` 导出；它只读任务森林，不改任务图。

**场景 4：长期协作中，保存本地协作画像。**
用 `$user-profile-keeper` 在本地保存可审计、可纠错、可撤回的协作画像。画像只记录用户确认或低敏的协作信号；secret、token、密码、私钥和验证码不进入画像。`$task-clarifier` 可读取低敏摘要来调整提问方式；没有画像时，它依然按当前上下文工作。

**场景 5：把已经跑通的流程沉淀成新 skill。**
用 `$run-history-skill-builder` 从真实对话、日志、文件、截图、artifact 和浏览器流程中提炼不变量、状态门、验证门和资源拆分，生成新的可复用 skill，或先给一个不落文件的设计方案。

**场景 6：根据真实运行反馈推动已有 skill 受控自我进化。**
用 `$run-history-skill-upgrader` 自动读取目标 skill 在真实执行中暴露出的困难、解决过程、验证结果和用户反馈等 session 信息，先给出结构化升级方案并停下；只有你明确批准该具体方案后，它才会修改已有 skill 文件。换句话说，只要周期性运行某个需要进化的 skill，持续积累这些真实 session 证据，再把它们交给 upgrader，就能形成一个最简单的 skill 受控自我进化闭环。

**场景 7：避免或去除学术论文中的 AI 语气。**
用 `$academic-humanizer` 撰写、审计或最小修改中英文学术文本。它识别公式化、空泛、机械重复、无来源拔高和暴露生成过程的 AI 式表达，同时保护命题、数字、引文、证据强度、否定、因果关系、比较对象和范围。目标是恢复自然、可信、符合学术共同体习惯的作者声音，显著降低读者将文本判断为 AI 生成的可能性；它不承诺所有读者都会作出相同的作者身份判断。

`$task-forest` 导出的任务关系树和对话更新流程：

![task-forest tree demo](assets/task-forest-demo.gif)

这个 GIF 展示多次对话更新后，当前 repo 的任务森林逐步成型。

DAG 关系视图：

![task-forest live DAG view](assets/task-forest-live-dag.png)

任务详情、目的、要求、证据和调度建议：

![task-forest live detail view](assets/task-forest-live-detail.png)

用户画像与需求对齐的协作方式：

![司南用户画像与需求对齐流程](assets/profile-alignment-flow.zh.png)

## 为什么需要 COMPASS

长任务需要持续保存四类信息：

- **用户信息**：沟通偏好、风险边界、常见遗漏和长期协作方式。
- **任务全局**：当前动作属于哪个长期目标、依赖什么、推进到哪里。
- **目标关系**：当前任务和原始目的之间的贡献关系，以及是否出现偏移。
- **续接上下文**：新 AI 对话需要知道什么，才能不重放完整聊天记录也能继续推进。

COMPASS 提供一套长期协作和 skill 演进流程：先读取用户协作画像，再查看任务森林，需要换 AI 对话时生成续接 prompt，在行动前完成目标对齐；当某条流程已经跑通、值得沉淀，或某个现有 skill 需要根据真实 session 证据受控自我进化时，再进入 `run-history` 双 skill。

## 四层协作模型 + 三个扩展 skills

| 层 | Skill | 解决的问题 |
| --- | --- | --- |
| **知人** | [`$user-profile-keeper`](skills/user-profile-keeper/) | 本地维护可审计、可纠错、可撤回的用户画像，让 agent 了解用户偏好、风险确认方式和协作边界。 |
| **知事** | [`$task-forest`](skills/task-forest/) | 在 repo 内维护任务森林 / DAG，记录长期目标、子任务、依赖、进度、偏差、todo 和历史快照。 |
| **知续** | [`$session-handoff-prompt`](skills/session-handoff-prompt/) | 把当前对话里真正需要延续的目标、进展、约束和下一步，压缩成可直接复制给新 AI 对话的提示词。 |
| **知向** | [`$task-clarifier`](skills/task-clarifier/) | 把模糊需求对齐成三方一致的执行契约：用户想清楚、agent 听准确、用户能确认没跑偏。 |
| **造技** | [`$run-history-skill-builder`](skills/run-history-skill-builder/) | 把已经跑通或反复打磨过的真实流程，抽成新的可复用 skill 包，或先生成不落文件的设计方案。 |
| **修技** | [`$run-history-skill-upgrader`](skills/run-history-skill-upgrader/) | 自动根据真实执行、遇到困难、解决困难、验证结果和用户反馈等 session 信息，为已有 skill 先产出结构化升级方案，并把这个过程组织成最简单的 skill 受控自我进化闭环；只有在明确批准后才执行修改。 |
| **润文** | [`$academic-humanizer`](skills/academic-humanizer/) | 在保留事实、证据强度、逻辑关系和学术语域的前提下，避免或去除中英文学术论文中的 AI 语气，恢复自然的学术作者声音。 |

一句话理解：

```text
$user-profile-keeper 让 AI 知道“你是谁、怎么协作”。
$task-forest 让 AI 知道“任务在哪里、做到哪里、为什么做，以及有没有偏离总的目标”。
$session-handoff-prompt 让 AI 知道“新对话怎样像接着原来的对话继续做事”。
$task-clarifier 让 AI 知道“用户的需求到底是什么”。
$run-history-skill-builder 让 AI 知道“这条已经跑通的流程怎样被沉淀成新的 skill”。
$run-history-skill-upgrader 让 AI 知道“现有 skill 怎样根据真实 session 证据受控自我进化”。
$academic-humanizer 让 AI 知道“怎样在不改变学术命题的前提下避免或去除 AI 语气”。
```

## 生态图

![司南 COMPASS 技能生态 DAG](assets/compass-system-map.zh.svg)

## 安装和 Agent 兼容

这些 skills 使用 Python 标准库和 Markdown 文档，不依赖云服务，不上传用户数据。脚本按本地文件工作，已按 macOS、Windows、Linux 三类环境做路径约束：

- macOS / Linux：示例命令使用 `python3`。
- Windows：可使用 `py -3` 或 `python`。
- `$task-forest` 数据默认保存在当前 workspace 的 `.agent-workbench/task-forest/`。
- `$user-profile-keeper` 数据默认保存在用户目录下的 `.compass-skills/user-profiles/v1`，可用 `COMPASS_USER_PROFILE_HOME` 改到其他本地目录。
- 所有正式写入都在本地文件或本地 SQLite 内完成；没有网络上传、浏览器 cookie 读取、credential 读取或远程写入。

COMPASS 是一个 agent-agnostic 的 `SKILL.md` skills 包：凡是支持 `SKILL.md`、YAML frontmatter、Markdown instructions、可选 `scripts/` / `references/` 的 agent，都可以原生或近原生使用；暂不原生支持 skills 的 agent，可以通过根目录 [AGENTS.md](AGENTS.md) 做轻量适配。

| Agent / 环境 | 推荐接入方式 |
| --- | --- |
| Codex | 复制 `skills/` 下需要的 released skill 目录到 Codex 可发现的 skills 目录，或作为 repo-local skills 使用；当前公开版共 7 个 skills。 |
| Claude Code | 复制 `skills/` 下需要的 released skill 目录到 Claude Code 的 custom skills 目录，或放入项目 skills 根目录；当前公开版共 7 个 skills。 |
| OpenClaw | 放入 workspace `skills/`、`.agents/skills` 或个人/托管 skills 目录；按 OpenClaw 的 skill precedence 生效。 |
| OpenCode | 保留本 repo 的 `skills/` 和 [AGENTS.md](AGENTS.md)，让 agent 通过 AGENTS 规则发现并读取对应 `SKILL.md`。 |
| 其他 agent | 只要能读取文件并运行本地脚本，就按 [AGENTS.md](AGENTS.md) 的通用协议加载：先读 `SKILL.md`，再按需读 `references/` 和运行 `scripts/`。 |

**Agent-assisted 安装 prompt**

把下面这段发给你正在使用的 AI agent。它应该先审查安全边界，再按当前 agent / harness 的真实安装路径复制 released skills；如果无法确定安装路径，只输出安装计划，不要猜路径写入。

```text
请安全安装 COMPASS Skills：

Repo: https://github.com/dongshuyan/compass-skills

目标：在确认安全性的前提下，安装这个 repo 里 `skills/` 下的全部 released skills。

要求：
1. 先读取并审查 README、SECURITY、AGENTS.md、每个 `skills/*/SKILL.md`、相关 `references/` 和 `scripts/`。
2. 确认没有上传用户数据、读取 credential / token / cookie、远程写入、全局配置修改或危险命令。
3. 识别当前 agent / harness 的本地 skills 目录和加载规则；如果无法可靠识别，只给安装计划，不要写入。
4. 只复制 `skills/` 下的 released skill 目录；不要复制 `.git`、运行缓存、用户画像、任务图、原始截图或本地环境文件。
5. 安装后运行可用的本地验证，例如 Python 编译检查和 `$task-forest` 导出回归；如果某项无法运行，说明原因和剩余风险。
6. 最后报告安装位置、已安装 skills、安全检查结果、验证结果，以及如何在 AI 对话中调用。
```

手动安装时，把 `skills/` 下需要的 released skill 目录复制到目标 agent 的本地 skills 目录；当前公开版共 7 个 skills。安装后可在 AI 对话中点名使用：

```text
$user-profile-keeper
$task-forest
$session-handoff-prompt
$task-clarifier
$run-history-skill-builder
$run-history-skill-upgrader
$academic-humanizer
```

## 四个核心协作 skills

### $user-profile-keeper：本地用户画像

`$user-profile-keeper` 维护一个只保存在本机的用户画像。画像记录协作偏好、澄清方式、风险边界、能力边界和常见遗漏；secret、token、密码、私钥和验证码不得写入。`$task-clarifier` 只能读取低敏 `clarification_summary`，用于调整提问方式；没有画像时它也能正常工作。

**重要提醒：** `$user-profile-keeper` 是本地明文存储，没有经过任何加密处理。本系列 skills 的规则禁止上传、窃取或读取 credential；本地文件仍可能被同一台机器上的其他进程、备份系统或有权限的用户读取。请在充分理解风险后再使用，不要保存 secret、token、密码、私钥、验证码或高度敏感信息。

**首次构建画像 prompt**

```text
请用 $user-profile-keeper 初始化我的本地用户画像。

目标：通过本地问卷或当前上下文，建立一个可审计、可纠错、可撤回的用户画像。
边界：
1. 只保存到本机，不上传，不读取浏览器 cookie、token 或 credential。
2. 年龄、教育、职业、长期目标等 private 信息先进入待确认 proposal。
3. 不要把本次任务规则误当成长期画像。
4. 完成后告诉我：已写入哪些低敏信息，哪些进入 pending proposal，哪些被跳过。
```

**任意对话更新画像 prompt**

```text
请用 $user-profile-keeper 从当前对话更新我的本地用户画像。

请只提取对长期协作有价值的信息，例如沟通偏好、风险确认方式、常见遗漏、能力边界和隐私边界。
低敏、明确、无冲突的信息可以直接应用；推断性、private、敏感或冲突信息必须进入 proposal 等我确认。
不要保存 secret、token、密码、私钥、验证码或浏览器 session 信息。
```

### $task-forest：任务森林和进度总控

`$task-forest` 在当前 repo 内维护任务森林 / DAG，负责记录长期目标、子任务、依赖、进度、偏差、待办、决策和对话历史。导出的 HTML 可以离线查看树视图、DAG 视图、历史变化和待复核节点。

**构建或更新任务森林 prompt**

```text
请用 $task-forest 分析当前对话，并维护当前 workspace 的任务森林。

目标：把本轮对话中有长期价值的目标、任务、进度、偏差、风险、决策和 follow-up 写成 `$task-forest` proposal。
要求：
1. 先读取当前 `$task-forest` 的 list 和 todo；如果不存在就初始化。
2. 判断本轮工作服务哪个长期目标；找不到关系时不要硬挂，先问我或生成 question/risk。
3. 如果发现某个任务无法达成用户真实目的，记录偏差或提出替代方案。
4. 只保存 proposal，展示准备改什么；等我确认后再 apply。
5. apply 后运行 validate 和 export，并给出 HTML 路径。
```

### $session-handoff-prompt：新 AI 对话续接 prompt

`$session-handoff-prompt` 负责把当前对话里真正需要延续的目标、进展、约束和下一步，压缩成一段可直接复制给新 AI 对话的提示词，让新对话像接着原来的对话继续做事。它优先使用当前对话、用户明确提供的 transcript 或 log、当前 workspace 证据和 `$task-forest` 导出；默认输出 balanced 模式，也可以生成 minimal 或 full。

它有两个隐私模式：

- `privacy=local`：用于同一台机器的新 AI 对话，可以保留真实 workspace 路径，方便继续工作。
- `privacy=shareable`：用于公开分享、issue、外部交接或截图，会脱敏本地路径和 credential-like 字符串。

**生成续接 prompt**

```text
请用 $session-handoff-prompt 为当前对话生成一个 balanced 的新 AI 对话续接 prompt。

目标：让新 AI 对话不需要重放完整 transcript，也能继续当前任务。
要求：
1. 使用当前对话、我明确给出的文件、当前 workspace 证据，以及存在的 task-forest exports。
2. 只读 task-forest；不要保存 proposal，不要修改任务图。
3. prompt 使用我的语言；未知时默认中文。
4. 本机续接使用 privacy=local；如果我要公开分享，再改成 privacy=shareable 并先脱敏校验。
5. 先给可复制 prompt，再简短说明模式、来源和限制。
```

**代表性输出形态**

```text
你正在接手一个已经进行过多轮的 AI 对话。请按以下上下文恢复任务状态；如果当前文件或可验证证据与这里冲突，以当前证据为准。

【工作目录】
<workspace>

【用户目标】
把 session-handoff-prompt 作为 COMPASS 的正式 skill 接入，支持 macOS、Linux、Windows 和主流 agent。

【必须遵守的要求】
- [已验证] 内部说明用英文；交互和输出使用用户语言，默认中文。
- [已验证] 不读取 credential、cookie、浏览器 session 或无关私有日志。

【下一步】
1. 更新 README 和 manifest。
2. 运行 smoke test 和安全扫描。
3. 报告验证结果和剩余风险。
```

### $task-clarifier：需求对齐和风险门禁

`$task-clarifier` 是低打扰但强对齐的需求对齐入口。它把模糊想法对齐成三方一致的可执行需求：用户想清楚，agent 听准确，用户也能确认 agent 没理解偏。它会先识别哪些决策必须由用户决定，问 1-3 个带推荐答案的关键问题，确认共享理解后再搜索或执行。

如果安装了 `$user-profile-keeper`，`$task-clarifier` 可以读取低敏画像摘要，让提问方式更符合用户习惯；如果没有，它仍会根据当前上下文、文件和证据正常工作。

**通用使用 prompt**

```text
请用 $task-clarifier 对齐下面这个任务。

任务：...
材料：...
约束：用户拥有的决策先问我；能从文件、上下文或可靠来源判断的事实不要让我重复提供；只问会改变范围、方法、证据、格式、安全或验收的问题。
输出：先给 1-3 个关键问题和推荐答案；核心需求清楚后，用 2-5 行复述你的理解并让我确认。
```

## 能做什么

- 新 AI 对话结束时，把进度、偏差、决策和待办归入全局任务图。（用户可以自行做成 hook）
- 上下文变长或需要切换 agent 时，生成可复制续接 prompt，让新 AI 对话带着目标、证据、状态和下一步继续。
- 当一个新任务找不到父节点或贡献关系时，也就是不知道当前对话为什么要做时，提醒用户重新确认目标，确保当前对话符合全局目标、不偏离。
- 在任务变复杂、变危险、变模糊时，先进入 alignment gate，避免返工和隐私风险。
- 让用户画像影响“怎么问”，当前上下文始终优先，历史偏好只作为参考。
- 在不增加事实、引文或作者经历的前提下，避免或去除中英文学术论文中的 AI 语气，并保护原有论证强度。
- 为后续日报、周报、任务排序、习惯系统、多 agent 总控和 skill 升级提供结构化数据。

## 验证状态

本地发布包已运行代表性验证：

- `python3 skills/session-handoff-prompt/scripts/smoke_test_handoff.py --skill-dir skills/session-handoff-prompt`：验证 Codex compacted 事件投影、task-forest 只读摘要、本机 handoff 校验和 shareable 脱敏。
- `printf '%s\n' '本研究采用分层抽样。' | python3 skills/academic-humanizer/scripts/metrics.py - --json`：只读检查语言路由、过程残留和对立句式候选，不输出作者身份概率或质量分数。
- `python3 -m py_compile ...`：验证新增 Python 脚本语法。
- `skills.sh.json` 和 `evals/trigger-and-quality-cases.json` 已通过 JSON 解析。

## 安全和隐私

COMPASS 的默认安全边界：

- 不联网、不上传用户画像、不读取浏览器 cookie、token 或 credential。
- `$user-profile-keeper` 默认是本地明文存储；它的边界是本地保存、可审计、可删除。它没有加密防护层，用户需要自行判断是否安装使用。
- 不把完整用户画像提供给普通 skill；只允许读取低敏 `clarification_summary`。
- `$task-forest` 的完整任务图保存在 repo-local 目录，不把节点正文写入全局 registry。
- `$session-handoff-prompt` 默认只读；本机续接可以保留路径，公开分享前必须使用 shareable 脱敏和校验。
- `$academic-humanizer` 不增加事实、引文、机制或作者经历；可选指标脚本只读输入并输出描述性候选。
- 删除、覆盖、发布、远程写入、credential、全局配置等高风险动作必须确认。
- HTML 导出是静态离线文件，不直接修改任务图。

更多检查见 [SECURITY.md](SECURITY.md)。

## Roadmap

![司南 COMPASS Roadmap 技能生态](assets/compass-roadmap-ecosystem.zh.png)

即将开源 / 计划接入：

- 本机代理控制室：汇总多个本地 agent 的运行、等待、卡住、风险和待 review 状态。
- 等待间隙任务路由：根据等待时间、精力、切换成本和 `$task-forest` todo 推荐可处理的小任务。
- 日报 / 周报 / 项目复盘：基于用户画像和任务森林生成更贴合用户目标的报告。
- 任务排序和 deadline planning：结合任务重量、用户能力、上下文切换成本和 deadline 推荐执行顺序。
- 健康习惯和节奏系统：用任务森林观察长期负载，帮助用户安排更可持续的工作节奏。

## 开源许可证

本项目使用 MIT License，见 [LICENSE](LICENSE)。

## 社区讨论

- 当前 repo 已经分享开源至 [Linux.do](https://linux.do/)。

## Star 趋势

[![Star History Chart](https://api.star-history.com/svg?repos=dongshuyan/compass-skills&type=Date)](https://www.star-history.com/#dongshuyan/compass-skills&Date)
