---
name: learning-cycle
description: >-
  Run one Kolb experiential-learning cycle over a named subject
  (pipeline run, chat session, log file, git history, transaction record,
  or friction pattern). Observes evidence, writes action notes, distills
  patterns, surfaces numbered improvement proposals. Applies only on
  explicit consent. File-based memory persists across cycles
---

# Learning Cycle

Run one full **Kolb experiential-learning cycle** over a subject the user names and leave a measurable, auditable trail behind. Each invocation completes one full loop.

| Kolb phase | Skill step |
|---|---|
| Concrete Experience (CE) | Step 2–3: identify subject + gather evidence |
| Reflective Observation (RO) | Step 4: write dated action note |
| Abstract Conceptualization (AC) | Step 5: distill patterns |
| Active Experimentation (AE) | Step 6–7: emit proposals, apply on consent |

The skill produces a structured report with **numbered improvement proposals**, asks the user direct questions about the highest-leverage findings, and applies changes only when the user explicitly accepts via `AskUserQuestion`. Proposals are options. The user chooses.

## Scope

- **Reads**: project files, git history, logs, `.learning-cycle/` contents
- **Delegates**: evidence gathering to `Agent(general-purpose)` — writes evidence to `.learning-cycle/cycles/`
- **Writes (on consent only)**: `.learning-cycle/` files (config, memory, notes), accepted proposal edits, CLAUDE.md annotation
- **Never** writes without explicit user acceptance via `AskUserQuestion`

### Self-contained folder

All skill-generated files live in `.learning-cycle/` at the project root:

```
.learning-cycle/
  config.md        # user-editable defaults (subject, conventions)
  memory.md        # cross-cycle knowledge (append at top, cap reads at ~15)
  cycles/          # one folder per cycle — self-contained
    2026-05-27-001/
      evidence.md  # written by Agent (Step 3)
      action-note.md  # written by skill (Step 4)
```

On first run, the skill offers to create this folder and register it in `CLAUDE.md` so all future sessions know it exists. Cleanup: `rm -rf .learning-cycle/` removes everything.

## Procedure

### Step 1 — Load project context and bootstrap

Identify the project root and check for `.learning-cycle/`.

```powershell
$root = git rev-parse --show-toplevel 2>$null
if (-not $root) { $root = $PWD.Path }
$lcDir = Join-Path $root ".learning-cycle"
```

```bash
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
LC_DIR="$ROOT/.learning-cycle"
```

**If `.learning-cycle/` exists**: read its contents:
- `.learning-cycle/config.md` — extract default subject, evidence sources, project conventions
- `.learning-cycle/memory.md` — load the **last 15 cycle entries** only (reverse chronological, cap to prevent context bloat). Treat user-edited lines as ground truth — they override prior cycle entries on conflict.

**If `.learning-cycle/` does not exist (first run)**: use `AskUserQuestion` to offer bootstrapping:
- Options: "Create .learning-cycle/ folder", "Skip — run without persistence"
- If user accepts, create the folder structure:

  ```
  .learning-cycle/
    config.md      # empty skeleton with section headers
    memory.md      # empty with header
    notes/         # empty directory
  ```

- Then append a registration block to `CLAUDE.md` (create if absent) so all future sessions — including other plugins and agents — know the folder exists:

  ```markdown
  ## Learning Cycle

  This project uses the `learning-cycle` plugin. Cycle data lives in `.learning-cycle/`:
  - `config.md` — subject defaults, evidence sources, project conventions
  - `memory.md` — cross-cycle patterns and calibration (human-editable)
  - `cycles/` — one folder per cycle (evidence, action notes, each self-contained)
  ```

- If user declines, continue without persistence — the skill still runs the full cycle but skips Steps 4 and 8.

### Step 2 — Identify the subject

Determine what is being learned-from this cycle. Valid subjects:

- A **pipeline run** (logs, outputs, deviations from spec)
- The **current chat session** (assistant offers, deferrals, drift)
- A **log file** or set of log files
- Recent **git history** (a range of commits, a branch, a PR)
- **Transaction records** (database rows, audit log, queue events)
- A **recurring friction pattern** the user has noticed across runs

