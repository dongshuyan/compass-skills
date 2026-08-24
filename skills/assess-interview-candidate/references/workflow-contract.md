# 候选人评估工作流与双层输出契约

## 用途与边界

本工作流把简历、岗位要求、公开职业证据和结构化面试组织成两层材料：

- 后台审计层：完整保存岗位模型、证据、来源、假设、蓝图和评分数据。
- 面试官视图层：只展示面试现场需要的候选人简介、核心简历疑点和面试问题。

只评价与岗位任务直接相关、可观察和可验证的行为与产出。不从姓名、照片、声音、表情、口音、年龄、性别、民族、宗教、婚姻、健康、残障、籍贯、家庭或私人生活推断能力、人格、稳定性或文化适配。不自动录用、淘汰或排序候选人。

## 案件目录

```text
<approved-case-root>/<local-date>-<role-slug>-<random-id>/
  input/
  normalized/
  research/
  models/
  interview/
  output/
  audit/
```

推荐文件：

```text
input/resume-original.*
input/job-description-original.*
input/supplied-links.json
input/consent-and-scope.yaml
normalized/resume.md
normalized/job-description.md
normalized/case-manifest.json
research/queries.jsonl
research/sources.json
models/job-model.json
models/evidence-ledger.json
models/interview-blueprint.json
interview/score-state.json
output/assessment-data.json
output/interviewer-report-data.json
output/<候选人姓名>-候选人评估与面试报告.html
audit/run-manifest.json
audit/validation.json
audit/privacy-log.json
```

案件目录使用随机编号，不含候选人姓名；最终 HTML 文件名必须包含候选人姓名，方便招聘方同时处理多人报告。

## 处理阶段

### 0. 范围与权限

记录处理目的、岗位、允许的数据源、候选人职业信息核验状态、人工责任人和公司工作地点。候选人职业信息核验与通用岗位研究分开。

### 1. 输入标准化

保留原件并记录哈希。PDF 简历复制为案件内固定受限文件 `input/resume-original.pdf`，案件清单另存原始文件名和哈希。PDF 同时做文字提取和逐页视觉检查，生成带页码或段落定位的文本。无法可靠读取的部分标记提取不确定，不猜测。原件和完整提取文本属于受限候选人资料，可能保留联系方式；联系方式不得进入查询、研究记录、面试官数据或 HTML。

逐页视觉检查还要记录候选人头像状态。若页面存在清晰的候选人头像，先检查 PDF 嵌入图片，再按需要裁切页面；所有提取结果都转换为 PNG，并在转换后重新与原页面视觉比对。只有最终 PNG 与原页面一致时才可标为 `included`。无头像、无法确认是候选人本人、可见但无法可靠提取时分别标为 `not_present`、`ambiguous`、`extraction_unavailable`。不得从 PDF 之外补图，也不得做生物识别或外貌推断。

候选人已明确提供的姓名、出生信息、出生地、籍贯或老家、婚姻状况、现居城市、学校、学历、专业、工作单位、职位、任职时间和明确城市可以进入面试官视图。没有提供的字段显示“未提供”。

### 2. 当前岗位研究

先用不含候选人身份信息的查询研究岗位，形成：

```text
工作产出 -> 关键任务 -> 能力 -> 目标熟练度 -> 可接受证据 -> 验证方法
```

分别记录重要性、频率、失败影响和入职门槛。权重在岗位专家确认前标为暂定。

### 3. 简历证据整理

把关键声明转换为情境、任务、本人行动、结果、个人贡献边界和验证方式。保留原文位置、来源状态、替代解释和核验问题。简历缺失表示当前材料没有证据，不等于候选人不具备能力。

### 4. 公开职业证据核验

只使用范围获准、公开可访问、身份确认且与岗位直接相关的职业页面。系统发现页面至少需要两个一致职业锚点。无法确认身份时记为 `identity_unresolved`，不摘录、不归因、不评分。

联网查询不得查找或补充年龄、出生地、籍贯、婚姻、家庭、健康、财务、政治、宗教、精确住址或私人社交内容。相关字段只能来自候选人主动提交的材料。

### 5. 后台岗位—证据映射

为关键能力形成正面材料、反面材料、缺口、替代解释和中性核验问题。文本是否读对、是否映射岗位、声明是否被佐证、材料是否支持能力判断分别记录。

### 6. 后台行为假设

后台可以保存专业能力、职业伦理、沟通、协作、事业投入条件、责任、薪酬取舍、候选人优先事项和压力情境等岗位行为假设。每项至少保留一个善意替代解释和可推翻条件。不得形成确定性人格诊断，也不得在主 HTML 中逐项展示。

### 7. 面试蓝图

同一岗位与级别使用相同的共同核心题、顺序、时间、允许追问和行为判断参考。首轮集中观察 3–4 项最高优先级能力，并准备 12–18 道可供面试官选择的问题。

