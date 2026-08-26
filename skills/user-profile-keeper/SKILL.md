---
name: user-profile-keeper
description: Local user-profile maintenance skill for Codex, Claude Code, OpenClaw, OpenCode, and other agent harnesses. Use only when the user explicitly invokes $user-profile-keeper to create, initialize, update, query, correct, delete, export, or audit a local persistent user profile. It can extract durable collaboration preferences, requirement-expression habits, capability boundaries, recurring omissions, risk preferences, privacy boundaries, and typical events from the current session into auditable, confirmable, retractable local profile data. Do not auto-invoke, upload profile data, or replace task-clarifier's normal clarification flow.
---

# User Profile Keeper

## Language Policy

**All output directed at the user — profile summaries, proposals, exports, questions, and confirmations — must be written in the user's language.** Detect the user's language from their message. Default to Chinese when unknown. Skill instructions are written in English; that does not affect the language of user-facing output.

## Role

Maintain a local-only user profile. The default user is `default`. Create or switch to another user only when the user explicitly names another identity.

## Portability

This skill is agent-agnostic. Resolve paths from the directory that contains this `SKILL.md`. Use the available Python command on the host (`python3`, `python`, or `py -3`). The scripts are intended for macOS, Windows, and Linux with Python 3 and the standard library.

## Core Contract

- Use this skill only when the user explicitly invokes `$user-profile-keeper`.
- Store profile data in the host user's local home directory under `.compass-skills/user-profiles/v1` by default. Use `COMPASS_USER_PROFILE_HOME` to set another local directory.
- Do not upload profile data. Do not read browser cookies, tokens, passwords, private keys, verification codes, or credentials.
- Treat the store as local plaintext. Before first initialization, tell the user that local files can be read by local processes, users, or backups with sufficient permission.
- Every profile assertion must include source type, confidence, sensitivity, status, and evidence. Avoid untraceable conclusions.
- Low-sensitivity explicit facts with no conflict may be sent through `--auto-apply-safe`; the script decides whether they become active. Inferred, private, sensitive, high-impact, or conflicting facts must become pending proposals.
- Profile scope includes collaboration preferences, requirement-expression habits, capability boundaries, risk confirmation, privacy boundaries, anti-bubble rules, typical events, and user-provided background such as age range, education, field, role, experience stage, and long-term goals.
- Treat background information as `private` by default unless the user explicitly asks for a low-sensitivity summary. Keep it out of cross-skill summaries by default.
- Let the user view, correct, retract, delete, and export profile data at any time.
- Read the full profile only inside this skill. Other skills may read only low-sensitivity views such as `clarification_summary`.
- Current session instructions, AGENTS rules, repository constraints, and skill operating rules constrain the current task. They do not initialize a durable user profile by themselves.
- If the user asks for the onboarding questionnaire or first-run WebUI, run `scripts/onboarding_webui.py --user <id>`.

## Context Adequacy Gate

Use one gate:

- Active profile exists: treat the task as an incremental update. Do not recommend the questionnaire by default.
- No active profile exists: recommend the onboarding questionnaire. If the user asks for it, run the WebUI. If the user declines, continue with the current task and use proposals for any durable profile candidates.

Do not decide that the current session is "enough" by counting covered questionnaire modules. Do not initialize an active profile from operational instructions.

## Session Inference Policy

- `source_type=inferred` always becomes a pending proposal. It never becomes active through `--auto-apply-safe`.
- Explicit self-reported background information, including age range, education, field, role, experience stage, and long-term goals, becomes a pending proposal by default with `sensitivity=private`.
- Use inference only to improve collaboration and follow-up questions. Avoid diagnosis, personality labels, value judgments, and restrictions on the user's choices.

## Workflow

1. Identify the user. Use `default` unless the user explicitly names another identity. Initialize with `scripts/profile_store.py init --user <id>` when needed.
2. Read current state with `scripts/profile_store.py read --user <id> --view clarification_summary`.
3. Apply the Context Adequacy Gate. For first-run questionnaire requests, run `scripts/onboarding_webui.py --user <id>`.
4. Extract candidate updates from the current session. Separate durable profile evidence from task-local instructions, AGENTS rules, repository constraints, and skill operating rules.
5. Write safely:
   - For clearly self-reported, low-sensitivity, non-conflicting collaboration facts, use `update-from-session --auto-apply-safe`. The script applies only candidates that pass safety checks and sends the rest to proposals.
   - For every other candidate, create a proposal with `proposal-create` or `update-from-session` without relying on auto-apply.
   - Report what was applied, proposed, redacted, skipped, and why.