Resolution order:
1. If the user provided a subject in their invocation arguments, use it
2. If `.learning-cycle/config.md` has a `## Default subject`, propose it
3. If ambiguous, use `AskUserQuestion` with detected candidates

For the **session** subject: summarize the current conversation context (key exchanges, decisions, open items) into a structured brief — this will be passed to the evidence-gathering agent in Step 3 since the agent cannot see the main thread.

### Step 3 — Gather evidence (CE) — Agent delegation

Spawn an agent to gather evidence and write it to the cycle folder:

```
Agent({
  subagent_type: "general-purpose",
  description: "Gather learning-cycle evidence",
  prompt: <constructed from subject + evidence sources + config + output path>
})
```

The Agent prompt must include:
- Subject description from Step 2
- Evidence sources from `.learning-cycle/config.md` (or sensible defaults for the subject type)
- Specific instructions: read files, run `git log`/`git diff`, grep patterns, read logs
- Cap quotes at 1–3 lines each with citations (`file:line`, commit hash, log timestamp)
- For **session** subject: include the conversation brief from Step 2 as the primary evidence source
- Output path: `.learning-cycle/cycles/<YYYY-MM-DD>-<ID>/evidence.md`

The agent writes evidence to disk using this template:

```markdown
# Evidence — Cycle <ID> — <YYYY-MM-DD>

## Subject
- <one-line description>
- Type: <pipeline | session | log-file | git-history | transaction | friction>

## Findings

### <source-1 label>
- `<file:line>` or `<commit-hash>` — <one-line context>
  > <verbatim quote, 1-3 lines max>

### <source-2 label>
- `<file:line>` or `<commit-hash>` — <one-line context>
  > <verbatim quote, 1-3 lines max>

...

## Summary
- Total sources scanned: <N>
- Findings: <N items>
- Anomalies: <N items worth investigating>
```

If `.learning-cycle/` was not bootstrapped (user declined in Step 1), the agent returns evidence as text in its response instead of writing to disk. The skill continues with that text.

Evidence types by subject:

| Subject | Primary evidence | Commands |
|---------|-----------------|----------|
| pipeline | log files, exit codes, timing | `Read`, `Grep` on log paths |
| session | conversation brief from Step 2 | (passed in prompt) |
| log-file | the log file itself | `Read`, `Grep` for errors/warnings |
| git-history | commits, diffs, authors | `git log`, `git diff`, `git show` |
| transaction | database/audit records | `Read`, `Grep` on record files |
| friction | cross-session patterns | `.learning-cycle/memory.md`, `git log`, project files |

After the agent returns, read `.learning-cycle/cycles/<YYYY-MM-DD>-<ID>/evidence.md` to confirm it was written, then proceed to Step 4.

### Step 4 — Write dated action note (RO)

Write to the cycle folder created in Step 3: `.learning-cycle/cycles/<YYYY-MM-DD>-<ID>/action-note.md`. If `.learning-cycle/` was not bootstrapped (user declined in Step 1), skip this step.

**Each cycle's note lives alongside its evidence** — never overwrite prior cycles.

Note structure:
```markdown
# Action Note — Cycle <ID> — <YYYY-MM-DD HH:MM>

## Subject
- <subject description, inputs, context>

## What worked
- <concrete artifact citations from evidence.md>

## What surprised / broke / was slow / needed correction
- <concrete artifact citations from evidence.md>

## Artifacts referenced
- <file:line, commit hash, log excerpt>
```

### Step 5 — Distill patterns (AC)

Convert the evidence from Step 3 into generalizable **patterns** using the Decision Framework (below).

For each candidate pattern, record:
- **Title** — short, scannable
- **Pattern observed** — what kept happening or what hurt
- **Confidence** — `low` / `medium` / `high`
- **Scope** — which file, step, schema, or doc the pattern touches
- **Evidence pointer** — `file:line` / commit / quote from Step 3

Demote observations too noisy or one-off to **watch items** so they can mature across cycles.