共同核心专业题和工作样本可以计分；个性化简历核验、到岗安排以及婚姻状况等候选人自述题默认不计分。

### 8. 后台审计对象

四个稳定对象由既有 Schema 约束：

- `schema-job-model.json`
- `schema-evidence-ledger.json`
- `schema-interview-blueprint.json`
- `schema-source-record.json`

对象使用稳定的 `case_id`、`capability_id`、`evidence_id`、`source_id`、`question_id` 和 `section_id`。生成报告前检查唯一性和跨对象引用。

`output/assessment-data.json` 保留：

- 完整岗位模型；
- 简历证据项；
- 候选人视角；
- 九类岗位行为假设；
- 面试蓝图和初始评分状态；
- 来源记录和限制。

此文件不嵌入面试官 HTML。

### 9. 面试官视图对象

`output/interviewer-report-data.json` 必须通过 `schema-interviewer-report.json`。新生成报告使用 `schema_version=1.1.0`；校验器继续接受不含新增字段的既有 `1.0.0` 报告，避免为本次升级重写旧工件。`1.0.0` 不能携带 `candidate_photo` 或 `timeline_age_estimate`，防止通过降低版本号跳过新增校验。对象只包含：

```text
case
candidate_overview
resume_risks
interview_questions
footer_note
```

#### 候选人简介

`candidate_overview.personal_info` 对出生信息、年龄、出生地、老家或籍贯、婚姻状况、现居城市使用统一来源状态：

- `candidate_provided`：候选人主动材料中明确出现，并保留 `source_locator`；
- `not_provided`：值固定为“未提供”，来源位置为 `null`。

不允许“根据学校推测籍贯”“根据单位地址推测现居地”等第三种来源状态。

`candidate_overview.candidate_photo` 和 `candidate_overview.timeline_age_estimate` 是 `personal_info` 的同级对象。前者是简历 PDF 展示工件，后者是显式推算；两者都不能伪装成候选人自述事实。

`candidate_photo` 使用四种状态：

- `included`：图片字节以内嵌 PNG `data:` URI 保存，同时记录 MIME、字节数、像素尺寸、图片 SHA-256、原始 PDF SHA-256、页码、提取方法以及图片索引或裁切框；
- `not_present`：逐页检查未发现候选人头像，不保存图片或来源对象；
- `ambiguous`：存在疑似图片，但无法可靠确认是候选人个人头像；保留已检查的 PDF 页码，不保存图片；
- `extraction_unavailable`：页面有清晰头像，但当前能力无法可靠提取；保留已检查的 PDF 页码，不保存图片。

`included` 只能来自 `input/resume-original.pdf`。嵌入图片方式必须使用非负 `image_index` 且没有裁切框；页面裁切方式必须记录 `x,y,width,height` 且没有图片索引。图片嵌入前必须统一转换为 PNG 并重新视觉核对；规范化时先检查尺寸，再校验 PNG 结构和像素数据，只保留显示所需图像数据并移除非显示辅助块和文件尾随内容。面试官数据校验器拒绝 JPEG、损坏图片和未经规范化的负载。所有照片状态都禁止公开头像搜索、人脸识别、跨来源相似度、年龄或外貌分析。

年龄按 `case.report_date` 换算：

- `YYYY-MM-DD`：准确周岁，`approximate=false`；
- `YYYY-MM`：换算近似年龄，`approximate=true`，显示中含“约”；
- `YYYY`：报告年份减出生年份，`approximate=true`，显示中含“约”；
- 未提供出生信息：年龄显示“未提供”。

当出生信息未提供时，另填 `timeline_age_estimate`：

1. 优先取简历明确写出的最早本科入学时间，接受 `YYYY`、`YYYY-MM` 或 `YYYY-MM-DD`。
2. 入学时间缺失时，仅当本科毕业时间和明确学制同时存在，才反推入学年份；不能自行假设学制，也不能把毕业月份或日期继承为入学月份或日期。
3. 入学年龄假设固定为最小 16 岁、典型 18 岁、最大 20 岁。区间上下界必须同时包含入学年龄不确定性和锚点日期精度不确定性。
4. 研究生入学、工作开始等后续日期只作为 `consistency_checks`。确定早于本科锚点时使用 `timeline_conflict` 并移除数值区间；日期精度重叠时使用 `not_assessable`，不能武断判冲突。
5. 没有合格锚点时使用 `insufficient_evidence` 且不输出数值；候选人提供了出生信息时使用 `not_needed`，不得同时保留时间线锚点。
6. `estimated` 的展示文字必须写明“推算”和“非候选人自述”，保存截止日、来源位置、锚点精度和固定假设。照片和所有年龄信息均不得进入岗位匹配、评分、稳定性判断、录用/淘汰或排序。

