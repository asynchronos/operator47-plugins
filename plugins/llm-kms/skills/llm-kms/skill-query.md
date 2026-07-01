# LLM-KMS — query

`/llm-kms query <question>` — answer from the wiki using two-stage routing.

## Conventions

**Folder layout** — namespace folders live directly under the repo root (no `wiki/`
container). A note with `namespace: "Tech/AI"` lives at `Tech/AI/<ID>.md`. Every namespace
folder (leaf *and* domain root) holds two control files: `index.md` + `log.md`.

**Link format** — links use `[[ID]]` where `ID` is the note-ID filename (no `.md`
extension): 17 digits by default, or 25 digits (+8 random) if this wiki uses
`ID_RANDOM_SUFFIX` for concurrent multi-agent writes.

## Procedure

1. **Stage 1 (route)** — read the root `index.md` and relevant namespace `index.md` files.
   Use the one-line summaries to pick candidate note IDs. Do **not** load every note.
2. **Stage 2 (load)** — read the full content of only the selected notes.
3. **Synthesize** an answer grounded in those notes, citing each claim with its `[[ID]]`.
   If the wiki lacks the answer, say so — do not invent. Suggest an `ingest` if the source
   exists in `raw/`/`inbox/`.

## MCP alternatives

| Step | Filesystem | MCP alternative |
|---|---|---|
| Query the wiki | Read index.md files, load notes, synthesize | Call `query(question)` → returns synthesized answer |
| Contribute new knowledge | Write markdown doc to `inbox/` | Write markdown doc to `inbox/` (same) |

The auto-log (`inbox/QUERY-<ID>.md`) is written server-side by `auto_log_query()`
on every `query()` tool call — the consuming agent does not need to do this manually.

**Key invariant:** after a query, if the agent has new knowledge to contribute, it
writes a new document to `inbox/` and waits for `ingest` to process it. It does NOT
call `write_note()` directly. `write_note()` is an internal step within `ingest`, not
a consumer-facing action.
