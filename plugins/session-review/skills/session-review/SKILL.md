---
name: session-review
description: "Review the current chat session — surface what's open, pending, or at risk. Default: report only, continue working. With --handoff: show a handoff draft and ask before writing .claude/handoff.md."
---

# Session Review

Two modes:

- **Default** — print the session report and stop. User keeps working; nothing is written.
- **`--handoff`** — print the same report, then show a handoff draft, then ask the user to confirm before writing `.claude/handoff.md`. The file is never written without explicit user confirmation.

## Procedure

### Step 1 — Resolve root and gather git state

```powershell
$root = git rev-parse --show-toplevel 2>$null; if (-not $root) { $root = $PWD.Path }
$slug = Split-Path $root -Leaf
$branch = git -C $root rev-parse --abbrev-ref HEAD 2>$null
git -C $root status --short
git -C $root log --oneline -10
git -C $root log '@{u}..HEAD' --oneline 2>$null
git -C $root stash list
```

```bash
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
SLUG=$(basename "$ROOT"); BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
git -C "$ROOT" status --short
git -C "$ROOT" log --oneline -10
git -C "$ROOT" log '@{u}..HEAD' --oneline 2>/dev/null
git -C "$ROOT" stash list
```

No git repo: note it, skip all git rows in the report.

### Step 2 — Scan project signal files

Auto-detect each; skip silently if absent.

- **.claude/handoff.md** — if found, show "↩ Previous handoff: <Written date> — <Start here line>" at the top of the report
- **TODO.md** (root and `docs/TODO.md`) — unchecked items (`^- \[ \]`), status table
- **inbox/** — files excluding `.gitkeep`
- **Log files** — `log.md`, `docs/log.md`, `notes/log.md`, `wiki-content/log.md` — last 3–5 entries, 1–3 lines each
- **index.md** — `## Now` section if present
- **Harness signals** (no I/O) — TodoWrite list state; `<ide_opened_file>` paths from this session

### Step 3 — Scan conversation

Look only for items that would be **lost on close**:

- **Open offers** — assistant said *"Want me to..."* / *"Should I..."* and user never confirmed
- **Deferred items** — *"noted for later"*, *"skip for now"*, *"out of scope"* — quote verbatim
- **State drift** — counts or dates changed in-session but not yet in any file — cite both values
- **Unexercised rules** — rule added to a file this session but never applied

Surface only items with quotable evidence. When unsure: "may still be open — confirm?"

### Step 4 — Print report

One labeled row per finding; inline evidence in `[brackets]`. **Omit any row with zero findings.**

```
SESSION REVIEW — <slug>  <YYYY-MM-DD HH:MM>  branch: <branch>
↩ Previous handoff: <date — "Start here" line>  (if .claude/handoff.md exists)
AT RISK ON CLOSE: <N>  ────────────────────────────────────────

DONE     <sha> <title>  ·  <sha> <title>                [in-git]
FLIGHT   M <file> [tracked]  ·  ?? <file>         [chat-only ⚠]
OFFERS   "<verbatim offer>"                             [chat-only]
DEFER    <item> — <source:line or quote>                  [<tag>]
DRIFT    <file>:<line> "<stale>" → actual: <current>    [in-TODO]
NEXT     1. <concrete action>   2. <action if needed>    (max 2)
```

Tags: `[in-git]` `[in-TODO]` `[in-log]` `[in-inbox]` survive close on their own. `[chat-only]` items are **lost on close** and drive the AT RISK count.

**Default mode:** stop here. Do not chain, propose edits, or ask anything.

### Step 5 — Handoff draft + confirm (--handoff only)

After printing the report, show the handoff draft the user would be saving:

```
─── HANDOFF DRAFT ──────────────────────────────────────────────
# Handoff — <slug>
Written: <YYYY-MM-DD HH:MM>  Branch: <branch>

## Start here
<NEXT item 1 verbatim>

## At risk on close
<all [chat-only] findings, one per line — or: none>

## Git snapshot
Uncommitted: <git status --short, or "clean">
Unpushed:    <git log @{u}..HEAD, or "none / no upstream">
────────────────────────────────────────────────────────────────
Write to .claude/handoff.md? Reply **yes** to confirm.
```

Stop and wait for the user's reply.

- **If yes:** create `<project-root>/.claude/` if absent, write (overwrite) `.claude/handoff.md` with the exact draft shown above. Print `Handoff written: .claude/handoff.md`. If `.claude/handoff.md` is not in `.gitignore`, note it.
- **If no / anything else:** discard, do nothing.

## Rules

1. **Never write any file without explicit user confirmation.** The handoff file is written only on "yes" reply in --handoff mode.
2. **Every finding cites evidence** — file:line, git output, or verbatim conversation quote. No evidence → drop it.
3. **NEXT is capped at 2 items**, each concrete. "Review the code" is not concrete; "finish auth middleware at src/auth.ts:47" is.
4. **Degrade silently** on missing signals — absent files, no git, no open items — all fine.
5. **No credentials or PII in the handoff file.**

## Common Pitfalls

**Skipping Step 3.** Git and file checks may be clean while unanswered offers remain in chat — the conversation scan is the most easily missed signal.

**Treating TodoWrite as authoritative.** Surface disagreement: *"TodoWrite: completed; disk: file still shows old value"*.

**Padding NEXT beyond 2 items.** Force the ranking — if everything is priority 1, nothing is.

## Verification

1. Every finding row has inline evidence (sha, file:line, or quote).
2. NEXT has at most 2 items, each a concrete action.
3. **Default mode:** no file was written, no question was asked.
4. **--handoff mode:** draft was shown before any write; file was written only after user said yes.
