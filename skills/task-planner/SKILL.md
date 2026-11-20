---
name: task-planner
description: Create a complete, expandable HTML plan for an agreed task and keep the same report current as plan nodes finish. Use for a new task plan, continuing a planned run, or revising a plan from execution evidence.
---

# Task Planner

Use the confirmed goal, constraints, priorities and acceptance from the conversation or a Task Clarifier handoff. Resolve a material gap if it would change the deliverable. Keep permission to *execute this turn* separate from the project's acceptance criteria. Plan when the work is new. When an existing plan is being carried out, review it at each observable checkpoint. The executor owns the work and dispatch decisions.

## Build the first plan

Decide **whether to split at all**. A job that can deliver the complete, stable, accurate result in one pass can have a single root leaf. Split when an intermediate result can be used or checked, distinct prerequisites matter, or an executable leaf's estimated upper bound exceeds six hours.

For substantial work, organize the tree around delivery stages. A stage can contain sub-stages, then modules or concrete work. When building in layers, establish the framework first, then fill in real internals. Mock connections may let the user experience the whole flow early. Give that framework its own acceptance, and check the actual agreed functions at the functional parent. Add separate stability, accuracy, speed or polish stages only when the task warrants them. Make the normal path work early and scale testing to what that stage promises.

Every node, including the root, describes the task, constraints, estimated elapsed time, usable deliverable, expected effect, an observable acceptance test, and its actual prerequisites. The tree shows ownership. Dependencies show which results are needed and which leaves can proceed concurrently. When an external input is missing, mark an intake leaf as waiting for it and make its consumers depend on the verified receipt. Use stable IDs. Estimate elapsed time from applicable evidence and name the assumption that most affects it. Parent elapsed time can account for overlap.

Ground forecasts in facts, each with a source and qualitative confidence. Give a brief, checkable explanation of how they support the expectation. Mark unsupported premises as low-confidence assumptions. If a research baseline is missing, **deliver the complete tree now**. Put the first real measurement in a node, give its method, and mark unsupported downstream figures pending that observation. Keep the user's final target explicit.

Use [the data and command examples](references/plan-format.md) to publish one self-contained HTML file in the requested location, or `plan.html` in the task workspace. Open the existing report to resume; choose another name for a different plan. Run the helper relative to this skill's actual installation. Link the first HTML as soon as it is valid. A planning-only request ends with this deliverable.

## Review a running plan

When the user authorizes an entire run, carry this loop into the executing context. Keep the report path and node IDs with the work, including parallel work or a handoff. The agent observing a result performs the checkpoint automatically, without a separate user prompt per node. Installing this skill makes it discoverable; an active executor or reported evidence supplies the completion signal.

1. On taking up work, read `status` and record `start`. Starting a child opens its ancestors. While a node is underway, its HTML status is **in progress**. Keep provisional observations with the work until the node ends.
2. At each node end, inspect the output and run its acceptance check. Capture the measured time, outcome, source of evidence and the user's steps to use and retest it. For a working feature, test the real interface or data its acceptance promises. Identify fixtures or mocks in a prototype's outcome. If resuming a plan, inspect each active node: continue the same attempt if it can proceed, or record an observed interruption and restart when its input is available. Use an unknown duration if reliable timing was lost.
3. Before moving past that observable checkpoint or reporting completion, issue **one `close` event**. Include the verdict, actual, evidence, use/retest steps and any justified plan changes together. A successful command is evidence for the particular check it performed. Judge the promised deliverable as well. When everything matches, record the pass even if the future plan needs no changes. Record earlier completion as observed. Explain slower work or an unexpected functional result in proportion to its effect.
4. Revisit the original evidence and assumptions when a prediction misses. Explain which later work and final target it affects, including why an immediate retry is sufficient when applicable. Revise forecasts for active phases and definitions of future tasks. Add recovery work or retire superseded work. If a new finding undermines an earlier acceptance, preserve that result and add a fresh check to the remaining route. Include the new reasoning and its evidence. A valid measurement can satisfy a measurement node even if its predicted value was wrong. A phase needs its own integrated acceptance after its children finish. Continue the loop for every finished node during an authorized run.
5. If evidence undermines the final target, keep that target visible. Record the risk and options and discuss them with the user. Only a genuine user decision can change agreed root criteria. A threatened hard constraint can be raised in the conversation immediately; the node's HTML review is committed at its close.

The top of the report shows the current plan. The lower log preserves prior forecasts, findings, decisions, and what changed. Write in the reader's language (default Chinese). Name the actual result in the title, e.g. “核对各门店净额”. State the outcome and how to check it in one or two short sentences each. Put detailed arithmetic, commands and sources in the evidence or retest fields. Link a long technical record rather than pasting it into the summary.
