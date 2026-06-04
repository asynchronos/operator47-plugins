#!/usr/bin/env python3
"""SessionStart hook: inject an auto-generated index of DISABLED plugins.

Ships inside the ENABLED plugin-lazy. Once per session (and after auto-compaction)
it makes installed-but-disabled plugins VISIBLE to the model — cheaply — so the
model can recognise intent semantically and route a request into the right plugin,
WITHOUT keeping the disabled plugins' full skill/agent definitions in context.

Why this exists: native skill auto-invocation only works for ENABLED plugins
(their name+description must be in context). A disabled plugin is invisible, so a
request like "create a python venv" gets hand-rolled from scratch instead of using
the disabled python-venv skill. This hook injects a compact ~one-line-per-item
index (~50 tokens each, regardless of how large the real plugin is) so you can keep
expensive plugins installed-but-disabled — and discoverable — instead of deleting
them to save context.

Two routes, by plugin type:
  - skills-only  -> lazy-load INLINE via plugin-lazy Step 4 (no enable, no restart)
  - agent-heavy  -> enable + restart via plugin-lazy Step 5 (agents only load at
                    session start, so they cannot run inline)

Output contract (verified against https://code.claude.com/docs/en/hooks):
  {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "<text>"}}

Fail-open: on ANY error, emit an empty object and exit 0 so a broken hook never
blocks a session. Pure stdlib (no PyYAML) so it runs on a bare Python.
"""

import json
import os
import sys

# Chars of a description kept as the "use-when" trigger. Big enough to preserve
# discriminating detail (incl. any "do not use for" clause) without bloating the
# index. Tunable: smaller = cheaper, larger = better routing.
DESC_MAX = 200
# Never advertise these (e.g. the loader itself).
SKIP_PLUGINS = {"plugin-lazy"}


