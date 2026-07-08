# Open-Source Pattern Mining

Read this file when local evidence is not enough to choose a strong package structure or validation strategy.

## Search Goals

Use public references to learn packaging patterns, not to outsource judgment.

Good targets:

- official skill frameworks or platform docs;
- first-party or maintained example skill repositories;
- similar public skills with readable `SKILL.md`, clear boundaries, and transparent scripts.

## Search Discipline

Record for each candidate:

- repository or document URL;
- last-updated signal or commit date;
- files actually read;
- patterns adopted;
- patterns rejected and why.

## Screening Checklist

Prefer references that:

- explain when the skill triggers and when it does not;
- keep `SKILL.md` concise and push details into `references/` or `scripts/`;
- show validation, regression, or smoke checks;
- avoid credential handling, opaque installers, or dangerous automation.

Reject or heavily down-rank references that:

- ship hardcoded keys, session exports, or credential readers;
- rely on private paths or environment-specific assumptions;
- replace evidence with marketing claims;
- have no readable source for critical behavior.

## What To Adopt

- trigger wording patterns;
- resource split patterns;
- validator ideas;
- example/eval structures;
- route-hardening techniques.

## What Not To Adopt

- repo branding as proof of quality;
- unexplained heuristics;
- forced `README`, installer, or changelog files when the target ecosystem does not need them;
- local company conventions presented as universal rules.

## Temporary Research Directories

Clone or download references only into a temporary local directory outside the final skill package. Do not ship the research copies unless the user explicitly asks for them.

## Packaging Rule

If public references disagree with the run history, trust the run history for the user's actual workflow and use the public material only to improve packaging quality.
