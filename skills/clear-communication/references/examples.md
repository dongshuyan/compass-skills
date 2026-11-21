# Information-Selection Examples

These examples are hypothetical package examples, not project or experiment
results. They show how to preserve the relationships that affect a reader's
next decision.

## Turn a record into usable instructions

The reader needs to know how to start with a newly installed note tool. The
source says: open NoteBox and choose **New note**; content is saved in the
current browser. One real save operation was checked. A cloud-sync button is
visible but the service is not connected. The maintenance log lists 23 local
checks, `sync_enabled=false`, and a plan to organize logs later. Clearing
browser data deletes local notes; closing the window does not.

Better:

> Open NoteBox and choose **New note** to begin. Your notes are saved in the
> current browser. The save operation has been checked; cloud sync is not
> connected yet, so another device cannot read these notes through the sync
> button. Closing the window does not delete notes, but clearing browser data
> does.

The rewrite keeps the start action, storage location, verified scope, sync
limit, and the two different deletion consequences. The check count, internal
flag, and future log plan stay in the maintenance record because they do not
change this reader's next action. A maintenance audit could need them again;
the omission rule depends on the reader and task.

## Keep state and evidence together

Source: the change is complete, eight local tests pass, and Windows has not
been tested.

Misleading:

> The fix is complete and works on Windows.

Better:

> The change is complete and eight local tests pass. Windows still needs a
> runtime check.

The point is to keep the work state beside the evidence boundary. Shorter
sentences alone do not make the claim safer.

## Put conditions next to the operation they qualify

Source: read requests may be retried. Write requests may be retried only when
they carry an idempotency key, and the same key represents the same operation.

Easy to misread:

> Retry failures, and remember to use an idempotency key.

Better:

> A read request may be retried. A write request may be retried only
> when it carries an idempotency key; reuse that same key when retrying the
> same operation.

The terminology stays intact, but the reader no longer has to guess which
request type the condition governs.

## Do not turn correlation into a cause

Source: the error has not reappeared after a service restart, and its root
cause is unknown.

Misleading:

> Restarting the service fixed the problem.

Better:

> The error has not reappeared since the restart. Its root cause is still
> unknown.

## Preserve a clear short sentence

Source: `Save, then close the window.`

Keep it as written when the task does not require storage details or failure
handling. Do not add background merely to make the edit look substantial.

## Preserve scholarly evidence strength

Source: on one dataset, A has a higher mean than B. No significance test was
run, and the observation does not establish causality.

Misleading:

> A is significantly better than B, showing that the mechanism improves
> performance.

Better:

> On this dataset, A has a higher mean than B. No significance test was run,
> and this observation does not establish causality.

Keep the manuscript's terminology and citations. This example illustrates an
evidence boundary; it is not a fixed closing sentence for every paper.
