# Examples

## 初始化默认用户

```bash
# macOS / Linux
python3 <user-profile-keeper-dir>/scripts/profile_store.py init --user default

# Windows
py -3 <user-profile-keeper-dir>\scripts\profile_store.py init --user default
```

## 读取给 task-clarifier 的低敏摘要

```bash
python3 <user-profile-keeper-dir>/scripts/profile_store.py read --user default --view clarification_summary
```

## 读取本 skill 内部的画像概览

```bash
python3 <user-profile-keeper-dir>/scripts/profile_store.py read --user default --view profile_overview
```

`profile_overview` 可展示 low/private active 断言，但省略 sensitive、intimate、secret 和证据原文。其他 skill 不应读取这个视图。

## 从当前 session 生成候选更新

首次构建画像时，先运行 Context Adequacy Gate。只有当前 session 包含足够的长期画像证据，或用户明确拒绝问卷，才跳过 WebUI；AGENTS、skill 操作规则和当前任务约束不能单独证明“上下文足够”。

Agent 先根据当前 session 提取候选 JSON，再运行：

```bash
python3 <user-profile-keeper-dir>/scripts/profile_store.py update-from-session \
  --user default \
  --session-summary "用户明确要求删除、覆盖、发布、安装等高影响动作前必须确认。" \
  --candidate-json '[{"category":"risk_boundary","claim":"confirm_high_impact_actions","value":{"summary":"高影响、删除、覆盖、发布、安装等操作前需要确认"},"scope":"global","source_type":"self_report","confidence":0.95,"sensitivity":"low","evidence":{"summary":"用户明确要求高影响动作前确认","context":"current session","raw_excerpt":"删除、覆盖、发布、安装前请先确认。"}}]' \
  --auto-apply-safe
```

## 用户自述背景信息生成 proposal

年龄段、学历、专业、职业/角色、经验阶段、长期目标等背景信息默认 `private`，即使用户明确填写，也先进入 proposal：

```bash
python3 <user-profile-keeper-dir>/scripts/profile_store.py update-from-session \
  --user default \
  --session-summary "用户在初始化问卷中主动填写背景信息。" \
  --candidate-json '[{"category":"education_background","claim":"major_or_specialty","value":{"summary":"用户自述专业或研究方向为 AI 系统"},"scope":"global","source_type":"self_report","confidence":0.9,"sensitivity":"private","evidence":{"summary":"初始化问卷填写专业或研究方向","context":"local onboarding questionnaire"}}]' \
  --propose
```

## 推断性画像只生成待确认 proposal

推断必须带置信度、依据、反证和确认问题：

```bash
python3 <user-profile-keeper-dir>/scripts/profile_store.py update-from-session \
  --user default \
  --session-summary "用户多次要求复杂改动前先给方案，再经确认后执行。" \
  --candidate-json '[{"category":"clarification_style","claim":"prefers_plan_before_structural_changes","value":{"summary":"用户可能偏好结构性改动前先看完整方案","basis":["用户要求先解释原因、范围和验证方式","用户确认方案后才要求执行"],"reasoning":"该偏好可能有长期协作价值，但也可能只是本次任务要求。","counter_evidence":["用户有时会要求直接执行低风险任务"],"usefulness":"用于判断高影响改动前是否先输出方案。","review_question":"是否保存为长期协作偏好？"},"scope":"global","source_type":"inferred","confidence":0.55,"sensitivity":"private","evidence":{"summary":"多轮复杂改动讨论中的行为模式","context":"current session"}}]' \
  --propose
```

## 查看和应用 proposal

```bash
python3 <user-profile-keeper-dir>/scripts/profile_store.py proposal-list --user default
python3 <user-profile-keeper-dir>/scripts/profile_store.py proposal-apply --user default --proposal-id <id>
```

## 用户纠错

```bash
python3 <user-profile-keeper-dir>/scripts/profile_store.py correct \
  --user default \
  --assertion-id <id> \
  --note "这个判断不准确，我只是这次任务需要详细方案。"
```

## 启动本地问卷

```bash
python3 <user-profile-keeper-dir>/scripts/onboarding_webui.py --user default
```

问卷中的选择题必须包含“用户自定义答案”这个互斥选项；只有选中后才显示文本框，提交时只把文本框内容当作该题答案。提交结果只生成 proposal；如果自定义内容包含疑似 credential，原文会被脱敏，且只记录 redaction 事件。

问卷中用于替代“是否希望被挑战”的问题应写成“我应该如何指出问题、反驳假设或提醒风险”，并说明这是针对任务、方案、证据或假设，不是评价用户本人。
