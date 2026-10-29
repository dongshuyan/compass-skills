# Third-party notices

## Agent Clarity session titles

The optional `clarity-session-titles` Codex plugin derives substantially from [panda-z519/agent-session-titles](https://github.com/panda-z519/agent-session-titles), pinned to revision [2d931a54a736a57c23a3e9a7fcfca56031dfd5f3](https://github.com/panda-z519/agent-session-titles/tree/2d931a54a736a57c23a3e9a7fcfca56031dfd5f3), MIT, Copyright (c) 2026 panda-z519.

- Copied: `parse_three_part_title`, `protected_segments`, and `merge_protected_title` in [title_segments.py](plugins/clarity-session-titles/scripts/title_segments.py). Their function bodies and signatures match the pinned source.
- Adapted: manual-edit reconciliation in `title_runtime.py` and the plugin's `manage-title` Skill guidance. The three-part title format, per-segment manual-edit protection, and lifecycle prompting pattern originate upstream.
- Added in Agent Clarity: project/global installation and removal, API-only title writes with readback, per-turn verification with at most one repair, scope handover and concurrent-write coordination, and an explicit shared-state installation mode for configured Codex/Harbor homes.
- Added for this repository: public packaging, separation from portable Skill installation, relocation verification, and installation/source documentation.

The original MIT notice is retained verbatim in [LICENSES/agent-session-titles.txt](plugins/clarity-session-titles/LICENSES/agent-session-titles.txt). The plugin bundle also includes a [copy of the COMPASS MIT license](plugins/clarity-session-titles/LICENSE) for its original contributions. The upstream project is credited for the reused design and code; this package does not imply upstream endorsement. See [installation and source notes](docs/session-titles.md).

## Clear Communication

The writing guidance in Clear Communication was informed by and adapted from principles in:

- [GPT with Taste](https://github.com/NB-Corp/gpt-with-taste/tree/079fb262b4d7932515ba4e6341fd57b6f2122f4a), revision 079fb262b4d7932515ba4e6341fd57b6f2122f4a, MIT. The original notice is distributed in [gpt-with-taste.txt](skills/clear-communication/references/licenses/gpt-with-taste.txt).
- [plain-english](https://github.com/Tradelord223/plain-english/tree/d108f2b61544cdabb33cd67f6365faf3f51259a9), revision d108f2b61544cdabb33cd67f6365faf3f51259a9, MIT. The original notice is distributed in [plain-english.txt](skills/clear-communication/references/licenses/plain-english.txt).

Its reader-oriented goal also draws on the International Plain Language Federation's definition, available on [Clarity's institutional website](https://www.clarity-international.org/).

The evaluation design was informed by [plain-writing-skill](https://github.com/docwriter-org/plain-writing-skill/tree/f0d3630983ac7a82aa580f1c1509d72df739ee12) and [Agrawal and Carpuat's 2024 TACL paper](https://aclanthology.org/2024.tacl-1.24/). These references supply methods and context, rather than evidence of this package's effectiveness.

The package includes the writing instructions, original hypothetical examples, source notes, and required license notices. It does not bundle upstream installers, hooks, evaluation datasets, or the paper.

See [the source notes](skills/clear-communication/references/sources.md) for the contribution and limits of each reference. The repository's original contributions remain under [its MIT license](LICENSE); the retained notices apply to the corresponding upstream material.
