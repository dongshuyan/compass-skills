---
name: pause-and-resume
description: >-
  Cooperatively pause unfinished work in the current session, leave a precise
  continuation checkpoint, and resume from it when the user later says
  continue. Use only when the user explicitly requests this pause workflow.
  Do not use for crashes, app shutdown, new-session handoffs, or ordinary task
  summaries.
---

# Pause and Resume

Keep this workflow in the current session. Store its state in the pause
response; do not create files, commits, or new tasks solely to checkpoint it.

## Pause

1. Stop expanding the task. Do not begin another subtask, retry, or optional
   check.
2. Let an already-started atomic action finish only when interruption would
   leave inconsistent state. Otherwise stop at the nearest safe boundary. Use
   only the smallest necessary read-only check or already-authorized cleanup to
   record an accurate, safe state.
3. Preserve facts, not guesses. Distinguish completed, in progress, blocked,
   and unknown work. Record exact non-sensitive paths, parameters, job IDs, and
   receipts when they are needed to continue. Never expose secrets.
4. If work continues independently, record its handle, observed status, and
   how to reconcile it. Do not cancel, restart, or dispatch it again merely to
   pause.
5. End the turn with the compact checkpoint below, in the user's language.
   Keep the marker exact, omit irrelevant detail, and state explicitly when
   there is no known non-repeatable effect.

```text
PAUSE_CHECKPOINT: ACTIVE
- Goal and done condition:
- Completed:
- Current stopping point:
- Remaining work:
- First action on resume:
- Do not repeat:
- Constraints and settled decisions:
- Live state, running work, and facts to recheck:
```

Finish with the equivalent of: `Paused. When you return, say "continue".` Then
stop. Do not perform the first resume action in the pause turn.

If there is no unfinished task, say so and stop without emitting an active
checkpoint.

## Resume

When the user later asks to continue the paused work:

1. Use the newest unconsumed `PAUSE_CHECKPOINT: ACTIVE` in this session. A
   checkpoint is consumed once substantive work has resumed from it. If none
   exists, interpret the request from the immediate conversation normally.
2. Apply later user instructions over the checkpoint. Recheck only mutable or
   high-risk state that could have changed while paused, especially files,
   worktree state, running jobs, and external side effects.
3. Reconcile recorded in-flight work before starting replacements. Never repeat
   an item under `Do not repeat` unless current evidence proves it did not occur
   and repeating it is authorized.
4. Resume directly from `First action on resume`, then continue the recorded
   remaining work. Do not ask the user to restate known context or produce a new
   plan unless material drift makes a decision necessary.

This workflow cannot recover a killed process, missing conversation, or a
different session; use a handoff or persistent checkpoint workflow for those
cases.
