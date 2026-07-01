# LLM-KMS — ingest

`/llm-kms ingest <path>` — compile a raw document into the wiki.

## Conventions

**Folder layout** — namespace folders live directly under the repo root (no `wiki/`
container). A note with `namespace: "Tech/AI"` lives at `Tech/AI/<ID>.md`. Every namespace
folder (leaf *and* domain root) holds two control files: `index.md` + `log.md`.

**Five-layer lifecycle** (`inbox → raw → concept → archive`, with `system` cross-cutting).
Ownership is a per-layer attribute — these boundaries are never to be violated:
- `inbox/` ① — **human-owned, mutable** staging; read for `ingest`, don't treat as settled.
- `raw/` ② — **human-owned, IMMUTABLE** — read only, never write/modify (anti-hallucination anchor).
- Namespace folders ③ — **LLM-owned** — full read/write (L2 cache).
- `archive/` ④ — **LLM-owned**, cold store for `status: archived` notes (L3 cache).
- `CLAUDE.md` (repo root) + `system/` ⑤ — **co-owned** — change only with human approval.

**Note-ID file naming** — filename is the ID and only the ID. Default: `YYYYMMDDHHMMSSsss.md`
(UTC, millisecond precision, 17 digits). If this wiki uses `ID_RANDOM_SUFFIX` (concurrent
multi-agent writes — check `_config.py` if this wiki has a generated MCP server, or the
project's `CLAUDE.md`), append 8 random digits instead (25 digits total).
The title lives only in the `title:` frontmatter field.
Generate IDs from the real clock; for a batch of N, space them so each is unique:

```bash
python -c "import datetime,sys
n=int(sys.argv[1]); b=datetime.datetime.now(datetime.timezone.utc)
for i in range(n):
    t=b+datetime.timedelta(milliseconds=i*7)
    print(t.strftime('%Y%m%d%H%M%S')+f'{t.microsecond//1000:03d}', t.strftime('%Y-%m-%dT%H:%M:%S.')+f'{t.microsecond//1000:03d}Z')" N
```

Each line gives the `id`/filename (append 8 random digits per note if `ID_RANDOM_SUFFIX`
applies — `python -c "import secrets; print(f'{secrets.randbelow(10**8):08d}')"`) and the
matching ISO `created`/`updated` value.

**Frontmatter schema** — every concept page MUST carry exactly this block:

```yaml
---
id: YYYYMMDDHHMMSSsss          # equals filename without .md
title: "Human-readable title"
type: concept | entity | project | source | synthesis
namespace: "Domain/SubDomain"  # e.g. Tech/AI, Learning/PKM, Reference/Standard
tags: [domain/sub-tag]
created: YYYY-MM-DDTHH:MM:SS.sssZ
updated: YYYY-MM-DDTHH:MM:SS.sssZ   # bump on EVERY edit
source_ref: ["[[raw/path-to-source]]"]
links_to: ["[[ID]]"]           # explicit bidirectional links
confidence: 0.0-1.0            # from number of corroborating sources
status: active | contested | superseded | archived
superseded_by:                 # [[ID]] only when status: superseded
contested_by:                  # [[ID]] of conflicting note(s); set only when status: contested (reciprocal)
---
```

Body sections follow `system/templates/atomic-note.md`: `## Summary`, `## Details`,
`## Connections`, `## Open Questions`.

**Commit gate** — the repo has a gitleaks pre-commit hook. SSS IDs are already
allowlisted in `.gitleaks.toml`. Never bypass the hook with `--no-verify`; if it blocks,
fix the cause. Commit only when the user asks.

## Procedure

1. **Read the source fully** from `raw/` or `inbox/`. Never edit it.
2. **Identify 5–15 atomic knowledge units** — one idea per note. Pick `type` and the
   `namespace` (Domain/SubDomain) for each.
3. **Generate one SSS ID per new note** (batch snippet above).
4. **For each unit**, check the relevant namespace `index.md` for an existing related note:
   - **Exists** → update it in place; bump `updated`; keep `source_ref`; raise `confidence`
     if the new source corroborates.
   - **New** → create `<namespace>/<ID>.md` with full frontmatter + body sections.
5. **Link the graph** — set `links_to` so the new notes connect to each other and to
   existing notes. Make links reciprocal where the relation is mutual. **No orphans**:
   every note must end with ≥1 inbound or outbound link.
6. **Governance files:**
   - Ensure every touched namespace folder has `index.md` (page table: one line per note,
     `- [[ID]] | title | one-sentence summary`) and `log.md`.
   - **Folgezettel:** for any `Domain/SubDomain`, ensure the parent `Domain/index.md`
     exists and lists the sub-branch (create the domain-root MOC + its `log.md` if missing).
   - Append to each touched `log.md` (append-only): `| YYYY-MM-DD | ingest | <source> | <N notes> |`.
7. **Root registry** — add every new note to the root `index.md` global page table; append
   an entry to the root `log.md`.
8. **Verify** — run [§ lint](llmkms://skill/lint). Report a summary: notes created/updated,
   namespaces touched, lint result.

## MCP alternatives

| Step | Filesystem | MCP alternative |
|---|---|---|
| Read source | Read file directly | `ingest(source_path)` → returns content |
| Write note | Write `<ns>/<ID>.md` | `write_note(namespace, title, note_type, content, links_to, source_ref, confidence)` |
| Update index | Append row to `index.md` | `update_index(namespace_path, note_id, title, summary)` |
| Update log | Append row to `log.md` | `append_log(namespace_path, operation, subject, count)` |
| Promote source | Move file to `raw/` | `promote_to_raw(source_path)` |
| Run lint | Execute inline Python script | `lint()` → returns text report |