Cross-reference `.learning-cycle/memory.md` (if loaded): patterns that recur across cycles gain confidence; patterns previously rejected by the user lose confidence.

### Step 6 — Emit proposals and report (AE)

Print the full structured report directly to the user using the Output Format below. For each high-confidence pattern, include a **proposal**:
- **Title**
- **Target file** — exact path
- **Change** — exact diff or precise description (not vague)
- **Confidence** — `low` / `medium` / `high`
- **Rationale** — one line tracing back to the evidence

After the proposals menu, surface **1–3 direct questions** about the highest-leverage findings — decisions the user must make before applying.

Then use `AskUserQuestion`:
- Question: "Which proposals do you want to accept?"
- Options: "Accept all", "Accept specific (list numbers)", "Modify a proposal", "Reject all"

**Do NOT apply anything before the user responds.**

### Step 7 — Apply accepted proposals or interview

Parse the user's response from Step 6:

**Accepted proposals** (`accept N` or equivalent):
- Apply via `Edit`/`Write`
- Print clear before/after for each change

**Modification requests** ("scope 3 to staging only", "what if we did Y?"):
- Stop and interview via `AskUserQuestion`:
  - The exact constraint being added
  - Whether it changes the target file, diff, or rationale
  - Whether other proposals are affected
- Re-emit the modified proposal as a new numbered option
- Ask for acceptance again

**Destructive proposals** (rename, delete, restructure):
- Even if accepted, require a **second confirmation** via `AskUserQuestion` before applying
- Show exactly what will be renamed/deleted/moved

**Rejections**: acknowledge and skip.

### Step 8 — Update memory

After applying (or after rejection/completion), update `.learning-cycle/memory.md`. If `.learning-cycle/` was not bootstrapped (user declined in Step 1), skip this step.

Append a new cycle entry **at the top** (reverse chronological):

```markdown
## Cycle <ID> — <YYYY-MM-DD>
- Subject: <what was learned-from>
- Patterns: <titles of patterns distilled>
- Proposals accepted: <N of M>
- Conventions confirmed: <any user-confirmed conventions>
- Calibration: <patterns rejected by user + reason, if any>
- Watch items carried: <titles>
```

Memory worth keeping across cycles:
- Subject locations (where pipelines run, logs land, notes live)
- Pattern categories that tend to be high-confidence vs. noisy
- Conventions the user has reaffirmed or overridden
- File locations and naming patterns
- Anti-patterns (proposals applied then reverted — capture reversion reason)
- Calibration data (when "high" was rejected, what made evidence misleading)

## Output Format

Print this structured report at Step 6 (verbatim section headers):

```
## Cycle <ID> — <YYYY-MM-DD>

### Subject
- <one-line description of what was learned-from>

### Evidence captured
- <path / commit / quote> — <one-line context>
- ...

### Action note
- <path to the appended note file>

### Patterns distilled
1. <title> — <confidence> — scope: <where it touches>
   Evidence: <pointer>
2. ...

### Proposals (options)
1. <title> — target: <file> — confidence: <low/med/high>
   Change: <exact diff or precise change description>
   Rationale: <one line tracing to evidence>
2. ...

### Key findings — please confirm
- <direct question 1 — the decision needed before applying>
- <direct question 2>

### Watch items
- <title> — <why deferred; what would promote it to a pattern>

### Next cycle focus
- <one suggestion for what to observe next time>
```

If a section is genuinely empty, mark it `none — verified by <evidence>`.

## Decision Framework

For each candidate pattern, ask in order:

1. **Is the evidence reproducible across at least one clear instance with concrete artifacts?** If no → watch item.
2. **Does the proposed change generalize beyond the specific incident?** If no → one-off fix; propose directly without elevating to "pattern."
3. **Does the proposal touch user-facing conventions or external interfaces?** If yes → mark confidence `low` or `medium` regardless of evidence strength.
4. **Otherwise** → emit as a numbered proposal at recorded confidence; wait for consent.

## Rules

