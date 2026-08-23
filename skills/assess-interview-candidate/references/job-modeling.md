# 岗位建模方法

## 目的与边界

先建立岗位模型，再读取候选人证据。岗位模型描述“工作需要什么”，不得围绕某位候选人的强项倒推要求。职位名称只用于检索，相同名称可能对应不同产出、责任和级别。

岗位模型必须保持可审计：每项能力都要回溯到岗位产出或关键任务；缺少岗位专家确认时标记为 `provisional`，不得伪装成已确认事实。

## 建模顺序

按以下链条逐项建立模型：

```text
可观察工作产出 -> 关键任务 -> 能力 -> 目标熟练度 -> 可接受证据 -> 验证方法
```

1. 从岗位描述提取“动词 + 对象 + 情境/约束 + 产出”，避免直接把技能词当能力。
2. 区分核心产出、日常任务、入职即需具备、入职后可培养、加分项、工作环境与责任边界。
3. 用通用框架寻找遗漏项，再以当前组织的真实任务裁剪；框架不得覆盖本地岗位事实。
4. 对新兴岗位检索至少三个当前官方雇主岗位样本，并用至少两个政府、标准或官方技术来源校准。
5. 由招聘经理或岗位专家确认任务、级别和权重；未确认时显示未知或暂定。

## 能力分层

对每项能力分别记录 `importance`、`frequency`、`failure_impact`，不要把三者合并成一个模糊等级。

- `gate`：履职或风险控制所必需的门槛；不能被其他高分补偿。
- `critical`：决定核心产出的高权重能力。
- `supporting`：支持核心任务稳定完成的能力。
- `differentiator`：在满足核心要求后区分优秀表现的能力。

只有岗位专家确认且有直接任务依据的项目才能设为 `gate`。学历、年限、公司名气和职位头衔不能自动成为能力门槛。

## 最小记录字段

每个能力项至少包含：

```yaml
id: stable-id
name: 能力名称
outcomes: [对应产出]
tasks: [对应任务]
observable_behaviors: [可观察行为]
target_level: 目标级别及行为描述
tier: gate|critical|supporting|differentiator
importance: 1-5|unknown
frequency: 1-5|unknown
failure_impact: 1-5|unknown
entry_required: true|false|unknown
acceptable_evidence: [简历证据、作品、工作样本、面试行为]
preferred_assessment: [work_sample, structured_interview, verification]
sources: [source-id]
status: provisional|sme_confirmed
```

## 参考框架的使用方式

- 使用 [O*NET Content Model](https://www.onetcenter.org/content.html) 区分工作活动、任务、工作情境、技能、知识和工作风格。运行时检查[当前数据库版本](https://www.onetcenter.org/db_releases.html)，记录版本号和访问日期。
- 使用 [ESCO](https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/what-esco-and-how-use-it) 寻找职业与技能之间的“必要/可选”关系，避免把可选技能误写成硬门槛。
- 使用 [SFIA 9 责任级别](https://sfia-online.org/en/sfia-9/responsibilities) 校准自主性、影响范围、复杂度、知识和协作责任；只做映射，不大段复制受许可约束的内容。
- 使用 [OPM 岗位分析](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 确认评估内容与工作任务的联系。

## 质量门

完成岗位模型前逐项检查：

- 每项能力至少有一个具体任务或产出。
- 每项高权重能力都有可实施的验证方法。
- 工作样本与实际任务相似，且能在可用时间内完成。
- 要求没有被单一公司的特殊写法错误泛化。
- 新增能力同时满足：当前岗位需要、可观察、跨来源支持，或已由岗位专家确认。
- 未知信息保留为 `unknown`；不得用模型常识补成事实。

若缺少岗位描述且无法从用户材料确认核心产出，停止评分和面试生成，先请求补充岗位信息。
