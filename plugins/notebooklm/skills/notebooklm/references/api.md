# notebooklm-py API reference (verified)

Verified against `teng-lin/notebooklm-py` source — v0.6.0 (released 2026-05-29),
cross-checked against a v0.5.x flow that ran live. PyPI `notebooklm-py`, import
`notebooklm`, CLI `notebooklm`. Async library over NotebookLM's internal
batchexecute RPC. **Unofficial** — see [legal.md](legal.md).

`nlm.py` calls everything **by keyword** and probes for version differences, so it
works on both 0.5.x and 0.6.x. The notes below explain why each defensive choice exists.

## Client / auth

```python
from notebooklm import NotebookLMClient

# 0.6.x: from_storage is `async def` -> must be awaited.
# Full signature: from_storage(path=None, timeout=30.0, profile=None)
async with await NotebookLMClient.from_storage(path=None, timeout=30.0, profile=None) as client:
    ...
```

- ⚠️ **Version difference (important):** in **0.6.x** `from_storage` is `async def`
  and **must be awaited** (`async with await NotebookLMClient.from_storage() ...`).
  In **0.5.x** it was a sync classmethod returning the client directly (no `await`).
  `nlm.py` resolves this at runtime with `inspect.isawaitable(...)` and awaits only
  when needed — do the same in any new code instead of hard-coding one form.
- Auth resolution order: explicit `path=` > `NOTEBOOKLM_AUTH_JSON` env >
  profile's `storage_state.json` (default `~/.notebooklm/profiles/default/storage_state.json`).
  There is **no Python login API** — seed auth once via the CLI `notebooklm login`.
- Sub-APIs on the client: `notebooks`, `sources`, `artifacts`, `chat`, plus
  `research`, `notes`, `settings`, `sharing`, and `refresh_auth()`.

## Notebooks

```python
await client.notebooks.list()        # -> [nb, ...] each with .id, .title
await client.notebooks.create(name)  # -> nb with .id  (positional name)
```

`nlm.py` does **find-or-create by exact title** so re-runs reuse the same notebook.

## Sources

```python
await client.sources.add_text(notebook_id, title, content, *, wait=False,
                              wait_timeout=120.0, idempotent=False)   # -> Source(.id,.title,.is_ready)
await client.sources.add_url(notebook_id, url, wait=False, wait_timeout=None)   # auto-detects YouTube
await client.sources.add_file(notebook_id, file_path, wait=False, wait_timeout=None)  # PDF/TXT/MD/EPUB/DOCX
```

- Default is `wait=False`; `nlm.py` passes `wait=True` so a source is ready before
  generation. (`idempotent=True` raises `NonIdempotentRetryError` for text — leave it off.)
- ⚠️ **NotebookLM does not accept raw CSV.** Convert tabular data to a Markdown
  table first (see `data_adapter.py` / [examples.md](examples.md)).
- Source listing for idempotency isn't guaranteed across versions; `nlm.py`
  probes `client.sources.list(nb_id)` / `nb.sources` and falls back to "cannot
  enumerate" (may duplicate on re-run) rather than guessing.

## Chat

```python
res = await client.chat.ask(notebook_id, question, conversation_id=None, source_ids=None)
res.answer          # str
res.references      # [ref, ...] each: .source_id, .citation_number, .cited_text
res.conversation_id, res.turn_number
```

## Artifacts — generation (non-blocking)

```python
await client.artifacts.generate_report(
    notebook_id, report_format=ReportFormat.BRIEFING_DOC, source_ids=None,
    language="en", custom_prompt=None, extra_instructions=None)        # -> GenerationStatus

await client.artifacts.generate_infographic(
    notebook_id, source_ids=None, language="en", instructions=None,
    orientation=None, detail_level=None, style=None)                   # -> GenerationStatus
```

- ⚠️ **Positional order is NOT what you'd guess** (e.g. infographic is
  `source_ids, language, instructions, orientation, detail_level, style`). Always
  pass these **by keyword** — `nlm.py` does. Then param order is irrelevant.
- `report_format` defaults to `BRIEFING_DOC`. For `ReportFormat.CUSTOM`, supply the
  prompt via `custom_prompt=` (not `extra_instructions=`). `nlm.py` maps `--topic`
  to `custom_prompt` when `--report-format custom`, else to `extra_instructions`.

### GenerationStatus

Fields: `task_id` (**== artifact_id**), `status` (`pending`|`in_progress`|`completed`|`failed`|`not_found`|`removed`), `url`, `error`, `error_code` (e.g. `USER_DISPLAYABLE_ERROR`), `metadata`.
Properties: `.is_complete`, `.is_failed`, `.is_pending`, `.is_in_progress`,
`.is_not_found`, `.is_removed`, `.is_rate_limited`.

- ⚠️ Rate-limit/quota rejection comes back as a **status** (`is_failed` /
  `is_removed` / `is_rate_limited`), **not** an exception. `nlm.py` checks these
  before waiting. `.is_removed` (a delisted artifact) is distinct from `.is_failed`.

## Artifacts — poll & download

```python
final = await client.artifacts.wait_for_completion(notebook_id, task_id, timeout=300.0)  # raises ONLY TimeoutError
await client.artifacts.download_report(notebook_id, output_path, artifact_id=task_id)      # -> path (Markdown)
await client.artifacts.download_infographic(notebook_id, output_path, artifact_id=task_id) # -> path (PNG)
```

- `wait_for_completion` raises **only** on timeout; for `failed`/`removed`/`not_found`
  it **returns** the terminal status — check `final.is_complete`. It also accepts
  tuning kwargs (`initial_interval`, `max_interval`, `max_not_found`, `on_status_change`).
- Pass `artifact_id=task_id` to download the exact artifact you just generated
  (omitting it resolves "latest"). **task_id == artifact_id.**

## Enums

- ⚠️ **Import location differs:** 0.5.x re-exports enums at the top level
  (`from notebooklm import ReportFormat`); 0.6.x puts them under `notebooklm.rpc`.
  `nlm.py` tries top-level first, then `notebooklm.rpc`.

| Enum | Members |
|---|---|
| `ReportFormat` | `BRIEFING_DOC`, `STUDY_GUIDE`, `BLOG_POST`, `CUSTOM` (str-enum) |
| `InfographicOrientation` | `LANDSCAPE`, `PORTRAIT`, `SQUARE` |
| `InfographicDetail` | `CONCISE`, `STANDARD`, `DETAILED` |
| `InfographicStyle` | `AUTO_SELECT`, `SKETCH_NOTE`, `PROFESSIONAL`, `BENTO_GRID`, `EDITORIAL`, `INSTRUCTIONAL`, `BRICKS`, `CLAY`, `ANIME`, `KAWAII`, `SCIENTIFIC` |

Audio/Video/Quiz/etc. enums and signatures are in [capabilities.md](capabilities.md).

## Windows gotcha

notebooklm-py needs the **SelectorEventLoop** on Windows (the default
ProactorEventLoop can hang under httpx). `nlm.py` runs with
`asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)` on Python 3.12+
(falls back to `WindowsSelectorEventLoopPolicy` on older). It also reconfigures
stdout to UTF-8 to avoid `UnicodeEncodeError` printing Thai/emoji on cp874/cp932.

## Sources

- https://github.com/teng-lin/notebooklm-py — `src/notebooklm/_artifacts.py`, `rpc/types.py`, `_types/artifacts.py`
- https://pypi.org/project/notebooklm-py/ — version 0.6.0 (2026-05-29)
- https://context7.com/teng-lin/notebooklm-py