1. **Never apply without explicit consent** via `AskUserQuestion`. Reading the user's mind is forbidden.
2. **Destructive moves require second confirmation** regardless of initial acceptance. Rename, delete, or restructure triggers a confirmation question, not the edit.
3. **Evidence over intuition.** Every pattern and proposal traces to a concrete observation. No "trust me" findings.
4. **Smallest viable change per proposal.** Surgical edits over rewrites. Multiple small proposals beats one sprawling one.
5. **Idempotent.** No new evidence → report "no new evidence; nothing to integrate this cycle." Never fabricate changes.
6. **Respect project conventions.** `CLAUDE.md`, `SCHEMA`, `PLAYBOOK` files override defaults.
7. **Degrade silently when `.learning-cycle/` is absent.** Offer to bootstrap on first run. If user declines, run without persistence (skip Steps 4 and 8).
8. **Append-only action notes.** Never overwrite a prior note.
9. **Never auto-commit or auto-push.** The skill writes files; the user decides when to commit.
10. **Cap memory reads at ~15 cycles** to prevent unbounded context growth.

## Common Pitfalls

**Session subject loses detail.** When the subject is "this chat session," the conversation must be summarized into a brief for the agent (Step 3) since the agent cannot see the main thread. Expect some loss of nuance — keep the brief structured and quote key exchanges.

**Evidence file quality varies.** The general-purpose agent writes `evidence.md` based on its judgment. If a proposal requires exact line numbers, verify by reading the target file directly at Step 7 before applying.

**Memory file growth.** `.learning-cycle/memory.md` grows with every cycle. Rule 10 caps reads at ~15 entries, but the file itself is unbounded. Periodically review and prune stale entries.

**Model quality varies.** This skill runs on the session's model. For highest analytical quality on complex subjects, invoke from an Opus session.

**Fabricating patterns from thin evidence.** A single log line is not a pattern. The Decision Framework requires reproducible evidence. When in doubt, demote to watch item.

## Verification

After the skill completes, verify:

1. Every section of the Output Format is non-empty OR marked `none — verified by <evidence>`.
2. Each pattern cites concrete evidence (file:line, commit, verbatim quote).
3. Each proposal specifies an exact target file and precise change.
4. `evidence.md` and `action-note.md` exist in `.learning-cycle/cycles/<cycle>/`.
5. `.learning-cycle/memory.md` was updated (or bootstrap was offered and declined).
6. No files were modified without explicit user consent via `AskUserQuestion`.

## Extensibility

All skill-generated files live in `.learning-cycle/` at the project root. Users teach the skill by editing files in this folder — no forking required.

### `.learning-cycle/config.md`

Subject defaults, evidence sources, project-specific conventions. Created during bootstrap (Step 1) with an empty skeleton:

```
# Learning Cycle Config

## Default subject
- <pipeline | session | log-file | git-history | transaction | friction>

## Evidence sources
- <ordered list of source kinds this project uses>

## Project conventions to respect
- <one-liners; override the skill's defaults>
```

### `.learning-cycle/memory.md`

The **human-readable face** of cross-cycle memory. Users may edit directly to teach the skill or correct stale entries. The skill reads it every cycle and treats user-edited lines as ground truth (overriding its own entries on conflict).

### `.learning-cycle/cycles/`

One folder per cycle, named `<YYYY-MM-DD>-<ID>/`. Each contains:
- `evidence.md` — written by `Agent(general-purpose)` in Step 3
- `action-note.md` — written by the skill inline in Step 4

Each cycle is self-contained. The skill never modifies a prior cycle's files.

### CLAUDE.md registration

On first bootstrap, the skill appends a `## Learning Cycle` section to the project's `CLAUDE.md` documenting what `.learning-cycle/` contains. This ensures all future sessions — including other plugins and agents — discover the folder without needing to scan for hidden directories.

### Cleanup

Remove everything: `rm -rf .learning-cycle/` and delete the `## Learning Cycle` section from `CLAUDE.md`.

### Downgrade to inline execution

To remove Agent delegation (simplify Step 3): replace the `Agent(general-purpose)` spawn with inline `Read`/`Grep`/`Bash` commands that write `evidence.md` directly. All other steps remain unchanged.
