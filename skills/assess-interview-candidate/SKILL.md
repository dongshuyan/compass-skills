---
name: assess-interview-candidate
description: >-
  根据候选人简历与岗位要求生成可审计的后台评估、简明的候选人介绍、按岗位重要性排列的简历疑点、12–18 道可直接照读的面试题，以及支持重点标记和本机保存的离线 HTML。用于招聘方准备结构化面试、核验岗位能力和记录回答。不要用于求职者模拟面试、私人背景调查、心理或人格诊断、从敏感属性推断表现，或自动录用、淘汰、排序候选人。
---

# 候选人评估与面试报告

## 目标

把简历和岗位要求整理成两层材料：

1. 后台保留完整岗位模型、证据账本、来源、假设和评分数据，便于复核。
2. 给面试官的 HTML 只保留“候选人简介、简历疑点与水分排查、面试提问”三个模块，使用通俗中文。

始终区分候选人明确提供的事实、外部佐证、推断和未知。最终招聘决定由具备权限的人作出。

## 可移植运行约定

本 Skill 不依赖某个特定 Agent、Skill 安装根目录或命令行外壳。任何能够读取本地文件并运行 Python 3.10 及以上版本的 Agent 都可以使用；PDF 处理、联网核验和浏览器检查按当前宿主实际具备的能力执行。

- 先把 `<skill-dir>` 解析为本 `SKILL.md` 所在目录，不猜测固定安装路径。
- `<python>` 表示当前系统可用的 Python 3 启动方式。Windows 通常使用 `py -3` 或 `python`，macOS 与 Linux 通常使用 `python3` 或 `python`；先用版本命令确认实际可用项。
- `<approved-root>`、`<output-dir>` 等是路径占位符，不代表固定路径分隔符。通过宿主文件 API 或 `pathlib` 组合路径，并把含空格或非 ASCII 字符的路径作为一个完整参数传入。
- 命令示例使用单行、外壳无关的参数形式。不要依赖 Bash 续行符、环境变量展开、当前用户主目录结构或某个 Agent 的专用工具名。
- `agents/` 中的文件只是特定宿主可选的界面元数据；核心工作流以本文件、`references/`、`scripts/`、`assets/` 和 `evals/` 为准。

遇到能力差异时按 [agent-portability.md](references/agent-portability.md) 处理。缺少必要能力时明确报告未完成的核验，不得把未执行的步骤写成已完成。

## 结果契约

每次完整运行在新的案件目录中生成：

```text
input/       原始简历、岗位要求和用户提供的链接
normalized/  经文字提取与视觉核对的文本及案件清单
research/    查询和来源记录
models/      岗位模型、证据账本、行为假设和面试蓝图
interview/   初始评分状态
output/      完整后台数据、精简报告数据和离线 HTML
audit/       运行、校验和隐私排除记录
```

关键输出：

```text
output/assessment-data.json
output/interviewer-report-data.json
output/<候选人姓名>-候选人评估与面试报告.html
```

HTML 文件名、浏览器标题和页面最上方标题都必须包含候选人姓名。不要覆盖既有案件或报告。

## 开始前读取

先把 `<skill-dir>` 解析为本文件所在目录。

1. 每次读取 [workflow-contract.md](references/workflow-contract.md)、[evidence-and-inference-policy.md](references/evidence-and-inference-policy.md) 和 [privacy-and-fairness-cn.md](references/privacy-and-fairness-cn.md)。
2. 建立岗位模型前读取 [job-modeling.md](references/job-modeling.md)。
3. 联网核验候选人职业证据前读取 [research-and-identity-policy.md](references/research-and-identity-policy.md)。
4. 生成题目时读取 [structured-interview-methods.md](references/structured-interview-methods.md) 和 [scoring-and-coverage.md](references/scoring-and-coverage.md)。
5. AI、LLM、Agent 或工程岗位读取 [role-adapter-ai-llm-engineering.md](references/role-adapter-ai-llm-engineering.md)。
6. 写 JSON 前读取对应 Schema；面试官报告必须读取 [schema-interviewer-report.json](references/schema-interviewer-report.json)。

## 输入门

必需输入：

- 可读取的候选人简历；
- 岗位要求或招聘方确认的实际任务；
- 输出根目录，未提供时使用当前目录下的 `candidate-cases/`。

尽可能取得：

- 公司工作地点、岗位级别、现场办公和出差要求；
- 候选人主动提供的职业链接；
- 候选人职业信息联网核验的允许范围；
- 岗位专家确认的能力权重和门槛。

