# Examples / recipes

`python` below = `py` on Windows. Set the script paths once:

```bash
NLM="${CLAUDE_PLUGIN_ROOT}/skills/notebooklm/scripts/nlm.py"
DA="${CLAUDE_PLUGIN_ROOT}/skills/notebooklm/scripts/data_adapter.py"
```

## 0. Smoke test with the bundled demo (no real data, no real notebook needed for the file step)

```bash
# Feed the demo Markdown and generate both artifacts into ./notebooklm-output/
python "$NLM" run --notebook-title "NLM demo" --reuse \
    --file "${CLAUDE_PLUGIN_ROOT}/skills/notebooklm/assets/demo-data.md" \
    --language en
```

## 1. Turn a docs folder into a briefing + infographic

Any project with a `docs/` of Markdown (design docs, ADRs, READMEs):

```bash
python "$NLM" run --notebook-title "Project X docs" --reuse \
    --dir ./docs --glob "*.md" \
    --report-format briefing --style professional --orientation portrait --detail detailed \
    --language en --out-dir ./reports
```

Re-running is safe: the notebook is reused and already-added files are skipped;
only new/changed-title files are uploaded.

## 2. Refresh the report after editing docs (no re-upload)

```bash
python "$NLM" add --notebook-title "Project X docs" --dir ./docs --glob "*.md"   # adds only new titles
python "$NLM" generate --notebook-title "Project X docs" --language en
```

## 3. A dataset (CSV) → report

NotebookLM rejects raw CSV, so bridge it to Markdown first:

```bash
python "$DA" metrics.csv --title "Q2 metrics" --out metrics.md
python "$NLM" run --notebook-title "Q2 review" --reuse --file metrics.md \
    --question "What are the top 3 movements and likely causes?" \
    --report-format study --style bento
```

## 4. A "what changed" report from two snapshots

`data_adapter.py` emits NEW / GONE / +delta sorted by absolute change:

```bash
python "$DA" today.csv --prev yesterday.csv --key item,source --value price --out changes.md
python "$NLM" add --notebook-title "Daily diff" --file changes.md
python "$NLM" generate --notebook-title "Daily diff" --report-format briefing --no-infographic
```

## 5. Pull rows from a DB/API (no CSV) — use the library

```python
# your_export.py
import sqlite3
from data_adapter import dicts_to_markdown   # data_adapter.py is on sys.path / same dir

conn = sqlite3.connect("app.db")
rows = [dict(r) for r in conn.execute("SELECT name, region, price FROM items")]
md = dicts_to_markdown(rows, columns=["name", "region", "price"],
                       title="Item prices", right_align=["price"])
open("items.md", "w", encoding="utf-8").write(md)
```

```bash
python "$NLM" add --notebook-title "Catalog" --file items.md
```

## 6. Thai-language report from an existing notebook

```bash
python "$NLM" generate --notebook-title "Project X docs" --language th \
    --report-format briefing --style editorial --orientation portrait
```

## 7. Just ask questions (no artifacts)

```bash
python "$NLM" chat "Summarize the open risks and who owns each" --notebook-title "Project X docs"
```

## 8. Inline / piped source

```bash
printf '## Notes\n- decided to ship Friday\n- rollback plan in runbook\n' | \
    python "$NLM" add --notebook-title "Standup" --stdin --title "2026-05-30 notes"
```

## Tips

- `--topic "focus on cost trade-offs"` steers both the report (extra_instructions)
  and the infographic (instructions). With `--report-format custom`, `--topic`
  becomes the full report prompt.
- Use `--no-infographic` or `--no-report` to generate just one (infographics cost
  more quota).
- `--storage` / `--profile` pick a specific throwaway identity — handy when juggling
  more than one account.
- Outputs are stamped `report_YYYYMMDD.md` / `infographic_YYYYMMDD.png` in `--out-dir`.
