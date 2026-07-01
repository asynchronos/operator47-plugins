# LLM-KMS — lint

`/llm-kms lint` — health-check the knowledge graph (4 checks).

## Conventions

**Link format** — links use `[[ID]]` where `ID` is the note-ID filename (no `.md`
extension): 17 digits by default, or 25 digits (+8 random) if this wiki uses
`ID_RANDOM_SUFFIX` for concurrent multi-agent writes.

**Orphan** — empty `links_to` AND no inbound link from any other note → considered "dead"
by Zettelkasten standards.

**Folgezettel** — the parent/child relationship between a `Domain/SubDomain` namespace and
its `Domain` root; broken when a `Domain/SubDomain` note exists but no parent
`Domain/index.md` does.

## Procedure

**MCP alternative:** call the `lint()` tool and report its output — this replaces running
the script below.

Run this script from repo root:

```bash
python - <<'PY'
import re, glob, os
from collections import defaultdict

ID_PATTERN = r"\d{17}(?:\d{8})?"

def get_links(fm):
    m=re.search(r'^links_to:\s*\[(.+)\]',fm,re.M)
    if m: return re.findall(rf'\[\[({ID_PATTERN})\]\]',m.group(1))
    m=re.search(r'^links_to:\s*\n((?:[ \t]+-[^\n]+\n?)*)',fm,re.M)
    if m: return re.findall(rf'\[\[({ID_PATTERN})\]\]',m.group(1))
    return []

notefiles=[f for f in glob.glob("**/*.md",recursive=True)
           if re.fullmatch(ID_PATTERN, os.path.splitext(os.path.basename(f))[0])]
notes={}
for f in notefiles:
    fm=open(f,encoding="utf-8").read().split("---",2)[1]
    g=lambda n:(re.search(rf"^{n}:\s*(.*)$",fm,re.M) or [None,""])[1].strip()
    nid=os.path.splitext(os.path.basename(f))[0]
    notes[nid]={"file":f,"ns":g("namespace").strip('"'),
                "links":get_links(fm),"id":g("id")}
ids=set(notes); inc=defaultdict(set)
for n,d in notes.items():
    for l in d["links"]: inc[l].add(n)
print("notes:",len(ids))
print("id-mismatch:",[n for n,d in notes.items() if d["id"]!=n] or "none")
print("broken refs:",[(n,l) for n,d in notes.items() for l in d["links"] if l not in ids] or "none")
print("orphans:",[n for n,d in notes.items() if not d["links"] and not inc[n]] or "none")
miss=[]
for ns in {d["ns"] for d in notes.values()}:
    if "/" in ns:
        domain=ns.split("/")[0]
        if not os.path.exists(os.path.join(domain,"index.md")): miss.append(ns)
        if not os.path.exists(os.path.join(domain,"log.md")):
            print("MISSING control file:",os.path.join(domain,"log.md"))
print("broken folgezettel:",miss or "none")
for ns in {d["ns"] for d in notes.values()}:
    for c in ("index.md","log.md"):
        p=os.path.join(*ns.split("/"),c)
        if not os.path.exists(p): print("MISSING control file:",p)
PY
```

1. **Broken Refs** — `[[ID]]` links pointing to non-existent files (script: `broken refs`).
2. **Orphan Notes** — empty `links_to` AND no inbound link → "dead" by Zettelkasten standards.
3. **Contradictions** — notes in the same namespace making mutually inconsistent claims.
   The script can't detect these; read same-namespace notes and judge semantically.
4. **Broken Folgezettel** — a `Domain/SubDomain` note with no parent `Domain/index.md`.

**On a Contradiction → record, then STOP.** Do not auto-resolve. Invoke the Human-in-the-Loop rule:
1. On **both** notes: set `status: contested` + `contested_by: [[other_ID]]` (reciprocal), and add a
   `## Contradiction` body block — `⚠️ Conflicts with [[ID]] (flagged YYYY-MM-DD)`, then each side's claim.
2. Present both note IDs and the conflicting claims; ask the user "Which is correct? A, B, or neither?".
3. On the ruling: clear `contested_by` and delete the `## Contradiction` block on both; mark the loser
   `status: superseded` + `superseded_by: [[winner_ID]]`; the winner returns to `status: active`.

The note never leaves its namespace folder — `contested` is a field state, not a move.
