# LLM-KMS — prune

`/llm-kms prune` — move stale notes to the L3 cold archive.

## Conventions

**Folder layout** — namespace folders live directly under the repo root (no `wiki/`
container). A note with `namespace: "Tech/AI"` lives at `Tech/AI/<ID>.md`. Every namespace
folder (leaf *and* domain root) holds two control files: `index.md` + `log.md`.

**Archive rules** — `archive/` (Layer ④) is LLM-owned cold storage for notes with
`status: archived`. An archived note's file moves to `archive/`, keeping its frontmatter
and ID intact, and its entry is removed from the namespace `index.md` page table.

## Procedure

1. Read `log.md` files to find each note's last-access/last-touch date.
2. Identify notes untouched for > 6 months.
3. Move the file to `archive/`, set `status: archived`, bump `updated`.
4. Remove the archived entries from the relevant `index.md` page tables.
5. Append a `| YYYY-MM-DD | prune | <subject> | <N archived> |` line to the affected `log.md` files.
6. Report how many notes moved to L3.
