# Plan data and checkpoints

Python 3.9 or later, standard library only. The examples use `$tool` for the absolute path of this skill's `scripts/plan.py`. Set it from the actual skill location. Paths to the report and input are ordinary workspace paths. Supply JSON from a file or use `-` for standard input.

```sh
python3 "$tool" init plan.html first-plan.json
python3 "$tool" status plan.html
python3 "$tool" apply plan.html start.json
python3 "$tool" apply plan.html review.json
python3 "$tool" status plan.html --full
```

`init` creates a new report. `status` reads its revision, available leaves, active nodes, phases awaiting integrated acceptance and deviations. `--full` includes the complete definitions, work records and history. `apply` publishes one event. Use its returned revision when serializing your own events. After parallel work, read the latest revision and check that the evidence and proposed changes still fit before retrying a stale write.

## A complete small plan

This example illustrates input shape. Use the task's real evidence when authoring a plan.

```json
{
  "title": "核对导出总额",
  "goal": "导出文件的总额等于已确认明细之和。",
  "lang": "zh-CN",
  "nodes": [{
    "id": "total", "parent": null, "title": "交付可复测的总额",
    "description": "核对一份导出文件。", "constraints": ["保留原有明细"],
    "estimate_minutes": [5, 15], "deps": [],
    "deliverable": "含总额的导出文件", "expected": "总额与有效明细一致",
    "acceptance": "用同一份输入独立求和，并比较导出值。",
    "facts": [{"claim": "用户要求保留明细并增加总额。", "source": "已确认的交付要求", "confidence": "high"}],
    "rationale": "输入和计算口径已知，可以独立复算。估时假定现有导出流程能直接复用。"
  }]
}
```

Use a single positive number or `[low,high]` minutes. A leaf's high estimate must be at most 360. Parents may take longer. `constraints` and `deps` may be empty lists. IDs use letters, digits, dots, hyphens or underscores. Exactly one root has a null parent; sibling ordering follows the node list. All node fields in the example are required. If the only basis is a hypothesis, write its check in `rationale` and use `{"claim":"…","source":null,"confidence":"low"}`. Use `high`, `medium` or `low` for confidence. Source text may be a URL, a document with page or line, a measured artifact, or an explicitly attributed observation.

A prerequisite ID requires a passed result. Use `{"id":"baseline","needs":"evidence"}` when usable findings from a closed check suffice. A deviation qualifies only when its review explicitly identifies the usable output in `usable_evidence`. Interruptions and missing measurements do not qualify. Prerequisites on a parent apply to its descendants. The report lists eligible leaves and shows which prerequisites hold back others.

For an outstanding external input, place `"awaiting_input":"等待当天明细"` on its receipt leaf. Downstream nodes depend on that leaf. Once the file arrives, inspect it and include `"input_evidence":"已打开当天明细.csv，核对表头和行数。"` in the receipt's start. The HTML shows the source. A mock can have its own independent leaf. If real functionality requires the input, put the receipt in its prerequisites and test the real route at the functional parent.

For a pending quantitative prediction, use an honest `expected` such as “待首次实测后估算” and add `"baseline":{"metric":"准确率","method":"按确认的样本集复测","node":"measure"}`. Define the measurement in the initial tree. By default a leaf that names a separate measurement waits for its usable result. A phase or a self-measurement displays the forecast without blocking its own work. To indicate that independent framework work can start earlier, set `"use":"forecast"` inside its baseline. Set `"use":"input"` when a phase requires another branch's measurement before starting. The report shows the actual once available. Update affected expectations and reasons; retain the agreed target in the root goal and acceptance.

## Start and close

```json
{"kind":"start","node":"total","event_id":"total-start-1","base_revision":1}
```

```json
{
  "kind":"close","node":"total","event_id":"total-review-1","base_revision":2,
  "verdict":"passed","actual":"导出总额与独立复算一致。",
  "evidence":["核对记录中两种方法的总额与行数"],
  "use":"打开交付的导出文件，查看总额。",
  "test":"用同一输入执行核对命令，比较两处总额。"
}
```

`passed` means the acceptance condition was met. `deviation` means the attempt ended short of acceptance. `interrupted` records an observed stop before acceptance could be assessed. Record the last observable state and what is available to use or retest. A receipt, missing output, terminal log or other evidence must be specific enough for the reader to locate. The helper stores the agent's observations. Give real commands or concrete UI steps. Supply `reason` for a missed forecast, slower run, interruption, failed acceptance, goal risk or revision. Explain the effect on the remaining route and the target. If a deviation yielded a usable measurement, include its source and finding in `usable_evidence`.

Duration defaults to the observed start-to-close wall clock. For work measured elsewhere, set `duration_seconds` and cite its timing record in `time_source`. When timing cannot be verified, use null and explain why. After losing contact with an active attempt, inspect the artifacts. If the same attempt is continuing, keep its existing start. For an observed termination, close as interrupted and give the next concrete check, then start a new attempt when possible. Leave the state open while the outcome is genuinely unknown.

A close can carry a `changes` array of the following forms, applied together. All edits share the close's reason and evidence.

| Change | Data |
|---|---|
| Add a recovery task or sub-stage | `{"add": <complete new node>}` |
| Re-estimate, move, change prerequisites or update a forecast | `{"edit":"later","set":{"estimate_minutes":[15,25],"deps":["measurement"]}}` |
| Replace a planned or unsuccessfully closed task | Add the replacement, rewire prerequisites and `{"retire":"old-id"}`. The old result stays in history. |
| Retry the same unsuccessful or interrupted node | Start it again with a fresh event ID. Its original acceptance and past review stay intact. |

Edit future definitions as evidence warrants. On active nodes, only `expected`, `estimate_minutes`, `baseline`, `facts` and `rationale` may change. The helper keeps the forecast from the start of the attempt. Record active children's outcomes before closing a phase. When a phase ends early, record the interruption or deviation and any retirement/replacement of pending work together. Superseded work remains in the log. A phase passes only after its integrated check and all remaining children pass. Keep the user's goal, deliverable, constraints and acceptance distinct from revisable forecasts.

Example of evidence-based revision: the measurement node returns usable data but a lower score than predicted. Close that measurement as passed if its acceptance was “produce the measured score”. Record the forecast miss in `reason`. In the same close, add a diagnostic node and make the subsequent improvement depend on it; update the affected forecast and its facts. If the acceptance itself was missed, use `deviation`. These are different outcomes even when the observed number is the same.

Use optional `goal_risk` to explain the threat and practical choices. It stays visible above the tree until a later close explicitly clears it with `"goal_risk":""` and supporting evidence, or the user changes the goal. An explicitly confirmed change uses `{"kind":"goal_change","node":"ROOT_ID","event_id":"decision-1","base_revision":5,"goal":"new confirmed goal","confirmation":"the user's own decision or its reference","reason":"why it changed","changes":[]}`. The helper records the confirmation supplied by the agent. Changes to root requirements, deliverable or acceptance belong to this event.

The HTML is the authoritative plan and the user-facing deliverable. A hidden sibling lock coordinates local writers; it contains no plan data. Updates validate the tree and prerequisites before one atomic replacement. Event IDs make exact retries safe; changing an existing event's payload is rejected. A stale base returns exit 3. Invalid data returns exit 2 and leaves the previous report intact. Reopen or copy the HTML itself to read it offline. A live browser tab checks for disk revisions and retains its selection. Chinese and English labels are included. Set `lang` for the reader and write all task content accordingly; the optional `labels` object overrides interface wording (keys and defaults in `assets/report.html`).