缺少简历或岗位要求时以 `REQUIRED_INPUT_MISSING` 停止，不创建案件。缺少公司地点时继续生成，但写明“距离无法计算，待补充公司地址”。缺少候选人联网核验权限时关闭该分支，不影响本地简历分析。

## 工作流

### 1. 创建案件并完整读取材料

```text
<python> "<skill-dir>/scripts/create_candidate_case.py" --root "<approved-root>" --role-slug "<role-slug>"
```

复制原始输入并记录哈希，不移动或删除用户文件。PDF 必须同时使用当前宿主可用的文字提取能力和逐页视觉检查能力，核对页数、姓名、时间线、表格、图片文字及提取遗漏。为保证完整核对，原件和逐页提取文本可能保留电话、邮箱、证件号或精确住址，因此 `input/` 与 `normalized/` 都按受限候选人资料处理；这些内容不得进入联网查询、面试官数据或 HTML。若无法完成逐页视觉检查，以 `PDF_VISUAL_CHECK_UNAVAILABLE` 停止生成最终报告，并说明缺少的能力。

### 2. 建立当前岗位模型

按“工作产出 → 关键任务 → 能力 → 目标熟练度 → 可接受证据 → 验证方法”拆解岗位。记录重要性、频率、失败影响和是否入职即需具备。缺少招聘方确认时标为暂定，不把学历、年限或公司名气自动当作能力。

对快速变化岗位进行不含候选人身份信息的当前岗位研究；优先官方招聘页、一手技术资料、标准和职业框架。

### 3. 建立简历证据账本

逐条拆分与岗位重要能力有关的声明，记录原文位置、情境、任务、本人行动、结果、个人贡献边界、可验证材料和剩余缺口。简历没有写某项能力只表示“当前证据不足”，不能直接写成“不具备”。

疑点使用“描述不清”“可核验缺口”等中性语言。优先检查：

- 只写“参与”但没有本人分工；
- 完成功能但没说明自主设计、改造开源方案还是简单调用；
- 提到增长、准确率或降本，但没有基线、时间范围和计算口径；
- 团队、论文或平台结果与个人贡献边界不清；
- 岗位关键能力只有技能名词，没有可运行产物或验证过程。

### 4. 可选的公开职业证据核验

仅研究获得允许、公开可访问、身份确认且与岗位直接相关的职业资料。系统发现的页面至少需要两个一致职业锚点；同名不足以确认身份。不得搜索年龄、籍贯、婚姻、家庭或私人生活。没有公开主页、论文或代码仓库不得扣分。

### 5. 保留完整后台审计

继续生成岗位模型、证据账本、候选人视角、九类岗位行为假设、面试蓝图、评分状态、来源记录和 `output/assessment-data.json`。这些对象供审计与人工复核，不直接展示在面试官 HTML 中。

### 6. 生成精简面试官数据

按 [schema-interviewer-report.json](references/schema-interviewer-report.json) 生成 `output/interviewer-report-data.json`。

#### 候选人简介

- 姓名必须使用候选人材料中的明确姓名。
- 年龄、出生信息、出生地、老家或籍贯、婚姻状况、现居城市只使用候选人主动提供的材料；没有就显示“未提供”，不得搜索或推测。
- 有出生日期时按报告日期计算准确周岁；有出生年月或出生年份时计算近似年龄并标“约”。同时保存原始出生信息、规范日期、换算截止日和来源位置。
- 候选人已经明确提供的学校、学历、专业、工作单位、职位、时间和城市应直接汇总；某个城市没写就显示“未提供”，不根据学校或单位地址推测。
- 年龄、籍贯和婚姻状况不进入人岗匹配、能力评分或稳定性预测。
- 人岗匹配只用“符合”“有相关基础，需面试确认”“当前证据不足”。
- 单列现居地、公司地点、实际通勤、搬迁意愿、现场办公、出差和最早到岗问题。出生地或老家不能代替现居地计算距离。

#### 简历疑点与水分排查

只列与岗位核心能力直接相关的 0–8 项，按能力重要性降序。每项写清：对应能力、简历原话、哪里说不清、为什么要核实、怎么核实。不要在可见文案中输出内部状态码、能力编号或英文评估术语。

#### 面试提问

生成 12–18 道按优先级排列的问题。问题必须能让面试官直接照读。每道岗位题提供提问目的、回答好/一般/差的具体表现、加分点和减分点。

题库必须包含：

