---
name: session-review
description: Review the current chat session — surface what's open, pending, or stale before continuing or closing
---

# Session Review

Take stock of what's open, in-flight, deferred, or stale in the current chat session. Produce a six-section report with evidence cited per finding, then stop. The skill is **surface-only by contract** — it reads files, runs read-only commands, and prints findings. It never edits, commits, or auto-resolves anything.

## Procedure

Execute these steps in order. Each section of the final report cites evidence — never paraphrase a verdict.

### Step 1 — Identify project root

```powershell
$root = git rev-parse --show-toplevel 2>$null
if (-not $root) { $root = $PWD.Path }
Set-Location $root
```

```bash
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$ROOT"
```

If not in a git repo, fall back to cwd. Note the absence of git in the report ("Not a git repo — skipping git-state checks") and skip Step 3 entirely rather than repeating the error for each command.

### Step 2 — Scan harness signals (in-session, no I/O)

These signals are visible in the running skill's context — no commands needed:

- **TodoWrite list state.** If any todos are active, list each with its status (`pending` / `in_progress` / `completed`).
- **IDE-opened files.** If the conversation contains `<ide_opened_file>` system reminders, list the most recent path(s). These hint at where the user's attention is.

If neither signal is present, note "No harness signals captured."

### Step 3 — Scan git state

Run these read-only commands. Capture and quote output verbatim in the report:

```powershell
git status --short                         # uncommitted work
git log --oneline -10                      # recent commits this session
git log '@{u}..HEAD' --oneline 2>$null     # unpushed commits (if upstream configured)
git stash list                             # stashed work
```

```bash
git status --short
git log --oneline -10
git log '@{u}..HEAD' --oneline 2>/dev/null
git stash list
```

If `git log '@{u}..HEAD'` fails (no upstream), say so explicitly — don't silently skip.

### Step 4 — Scan project signal files

Auto-detect each. Skip silently if absent — no error noise.

**`TODO.md`** at project root and `docs/TODO.md`. For each found, extract:
- "Last updated:" header if present
- Status table (look for `| Layer | State |` or similar)
- Unchecked items (lines matching `^- \[ \]`)
- Checked items added recently (compare against git blame if cheap, else skip)

**`inbox/`** directory — list files excluding `.gitkeep`.

**Log files** — check `log.md`, `docs/log.md`, `notes/log.md`, `wiki-content/log.md`. For each found, read the last 3–5 entries (search for `^## \[` headers). Quote 1–3 lines per entry verbatim.

**`index.md`** — extract the `## Now` section if present.

### Step 5 — Scan conversation context

Review the current session for items the assistant surfaced but didn't land. Look specifically for:

- **Open offers** — Phrases the assistant used in THIS session: *"Want me to..."*, *"Should I..."*, *"Want me to commit?"*. An open offer is an assistant proposal that the user did not accept or confirm. Do NOT place prior-cycle text, deferred-but-named items, or to-do-style notes here — those belong in DEFERRED.
- **Deferred decisions** — Phrases used: *"noted for later"*, *"deferred"*, *"skip for now"*, *"out of scope"*. Quote the deferral verbatim with its rationale.
- **State-file drift** — When the assistant has seen counts/dates change but `TODO.md` or similar files still show the old values, flag the mismatch with both numbers cited.
- **Codified-but-unexercised rules** — When a rule was added to a wiki page, schema, or commands file but never applied in practice during the session, flag it as awaiting first-exercise.

These are *judgment calls* and the most error-prone part of the skill. Be conservative: only surface items where the evidence is concrete (a quotable line). When in doubt, prefer "I'm not sure if X is still open — user can confirm" over silently dropping it.

### Step 6 — Assemble, print, and stop

Six sections, in this exact order. Each section is non-empty OR explicitly marked `none — verified by <evidence>`.

**Persistence tagging — required on every bullet.** Tag each item with one of `[in-git]`, `[in-TODO]`, `[in-log]`, `[in-inbox]`, `[chat-only]`. The tag answers "if the chat closed right now, would this item survive?" Bullets tagged `[chat-only]` are the **at-risk-on-close** set. `[in-memory]` is intentionally **not** part of this vocabulary — Rule 7 forbids MEMORY.md cross-referencing.