`derive_timeline_age.py` 接受重复的 `--consistency-check-json` 参数。每个 JSON 对象包含 `event`、`date` 和 `source_locator`；脚本根据日期自动填写 `precision`，拒绝未知事件、缺失来源和不匹配的显式精度。

`education` 和 `employment` 直接汇总候选人明确提供的学校、专业/学历、单位、职位、时间和城市。城市另存 `city_source_status`：明确写出时为 `candidate_provided`，没写时为 `not_provided` 且值固定为“未提供”。不得根据学校或单位所在地补写城市。

`fit_items` 使用三种状态：

- `match` → 符合；
- `foundation_needs_confirmation` → 有相关基础，需面试确认；
- `evidence_insufficient` → 当前证据不足。

年龄、出生、籍贯、老家和婚姻词语不得进入 `fit_items`。

#### 简历疑点

`resume_risks` 最多 8 项，按 `importance` 从高到低、`order` 从 1 连续排列。每项都包含能力、原话、描述不清之处、核验原因和核验方式。

#### 面试问题

`interview_questions` 必须为 12–18 道，按 `must_ask`、`recommended`、`optional` 排列，顺序号从 1 连续递增。

题库至少各含一道 `job_core`、`work_sample`、`resume_check`、`soft_skill`、`logistics` 和 `candidate_choice`，防止题数达标但岗位覆盖缺失。

- `rated`：必须有回答好、一般、差的具体参考以及加分点、减分点。
- `record_only`：只提供记录说明，不得含评分字段。`logistics` 和 `candidate_choice` 必须使用此模式。

题库必须包含一道人岗评分之外的婚姻状况可选题：`kind=candidate_choice`、`evaluation_mode=record_only`。候选人不回答不产生负面判断。

### 10. 离线 HTML

HTML 只嵌入面试官视图对象，并恰好包含三个主模块。页面不渲染后台分数、权重、覆盖率、门槛、可比性、来源表、完整证据账本或九类行为假设。

`candidate_photo.status=included` 时，候选人简介使用照片加信息区的双栏布局，并在图片下标明来自简历 PDF 且不参与评估或排序；其他状态不得预留空白照片栏。`timeline_age_estimate` 不是 `not_needed` 时使用“履历推算年龄区间”独立标签；证据不足或时间冲突也要如实显示，不能悄悄省略失败状态。

页面状态使用以 `case_id` 命名空间隔离的 `localStorage`，只保存题目重点、回答表现和备注，不另存候选人基本信息。无本地存储时页面仍可使用和导出。不得发起网络请求。

重点状态：

- `none`：不标记；
- `maybe`：黄色“可能要问”；
- `must`：红色“一定要问”；
- `backup`：蓝色“备选”。

岗位题记录为“未问、好、一般、差”；自述题记录为“未问、已记录、不便回答”。颜色同时配有文字，不只依赖颜色传达。

## 校验顺序

1. 校验后台四个稳定对象和跨引用。
2. 校验来源账本和证据账本。
3. 计算后台面试分和覆盖状态。
4. 对照片运行结构、大小、尺寸、规范化字节、哈希、原始 PDF 来源和提取位置校验；对履历年龄区间重算锚点、精度、假设、时间顺序和上下界。
5. 校验 `interviewer-report-data.json`。
6. 用包含候选人姓名的文件名渲染 HTML。
7. 校验 HTML 的三模块、姓名、离线依赖和交互标记。
8. 浏览器分别检查有照片、无照片和推算失败状态的控制台、重点切换、本机恢复、导出、清空、打印和响应式布局。

## 交付检查

- [ ] 原始材料有哈希，PDF 完成文字与视觉双通道核对。
- [ ] 后台岗位、证据、来源、蓝图和评分对象校验通过。
- [ ] 面试官数据通过独立 Schema、照片来源与字节校验、出生年龄换算和履历年龄重算。
- [ ] 文件名、浏览器标题、页面主标题都包含候选人姓名。
- [ ] 主 HTML 只有三个模块，问题数为 12–18。
- [ ] 候选人已明确提供的学校、单位和城市已显示，缺失项未推测。
- [ ] 有照片时只使用简历 PDF 中视觉确认的头像；无照片时不预留空栏；未执行任何生物识别或外貌推断。
- [ ] 出生信息优先；无出生信息时履历年龄区间有明确本科锚点、固定假设和来源，证据不足或冲突时没有数值。
- [ ] 照片、年龄（含履历推算区间）、籍贯、婚姻未进入岗位匹配、评分、稳定性判断或排序。
- [ ] 简历疑点按重要性降序且使用中性中文。
- [ ] 重点标记和面试记录可以本机恢复与导出。
- [ ] 报告离线可用、无外部依赖、无自动录用或淘汰结论。