Read `references/update-policy.md` for auto-apply, pending, conflict, correction, and first-run rules. Read `references/privacy-boundary.md` for sensitivity boundaries.

## Storage And Tools

The main store is managed by `scripts/profile_store.py`:

- `init`: create registry, user directory, and SQLite database.
- `read`: read `clarification_summary`, `profile_overview`, `full`, or `pending`.
- `update-from-session`: update from agent-extracted candidate JSON or create proposals.
- `proposal-list` / `proposal-apply` / `proposal-reject`: review and apply pending updates.
- `assertion-add` / `correct` / `delete` / `search` / `export`: manual CRUD and export.
- `validate`: read-only check of an initialized store's integrity, permissions, WAL mode, and orphan evidence references. It reports a missing profile without initializing one.

`validate` does not change profile data or the registry. On a WAL-mode store, SQLite may still create or update a temporary `-shm` coordination file while opening the database read-only.
On POSIX systems, unexpected directory or database modes make validation fail; on Windows, `permission_ok` is `null` because POSIX mode bits are not a reliable permission check there.

Key usage examples:

```bash
# Initialize (macOS / Linux)
python3 <skill-dir>/scripts/profile_store.py init --user default
# Windows
py -3 <skill-dir>\scripts\profile_store.py init --user default

# Read low-sensitivity summary for task-clarifier
python3 <skill-dir>/scripts/profile_store.py read --user default --view clarification_summary

# Submit a self-reported low-sensitivity candidate (auto-apply-safe path)
python3 <skill-dir>/scripts/profile_store.py update-from-session \
  --user default \
  --session-summary "User requires confirmation before high-impact actions." \
  --candidate-json '[{"category":"risk_boundary","claim":"confirm_high_impact_actions","value":{"summary":"Confirm before delete, overwrite, publish, or install."},"scope":"global","source_type":"self_report","confidence":0.95,"sensitivity":"low","evidence":{"summary":"User explicitly stated this.","context":"current session"}}]' \
  --auto-apply-safe

# Submit a private background or inferred candidate as proposal
python3 <skill-dir>/scripts/profile_store.py update-from-session \
  --user default \
  --session-summary "User filled background in onboarding." \
  --candidate-json '[{"category":"education_background","claim":"major_or_specialty","value":{"summary":"User self-reported a field or research direction."},"scope":"global","source_type":"self_report","confidence":0.9,"sensitivity":"private","evidence":{"summary":"Onboarding questionnaire.","context":"local onboarding"}}]' \
  --propose

# Review and apply proposals
python3 <skill-dir>/scripts/profile_store.py proposal-list --user default
python3 <skill-dir>/scripts/profile_store.py proposal-apply --user default --proposal-id <id>

# Start onboarding WebUI
python3 <skill-dir>/scripts/onboarding_webui.py --user default
```

Read `references/profile-schema.md` for data structure and JSON input format. Read `references/questionnaire.md` when onboarding is needed.

## Read Views

- `clarification_summary`: low-sensitivity, active, need-alignment-related summary for optional use by skills such as `$task-clarifier`.
- `profile_overview`: low/private active overview for this skill; excludes sensitive, intimate, secret, and raw evidence text.
- `full`: full profile, only when the user explicitly invokes this skill for profile work.
- `pending`: pending proposals; never treat them as stable profile facts.

Read `references/task-clarifier-integration.md` for the `$task-clarifier` boundary. Read `references/examples.md` for typical usage.

## Safety Defaults

- Store no secrets, tokens, passwords, private keys, verification codes, or credentials.
- Send sensitive experiences, health, religion, politics, finance, identity, intimate history, and similar content to proposal or redaction paths.
- Current user statements override stored profile data.
- Treat the profile as collaboration support and need-alignment evidence.
