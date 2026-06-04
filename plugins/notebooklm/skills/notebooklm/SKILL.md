---
name: notebooklm
description: >-
  Turn local Markdown/text/CSV into an AI-generated report (Markdown) and
  infographic (PNG) via Google NotebookLM, plus grounded Q&A over the same
  sources. Wraps the unofficial notebooklm-py library and is project-agnostic.
  Use when the user wants to summarize a docs set or dataset into a NotebookLM
  report or infographic, feed files/folders into NotebookLM as sources,
  generate a briefing / study-guide / blog from sources, ask questions grounded
  in their documents, or convert a CSV/table into a NotebookLM source.
argument-hint: [file-or-dir-of-sources]
allowed-tools: Bash(python *), Bash(python3 *), Bash(py *), Bash(pip *), Bash(notebooklm *), Read, Write
---

# NotebookLM report + infographic generator

Drive Google NotebookLM from the command line to turn local content into an
AI **report** (Markdown) and **infographic** (PNG), and to run **grounded Q&A**
over those sources. All logic lives in two portable scripts under
`${CLAUDE_PLUGIN_ROOT}/skills/notebooklm/scripts/` — nothing is tied to any
particular project; sources are just text/Markdown.

> ⚠️ **Unofficial + ToS risk.** This uses `notebooklm-py`, which drives
> NotebookLM's private internal API. Use a **throwaway Google account**, keep
> usage light, and only send non-sensitive content. Confirm with the user
> before the first live run. See [references/legal.md](references/legal.md).

## When to use / not use

- **Use** when the user wants a NotebookLM report/infographic from their docs or
  data, wants to load files into a notebook, or wants grounded answers from sources.
- **Don't use** for ordinary summarization you can do directly, or when the user
  has no NotebookLM/Google account to spare — offer a local alternative instead.

## Prerequisites (one-time)

Check setup first; if it fails, walk the user through
[references/setup.md](references/setup.md).

```bash
pip install -r "${CLAUDE_PLUGIN_ROOT}/skills/notebooklm/scripts/requirements.txt"
notebooklm login                      # opens a browser; sign in with a THROWAWAY account
notebooklm auth check --test --json    # expect {"status": "ok", ...}
```

On Windows use `py -m pip ...` and `py` instead of `python`. `notebooklm login`
needs `[browser]` (Playwright), already in requirements.txt.

## The CLI: `nlm.py`

Set a path variable once, then call subcommands. On Windows substitute `py` for `python`.

```bash
NLM="${CLAUDE_PLUGIN_ROOT}/skills/notebooklm/scripts/nlm.py"

python "$NLM" check                                   # verify auth + list notebooks
```

**End-to-end (most common)** — add sources from a folder, then generate both
artifacts into `./notebooklm-output/`:

```bash
python "$NLM" run --notebook-title "My Project Docs" --reuse \
    --dir ./docs --glob "*.md" \
    --language en --report-format briefing \
    --style professional --orientation portrait --detail detailed
```

**Add sources only** (best-effort idempotent — skips titles it can already see;
may duplicate if the installed version can't enumerate sources):

```bash
python "$NLM" add --notebook-title "My Project Docs" \
    --file ./summary.md --file ./data.md --dir ./docs --glob "*.md"
# also: --text "inline text" --title "Note"   |   ... | python "$NLM" add --stdin --title "Piped"
```

**Generate from an existing notebook** (no new sources):

```bash
python "$NLM" generate --notebook-title "My Project Docs" --language th \
    --report-format study --style bento --no-infographic
python "$NLM" generate --notebook-id <uuid> --question "Summarize the key risks" \
    --no-report --no-infographic   # question only; drop these flags to also get both artifacts
```

**Grounded Q&A:**

```bash
python "$NLM" chat "Which option is cheapest and why?" --notebook-title "My Project Docs"
```

### Key flags

- `--report-format` `briefing` | `study` | `blog` | `custom` (custom uses `--topic` as the prompt)
- `--style` one of: auto, sketch, professional, bento, editorial, instructional, bricks, clay, anime, kawaii, scientific
- `--orientation` landscape | portrait | square · `--detail` concise | standard | detailed
- `--language` e.g. `en`, `th` · `--topic "..."` steers report + infographic
- `--out-dir` (default `./notebooklm-output`) · `--timeout` seconds per artifact (default 600)
- `--no-report` / `--no-infographic` to generate just one
- `--storage <storage_state.json>` / `--profile <name>` to pick an auth profile

Generation is **non-blocking** under the hood: each artifact is requested, polled
to completion, then downloaded. Rate-limit/quota rejections are reported, not crashes.

## Feeding structured data (CSV / DB / API)

NotebookLM **rejects raw CSV** as a source — it must be Markdown. Use
`data_adapter.py` to bridge any tabular data into a Markdown table, then `add` it:

```bash
DA="${CLAUDE_PLUGIN_ROOT}/skills/notebooklm/scripts/data_adapter.py"
python "$DA" prices.csv --title "Daily prices" --out prices.md
python "$NLM" add --notebook-title "My Project Docs" --file prices.md
```

It can also emit a **"what changed"** table from two snapshots
(`--prev old.csv --key item,source --value price`). To pull rows from a DB/API
instead of CSV, import it: `from data_adapter import rows_to_markdown, dicts_to_markdown, diff_markdown`.
See [references/examples.md](references/examples.md). Templates to copy live in
[assets/source-template.md](assets/source-template.md) and
[assets/demo-data.md](assets/demo-data.md) (the demo lets you test `run` with no real data).

## More capabilities

`notebooklm-py` can also generate **Audio Overview, Video, Quiz, Flashcards,
Mind Map, Slide Deck, and a Data Table**, and export to Google Docs/Sheets — these
are **not wired into nlm.py** but are one call away. Exact signatures and how to
extend `_finish_artifact` for them are in
[references/capabilities.md](references/capabilities.md).

## References

- [references/setup.md](references/setup.md) — install, throwaway login, auth check, profiles, Windows notes
- [references/api.md](references/api.md) — verified notebooklm-py API + gotchas (version differences, task_id==artifact_id)
- [references/capabilities.md](references/capabilities.md) — implemented vs available-but-not-wired (audio/video/quiz/…)
- [references/examples.md](references/examples.md) — end-to-end recipes for common project types
- [references/legal.md](references/legal.md) — unofficial-API / ToS / account / privacy guidance