```
SESSION REVIEW — <project name>  <YYYY-MM-DD HH:MM>
AT RISK ON CLOSE: <N items> — see [chat-only] tags below (or "none — all open work is in TODO.md/log/git/inbox")

DONE THIS SESSION
  Evidence: git log --oneline -10
  - [in-git] <commit-sha> <commit-title>     (or "none — git log shows no new commits")
  ...

IN-FLIGHT
  Evidence: git status --short
  - [in-git]     M  <file>     (uncommitted edits — tracked)
  - [chat-only] ?? <file>      (untracked — not yet in git, lost if discarded)
  ...

OPEN OFFERS
  Evidence: conversation excerpts (THIS session only)
  - [chat-only] "<verbatim assistant offer>" — from <approximate turn>
  ...

DEFERRED
  Evidence: log entries / TODO / inbox / conversation
  - [in-TODO]    <item> — TODO.md:<line>
  - [in-log]     <item> — <log-file>:<line>
  - [in-inbox]   <item> — inbox/<file>
  - [chat-only]  <item> — "<verbatim conversation quote>"
  ...

STATE DRIFT
  Evidence: file:line vs current reality
  Discard rule: items where current reality matches stated reality — drop. Cosmetic drift (e.g. stale "Last updated" header with correct body) — single-line tag as "cosmetic header drift only". The section reports actionable mismatches; everything else stays out.
  - [in-TODO] <file>:<line> shows <stale value>; current reality: <fresh value via <command>>
  ...

SUGGESTED NEXT (ranked by impact)
  1. [<persistence-tag>] <action>     (reason; affects: <files or systems>)
  2. ...
  (cap at 4)
```

Output the report to chat and stop. Do not chain into any other operation, propose edits, or write a report file. If the user wants to act on findings, they'll say so.

## Rules

1. **Surface-only — NEVER edit any file.** The skill is read + observe + report. Editing is the user's call.
2. **Never auto-commit, auto-push, or auto-`/lint`.** These are actions; the skill is read-only.
3. **Never silently dedupe or resolve ambiguous findings.** If two log entries seem contradictory, surface both with their evidence.
4. **Every claim cites evidence.** A finding without a quoted log entry, file:line reference, git-command output, or conversation quote is honor-system noise — discard or restate with evidence.
5. **Degrade silently when file-based signals are absent.** No `TODO.md`? Skip without comment. No `inbox/`? Skip. The skill works in any project.
6. **Cap signal scanning at obvious files.** Do not recurse into deep codebase exploration. Target: under 30 seconds.
7. **Honor "ignore memory" if active.** Don't apply remembered facts from prior sessions; only this session's signals count.
8. **One-call invocation.** The skill runs to completion in one pass. If the report is incomplete, say so explicitly in the relevant section.

## Common Pitfalls

**Treating the TodoWrite list as authoritative when it disagrees with disk state.** Both are signals; surface both. *"TodoWrite shows X as completed, but the file at <path> still contains <stale content>"* is exactly the kind of drift this skill catches.

**Reporting "nothing open" without scanning the conversation.** The git/file checks may pass while the assistant has unanswered offers hanging in the chat. The conversation scan in Step 5 is the most easily skipped part — and the most valuable.

**Mistaking "done this session" for "in-flight."** A commit landed but `TODO.md` wasn't refreshed → that's *state drift*, not in-flight work. Place it carefully.

**Quoting massive log entries.** Quote 1–3 lines max per entry. Long quotes drown the report.

**Conflating offers with confirmed commitments.** An "open offer" is something the assistant proposed and the user did not accept. If the user said "yes, do that," it's not an open offer — it's either in-flight or done.

## Verification

After the skill completes, verify:

1. **Every section is non-empty** OR explicitly marked `none — verified by <evidence>`.
2. **Each "open offer" / "deferred" item cites a verbatim quote** from the conversation or a log entry.
3. **State-drift items cite the stale field with current reality.** Example: `TODO.md:13 — "12 commits"; current reality: 16 commits`.
4. **Suggested-next items are concrete and ranked.** Vague like "review the wiki" doesn't cut it. Concrete: "refresh `TODO.md` status table (4 stale fields cited above)."
5. **STATE DRIFT items name a concrete action** or are tagged "cosmetic header drift only". Non-findings should be dropped per the discard rule.
