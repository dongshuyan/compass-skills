# Output Contract

Default output has two parts:

1. The paste-ready continuation prompt.
2. A short note to the current user about mode, privacy, sources, and limitations.

## Paste-Ready Prompt

Use the user's language. Default to Chinese when unknown. The section labels may be translated, but the structure must remain stable:

```text
You are taking over an ongoing agent session. Resume from the context below. Do not re-open settled decisions unless current files or verified evidence contradict them. If this prompt conflicts with current workspace evidence, prefer current evidence and explain the conflict.

Workspace:
...

User goal:
...

Hard requirements:
...

Confirmed facts and decisions:
- [verified] ...
- [inferred] ...
- [unverified] ...

Task-forest state:
...

Completed:
...

Pending / needs verification:
...

Key files / commands / artifacts:
...

Do not repeat / do not do:
...

Next actions:
1. ...
2. ...
3. ...
```

Omit `Task-forest state` when no exports were read, or state that task-forest exports were not found.

The validator recognizes the English and Chinese headings above. For another language, pass the exact translated headings with `--labels-json <labels.json>`:

```json
{
  "workspace": "Espacio de trabajo:",
  "goal": "Objetivo del usuario:",
  "requirements": "Requisitos obligatorios:",
  "completed": "Completado:",
  "pending": "Pendiente / por verificar:",
  "next": "Próximas acciones:",
  "fact_labels": ["[verificado]", "[inferido]", "[no verificado]"],
  "task_forest": "Estado de task-forest:"
}
```

The six section keys are required. `fact_labels` and `task_forest` are optional.

## Fact Labels

- `[verified]`: user explicitly stated it, or it came from files, tool output, test output, task-forest exports, or another concrete source.
- `[inferred]`: reasonable inference from multiple sources, but not directly confirmed.
- `[unverified]`: important but currently unchecked, stale, conflicting, or based only on weak evidence.

Never write a model guess as `[verified]`.

## Current-User Note

After the prompt, add a short note outside the paste-ready block:

```text
Mode: balanced. Privacy: local. Sources: current conversation, task-forest exports, workspace files. You can ask for minimal or full.
```

For `shareable` privacy, state that local paths and credential-like strings were redacted.

If source coverage is weak, state the limitation clearly:

```text
Source limitation: no transcript file or task-forest export was available, so this prompt relies on the visible conversation and workspace evidence.
```
