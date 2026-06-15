# Profile Schema

用户画像分三层：`semantic profile` 保存当前有效断言，`episodic evidence` 保存典型事件，`procedural memory` 保存如何沟通和追问。

画像可以保存两类信息：

- `collaboration profile`: 沟通、澄清、工作流、风险确认、隐私边界、反茧房规则等协作信息。
- `background profile`: 用户主动提供的年龄段、教育、专业、职业/角色、经验阶段、长期目标等背景上下文。背景信息默认 `private`，不进入跨 skill 低敏摘要。

## Files

```text
<home>/.compass-skills/user-profiles/v1/
  registry.json
  users/
    default/
      profile.sqlite3
      snapshots/
      proposals/
      exports/
```

目录权限应为 `0700`，数据库文件应为 `0600`。SQLite 使用 WAL、事务和 busy timeout，避免多 session 覆盖写。

## Tables

- `users`: 用户 ID、显示名、创建和更新时间。
- `profile_assertions`: 当前或历史画像断言。
- `evidence_events`: 支持断言的具体事件。
- `update_proposals`: 待确认更新包。
- `audit_log`: 所有写操作、确认、拒绝、纠错和删除记录。
- `consents`: 保存范围、禁存范围和确认偏好。
- `redactions`: 被拒绝保存、脱敏或替换的信息记录。
- `aliases`: 明确声明的新用户或别名。

## Assertion Fields

```json
{
  "category": "communication_preference",
  "claim": "prefers_structured_chinese",
  "value": {"summary": "用户偏好中文、结构化、证据优先的回答"},
  "scope": "global",
  "source_type": "self_report",
  "confidence": 0.95,
  "sensitivity": "low",
  "status": "active",
  "evidence": {
    "summary": "用户明确自述长期偏好中文、结构化、避免夸赞并优先准确性",
    "context": "current session durable self-report",
    "raw_excerpt": "以后默认用中文、结构化、少夸赞，优先准确性"
  }
}
```

允许的 `category` 包括但不限于：

- `communication_preference`
- `clarification_style`
- `decision_style`
- `domain_familiarity`
- `capability_boundary`
- `common_omission`
- `risk_boundary`
- `privacy_boundary`
- `workflow_preference`
- `background_context`
- `education_background`
- `career_context`
- `learning_context`
- `correction`
- `important_event`
- `anti_bubble_rule`
- `inference_hypothesis`

允许的 `source_type`：

- `self_report`: 用户明确自述。
- `observed`: 当前 session 中可观察到的稳定行为。
- `inferred`: agent 推断，默认 pending。
- `correction`: 用户纠正画像或先前判断。

允许的 `sensitivity`：

- `low`: 可安全用于需求澄清摘要。
- `private`: 私人但不高度敏感，默认不暴露给其他 skill，除非有用途。
- `sensitive`: 敏感身份、健康、财务、法律、羞耻或安全相关。
- `intimate`: 创伤、亲密经历、深层心理和强隐私内容。
- `secret`: credential、token、密码、私钥、验证码；不得保存原文。

允许的 `status`：

- `active`
- `pending`
- `superseded`
- `retracted`
- `conflicted`

## Proposal JSON

`profile_store.py update-from-session --candidate-json` 接受数组：

```json
[
  {
    "category": "clarification_style",
    "claim": "needs_complete_alignment_contract_for_high_risk_tasks",
    "value": {"summary": "高风险任务前需要明确对齐契约和确认"},
    "scope": "task-clarification",
    "source_type": "self_report",
    "confidence": 0.95,
    "sensitivity": "low",
    "evidence": {
      "summary": "用户要求确保需求完全、准确、清晰地对齐，重要情况必须确认",
      "context": "current session",
      "raw_excerpt": "重要的情况，比如设计删除文件等或者影响很大的情况还是需要让用户来确认/回答的"
    }
  }
]
```

`raw_excerpt` 应尽量短，只保存必要证据；敏感原文优先省略或脱敏。

## Inference Candidate Value

凡是 `source_type=inferred` 的候选，`value` 至少应包含：

```json
{
  "summary": "用户可能偏好在高风险 skill 设计前先看完整方案",
  "basis": ["多次要求先分析原因和流程，再改 skill"],
  "reasoning": "该偏好能解释用户反复纠正打补丁式修改，但仍可能只是当前任务要求。",
  "counter_evidence": ["用户也要求在明确同意后直接执行方案"],
  "usefulness": "用于决定是否先输出方案、哪些内容需要确认。",
  "review_question": "是否把“结构性改动前先给完整方案”保存为长期协作偏好？"
}
```

推断候选的 `category` 可以使用具体类别，例如 `clarification_style`，也可以在不确定时使用 `inference_hypothesis`。它们必须进入 proposal，等待用户确认；不得自动写入 active。