def config_dir():
    """Claude config dir, honoring CLAUDE_CONFIG_DIR, else ~/.claude (x-platform)."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".claude")


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def parse_frontmatter(skill_md_path):
    """Return (name, description) from a SKILL.md YAML frontmatter block.

    Minimal hand-rolled YAML supporting folded '>-' / literal '|' scalars, so the
    hook needs no PyYAML.
    """
    try:
        with open(skill_md_path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        return (None, None)
    if not text.startswith("---"):
        return (None, None)
    parts = text.split("---", 2)
    if len(parts) < 3:
        return (None, None)
    block = parts[1]

    name = None
    description = None
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if stripped.startswith("name:"):
            name = stripped[len("name:"):].strip().strip("'\"")
            i += 1
        elif stripped.startswith("description:"):
            val = stripped[len("description:"):].strip()
            if val in (">-", ">", "|", "|-", ">+", "|+", ""):
                base_indent = len(raw) - len(raw.lstrip())
                collected = []
                j = i + 1
                while j < len(lines):
                    nxt = lines[j]
                    if nxt.strip() == "":
                        j += 1
                        continue
                    indent = len(nxt) - len(nxt.lstrip())
                    if indent <= base_indent:
                        break
                    collected.append(nxt.strip())
                    j += 1
                description = " ".join(collected).strip().strip("'\"")
                i = j
            else:
                description = val.strip("'\"")
                i += 1
        else:
            i += 1
    return (name, description)


def short_trigger(description):
    """Short 'use-when' trigger from a description, preserving a negative guard.

    Keeps the first DESC_MAX chars; if a 'do not / not for / don't' clause exists
    further on, append it so negative discrimination survives truncation.
    """
    if not description:
        return "(no description)"
    desc = " ".join(description.split())
    if len(desc) <= DESC_MAX:
        return desc
    head = desc[:DESC_MAX].rsplit(" ", 1)[0]
    tail = desc[len(head):]
    guard = ""
    low = tail.lower()
    for marker in ("do not", "don't", "not for", "do **not**"):
        pos = low.find(marker)
        if pos != -1:
            clause = tail[pos:].split(".")[0].strip()
            if clause:
                guard = " | " + clause
            break
    return head + "..." + guard


def install_record(records):
    if not records:
        return None
    try:
        return sorted(records, key=lambda r: r.get("lastUpdated", ""))[-1]
    except Exception:
        return records[-1]


def is_disabled(key, enabled_map):
    return enabled_map.get(key) is not True


def list_dir(path):
    try:
        return sorted(os.listdir(path))
    except Exception:
        return []


def has_agents(install_path):
    agents_dir = os.path.join(install_path, "agents")
    if not os.path.isdir(agents_dir):
        return False
    for _root, _dirs, files in os.walk(agents_dir):
        if any(f.endswith(".md") for f in files):
            return True
    return False


def count_agents(install_path):
    n = 0
    agents_dir = os.path.join(install_path, "agents")
    for _root, _dirs, files in os.walk(agents_dir):
        n += sum(1 for f in files if f.endswith(".md"))
    return n


def plugin_description(install_path):
    pj = read_json(os.path.join(install_path, ".claude-plugin", "plugin.json")) or {}
    return pj.get("description") or ""


def build_index():
    cfg = config_dir()
    installed = read_json(os.path.join(cfg, "plugins", "installed_plugins.json"))
    settings = read_json(os.path.join(cfg, "settings.json")) or {}
    enabled_map = settings.get("enabledPlugins", {}) or {}
    if not installed:
        return None
    plugins = installed.get("plugins") or {}
    if not plugins:
        return None

    skills_entries = []  # (skill_name, trigger, plugin_key)
    agent_entries = []   # (plugin_name, trigger, plugin_key, n_agents)

    for key, records in plugins.items():
        if not is_disabled(key, enabled_map):
            continue
        bare_name = key.split("@", 1)[0]
        if bare_name in SKIP_PLUGINS:
            continue
        rec = install_record(records)
        if not rec:
            continue
        install_path = rec.get("installPath")
        if not install_path or not os.path.isdir(install_path):
            continue

        if has_agents(install_path):
            # Agent-heavy: agents register only at session start, so the skill
            # cannot run inline — advertise it as enable+restart instead.
            trigger = short_trigger(plugin_description(install_path))
            agent_entries.append((bare_name, trigger, key, count_agents(install_path)))
            continue

        skills_dir = os.path.join(install_path, "skills")
        for skill_subdir in list_dir(skills_dir):
            skill_md = os.path.join(skills_dir, skill_subdir, "SKILL.md")
            if not os.path.isfile(skill_md):
                continue
            name, desc = parse_frontmatter(skill_md)
            skills_entries.append((name or skill_subdir, short_trigger(desc), key))

    if not skills_entries and not agent_entries:
        return None

    skills_entries.sort(key=lambda e: e[0].lower())
    agent_entries.sort(key=lambda e: e[0].lower())

    out = []
    out.append(
        "DISABLED PLUGINS AVAILABLE ON DEMAND (auto-generated each session; their "
        "full skill/agent definitions are NOT loaded, to save context). If a user's "
        "request matches a use-when trigger below, do NOT improvise the procedure "
        "from scratch — use the routed plugin via plugin-lazy."
    )

    if skills_entries:
        out.append("")
        out.append("Lazy-loadable INLINE (skills-only; no enable, no restart):")
        for name, trigger, _key in skills_entries:
            out.append("- {0}: use when {1}".format(name, trigger))

    if agent_entries:
        out.append("")
        out.append("Require ENABLE + RESTART before use (agent-heavy; agents only "
                   "load at session start):")
        for name, trigger, key, n in agent_entries:
            out.append("- {0} ({1} agent(s)): use when {2}".format(name, n, trigger))

    out.append("")
    out.append(
        "To use one: for a skills-only entry, lazy-load it via the plugin-lazy "
        "skill (read plugin-lazy's SKILL.md and follow Step 4: read & execute the "
        "target SKILL.md from cache) — the plugin stays DISABLED, no settings "
        "change, zero ongoing context cost. For an agent-heavy entry, tell the user "
        "it needs `lazy enable <plugin>` + a session restart (plugin-lazy Step 5) "
        "before its agents are available; do not claim its agents work without a "
        "restart."
    )
    return "\n".join(out)


def main():
    try:
        sys.stdin.read()
    except Exception:
        pass
    try:
        index = build_index()
    except Exception:
        index = None
    if not index:
        print(json.dumps({}))
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": index,
        }
    }))


if __name__ == "__main__":
    main()
