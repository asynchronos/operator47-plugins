# Capabilities: implemented vs available-but-not-wired

`nlm.py` deliberately wires only the surface this skill was scoped to. The
underlying `notebooklm-py` (v0.6.0) can do much more — documented here with
**real, source-verified signatures** so you can extend the CLI when needed.

## Implemented in `nlm.py`

| Capability | Subcommand | Library calls |
|---|---|---|
| **Report** (Markdown) | `generate` / `run` | `generate_report` → `wait_for_completion` → `download_report` |
| **Infographic** (PNG) | `generate` / `run` | `generate_infographic` → … → `download_infographic` |
| **Grounded Q&A** | `chat` (and `--question`) | `chat.ask` |
| **Add sources** | `add` / `run` | `sources.add_text` (find-or-create notebook) |
| **CSV/table → source** | `data_adapter.py` | local; output fed via `add --file` |

## Available in the library, NOT wired into `nlm.py`

All of these are **non-blocking** and follow the exact same lifecycle as report/
infographic — so wiring one in is just: call `generate_*`, reuse `_finish_artifact`,
pass the matching `download_*`. Enums import from `notebooklm.rpc` (0.6.x) or the
top-level `notebooklm` (0.5.x).

### Audio Overview (podcast-style MP3)

```python
from notebooklm.rpc import AudioFormat, AudioLength
status = await client.artifacts.generate_audio(
    notebook_id, source_ids=None, language="en", instructions=None,
    audio_format=AudioFormat.DEEP_DIVE,   # DEEP_DIVE | BRIEF | CRITIQUE | DEBATE
    audio_length=AudioLength.DEFAULT,     # SHORT | DEFAULT | LONG
)
final = await client.artifacts.wait_for_completion(notebook_id, status.task_id, timeout=600)
if final.is_complete:
    await client.artifacts.download_audio(notebook_id, "overview.mp3", artifact_id=status.task_id)
```

No discrete "voice" enum — host/voice is implicit (driven by `language`, 50+
supported, and `instructions`). Output is MP3.

### Video Overview (MP4)

```python
from notebooklm.rpc import VideoFormat, VideoStyle
# generate_video(notebook_id, source_ids=None, language="en", instructions=None,
#                video_format=None, video_style=None, style_prompt=None)
# VideoFormat: EXPLAINER | BRIEF | CINEMATIC
# VideoStyle:  AUTO_SELECT, CUSTOM, CLASSIC, WHITEBOARD, KAWAII, ANIME,
#              WATERCOLOR, RETRO_PRINT, HERITAGE, PAPER_CRAFT
# download_video(notebook_id, output_path, artifact_id=None) -> MP4
```

### Quiz & Flashcards

```python
from notebooklm.rpc import QuizQuantity, QuizDifficulty
# generate_quiz(notebook_id, source_ids=None, instructions=None, quantity=None, difficulty=None)
# generate_flashcards(...)  same signature
# QuizQuantity: FEWER | STANDARD | MORE      QuizDifficulty: EASY | MEDIUM | HARD
# download_quiz / download_flashcards(notebook_id, output_path, artifact_id=None, output_format="json")  # json|markdown
```

### Study Guide

```python
# generate_study_guide(notebook_id, source_ids=None, language="en", extra_instructions=None)
# (thin wrapper over generate_report) -> download via download_report
# Equivalent in nlm.py today: `generate --report-format study`.
```

### Mind Map

```python
# generate_mind_map(notebook_id, source_ids=None, language="en", instructions=None)
#   -> returns a dict (persisted as a note), NOT a GenerationStatus
# download_mind_map(notebook_id, output_path, artifact_id=None) -> JSON
```

### Slide Deck

```python
from notebooklm.rpc import SlideDeckFormat, SlideDeckLength
# generate_slide_deck(notebook_id, source_ids=None, language="en", instructions=None,
#                     slide_format=None, slide_length=None)
# SlideDeckFormat: DETAILED_DECK | PRESENTER_SLIDES    SlideDeckLength: DEFAULT | SHORT
# download_slide_deck(notebook_id, output_path, artifact_id=None, output_format="pdf")  # pdf|pptx
# Also: revise_slide(...)
```

### Data Table (CSV out)

```python
# generate_data_table(notebook_id, source_ids=None, language="en", instructions=None)
# download_data_table(notebook_id, output_path, artifact_id=None) -> CSV
```

### Export to Google Docs / Sheets

```python
from notebooklm.rpc import ExportType
# export_report(notebook_id, artifact_id, title="Export", export_type=ExportType.DOCS)
# plus artifacts.list / delete / rename / share
```

### More source types

```python
await client.sources.add_url(notebook_id, url)     # web page; auto-detects YouTube
await client.sources.add_file(notebook_id, path)   # PDF / TXT / MD / EPUB / DOCX
```

`nlm.py` only uses `add_text`; adding `--url` / `--source-file` flags that call
these is straightforward.

## How to wire a new artifact into `nlm.py`

1. Add the enum import (top-level or `notebooklm.rpc`) and a `--…` flag.
2. In `_generate`, call `client.artifacts.generate_<x>(nb_id, …, language=…)`.
3. Reuse the existing helper:
   `await _finish_artifact(client, nb_id, status, client.artifacts.download_<x>, out_dir / f"<x>_{stamp}.<ext>", "<x>", args.timeout)`.

That helper already handles the non-blocking status check, `wait_for_completion`
(timeout-only raise), `is_complete` / `is_removed` / rate-limit, and download with
`artifact_id=task_id`.

> Notes: there is **no dedicated FAQ artifact** — use a briefing/study-guide report
> or `generate_data_table`. Signatures verified against v0.6.0; a future 0.6.x patch
> could tweak them — re-check `notebooklm.rpc` / `_artifacts.py` if a call 400s.
