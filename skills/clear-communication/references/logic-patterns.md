# Logic Patterns

This reference gives compact models for choosing an information shape. The examples are illustrative; they are not fixed templates.

## A pipeline

Use a pipeline when later actions require earlier results:

```text
goal → prerequisites → action → check → outcome or recovery
```

Keep the check beside the action it validates. If a failure changes the next step, branch at the failure instead of hiding it in a final warning.

## A decision tree

Start with the observable condition, then name the branch and its consequence:

```text
What is the current state?
├─ state A → do A → verify A
└─ state B → do B → if B fails, recover or stop
```

Do not list branches before telling the reader how to identify them.

## A network

For a system with many relationships, give the reader a map before enumerating nodes:

```text
entry point → central nodes → dependent nodes
                         ↘ feedback or cross-link
```

Explain why the chosen traversal is useful. A network description may have a reading order without claiming that the system itself is linear.

## A narrative reveal

An opening result, flashback, or delayed explanation works when it creates a question and later answers it. Give the reader enough orientation to know whose result it is, when it matters, or what question is being answered. Each reveal should reduce a stated uncertainty rather than introduce an unrelated fact.

## A review pass

Mark each major unit with the relation it has to the previous one: `because`, `therefore`, `however`, `for example`, `if`, `after`, `while`, or `this changes`. Missing or contradictory relations are candidates for a bridge sentence, reorder, split, or explicit uncertainty label.
