---
name: llm-kms
description: Wiki Compiler Agent operations for this SSS-based Zettelkasten wiki. Routes the four standard operations by subcommand — `ingest <path>` (compile a raw/inbox document into atomic notes), `query <question>` (two-stage routed answer with [[ID]] citations), `lint` (broken refs / orphans / contradictions / broken Folgezettel), `prune` (archive stale notes to L3). Trigger on `/llm-kms <op> ...` and whenever the user asks to ingest a document into the wiki, query/answer from the wiki, lint/health-check the knowledge graph, or prune/archive old notes. CLAUDE.md at the repo root is the authoritative schema; this skill is its executable form.
---

# LLM-KMS — Wiki Compiler Agent Operations

You are the **Wiki Compiler Agent**. The repo-root `CLAUDE.md` is the authoritative
system schema; this skill is its executable form. Read `CLAUDE.md` if anything here is
ambiguous — the schema wins.

## Argument routing

The invocation argument is `<operation> [argument...]`. Each operation has its own
self-contained skill file — read only the one you need.

| First token | Per-op skill file | MCP resource | Argument |
|-------------|--------------------|--------------|----------|
| `ingest`    | `skill-ingest.md` | `llmkms://skill/ingest` | path to a file in `raw/` or `inbox/` |
| `query`     | `skill-query.md`  | `llmkms://skill/query`  | a natural-language question |
| `lint`      | `skill-lint.md`   | `llmkms://skill/lint`   | (none) |
| `prune`     | `skill-prune.md`  | `llmkms://skill/prune`  | (none) |

If the first token is none of these, show this table and ask which operation.

Each per-op file is bootstrapped alongside this router at
`.claude/skills/llm-kms/<per-op skill file>`. If it is missing, fetch it from the
matching MCP resource above.
