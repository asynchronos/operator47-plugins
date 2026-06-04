# Unofficial-API, ToS & privacy guidance

> Not legal advice. This documents the risk so you and the user can make an
> informed choice before running anything live.

## The core risk

`notebooklm-py` drives **NotebookLM's private internal API** — there is **no
official public consumer API**. That means:

- It is **against Google's Terms of Service**. The account used can be
  **rate-limited, suspended, or banned**.
- The internal API can **change or break without notice**; calls may start
  failing after any NotebookLM update.
- Treat it as **best-effort, throwaway tooling**, not production infrastructure.

## Practices baked into this skill

1. **Throwaway Google account only.** Never authenticate with a primary/work
   Google identity. Keep a dedicated spare account for this. ([setup.md](setup.md))
2. **Light usage.** The free tier allows on the order of ~50 queries/day. Batch
   small, don't loop hard. Rate-limit/quota rejection returns as a status
   (`is_rate_limited` / `USER_DISPLAYABLE_ERROR`), which `nlm.py` reports rather
   than retrying aggressively.
3. **Confirm before the first live run.** Generation and source upload send your
   content to Google and consume quota — get explicit user go-ahead.
4. **Send only non-sensitive content.** Do not upload secrets, credentials, PII,
   or anything export-controlled/confidential. Once uploaded it lives in that
   Google account's NotebookLM.

## Privacy / data minimization

- Only feed what the report actually needs. For datasets, export **just the
  columns required** (e.g. via `data_adapter.py`) — strip names, emails, IDs, and
  other personal data before it becomes a source.
- Be mindful of jurisdiction-specific data-protection rules (e.g. GDPR/PDPA): if
  the source data contains personal data, you are sending it to a third party.

## Safer alternatives (when the risk isn't acceptable)

If a project can't take the ToS/account risk, prefer official/local paths and
skip this skill:

- **Report:** generate Markdown/HTML locally (e.g. a templating tool, or an
  official LLM API you have a license for).
- **Infographic:** an official image-generation API, or a charting library
  (Plotly/matplotlib) rendered to PNG.

This skill is best used for **proof-of-concept / personal** report+infographic
generation where NotebookLM's output quality is the goal and the account is
disposable.