- 共同核心专业题和至少一个真实工作样本；
- 与本候选人核心简历声明对应的核验题；
- 表达沟通、协作责任、危机处理或压力情境题；
- 现居地、通勤/搬迁、到岗和现场工作安排；这些题只记录双方条件，不评分；
- 一道可选择不问的婚姻状况问题。该题只记录候选人自愿回答，不设好坏、不加分、不扣分；候选人可以不回答。

### 7. 生成离线 HTML

HTML 只嵌入 `interviewer-report-data.json`，不嵌入完整 `assessment-data.json`。页面恰好包含三个主模块：

1. 候选人简介；
2. 简历疑点与水分排查；
3. 面试提问。

每道题支持：单击“标记”默认设为黄色“可能要问”；下拉改为红色“一定要问”、蓝色“备选”或取消；记录“好/一般/差/未问”及备注。地点、到岗和其他自述类问题只记录“已记录/不便回答/未问”。重点标记和回答自动保存到当前浏览器本机，并可导出或清空。不得发送网络请求、加载外部资源或保存候选人资料到远程服务。

页面不显示简历证据分、综合分、权重、覆盖率、门槛、可比性、来源表、九类行为假设或内部英文状态。这些信息继续留在后台文件。

使用：

```text
<python> "<skill-dir>/scripts/validate_interviewer_report_data.py" "<interviewer-report-data.json>"
<python> "<skill-dir>/scripts/render_candidate_report.py" --data "<interviewer-report-data.json>" --output "<candidate-report-file>"
<python> "<skill-dir>/scripts/validate_candidate_report.py" "<candidate-report-file>"
```

渲染器会拒绝文件名不含候选人姓名的输出。

### 8. 校验和交付

继续校验后台对象：

```text
<python> "<skill-dir>/scripts/validate_case_contract.py" --job-model "<job-model.json>" --sources "<sources.json>" --evidence-ledger "<evidence-ledger.json>" --blueprint "<interview-blueprint.json>" --score-state "<score-state.json>" --assessment-data "<assessment-data.json>"
<python> "<skill-dir>/scripts/validate_source_log.py" "<sources.json>"
<python> "<skill-dir>/scripts/validate_evidence_ledger.py" "<evidence-ledger.json>"
<python> "<skill-dir>/scripts/calculate_interview_score.py" --blueprint "<interview-blueprint.json>" --state "<score-state.json>"
```

将命令、时间、退出码、错误和警告写入 `audit/validation.json`。交付时说明案件目录、HTML 文件、采用与拒绝的来源数量、关键未知项、校验结果和仍需人工确认的内容。

## 停止条件

- `REQUIRED_INPUT_MISSING`：缺少简历或岗位要求；
- `PDF_VISUAL_CHECK_UNAVAILABLE`：当前宿主无法完成 PDF 逐页视觉核对；
- `AUTHORITY_UNCONFIRMED`：无法确认有权处理简历；
- `IDENTITY_UNRESOLVED`：候选人职业页面身份不能确认；
- `PRIVATE_ACCESS_REQUIRED`：需要登录私人账号或绕过权限；
- `SENSITIVE_DATA_HIT`：联网结果出现不应处理的私人或敏感内容；
- `CONTACT_DETAIL_LEAK`：面试官数据或 HTML 中出现邮箱、手机号、证件号或其他不应展示的联系方式；
- `JOB_RELEVANCE_MISSING`：信息无法映射到岗位任务；
- `AUTOMATED_ADVERSE_ACTION`：要求自动拒绝、排序或触发不利决定；
- `HUMAN_REVIEW_MISSING`：拟把未经人工确认的结果用于招聘决定。

停止一个联网分支不妨碍继续处理获准的本地材料。

## 完成检查

- PDF 已通过文字提取和逐页视觉检查。
- 后台岗位、证据、来源、蓝图和评分对象可互相追溯。
- HTML 文件名、浏览器标题和页面主标题都包含候选人姓名。
- HTML 只有三个主模块，问题数为 12–18。
- 面试官数据和 HTML 不含邮箱、手机号、证件号或精确住址。
- 候选人已明确提供的学校、工作单位和城市已汇总；缺失项没有被推测。
- 出生信息存在时年龄已按报告日期换算；不存在时显示“未提供”。
- 年龄、籍贯和婚姻没有进入岗位匹配或评分。
- 简历疑点按岗位重要性排序，使用中性、通俗中文。
- 问题可直接照读，判断参考和加减分标准具体。
- 重点标记、回答、备注、本机恢复、导出和清空均可用。
- 页面离线可用、无外部资源、文本安全转义、移动端可读。
- 最终输出不含自动录用、淘汰、排序、人格诊断或虚假确定性。
