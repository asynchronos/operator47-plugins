---
name: plugin-lazy
description: >-
  Lazy-load a disabled plugin on demand. Lists installed-but-disabled plugins,
  reads skills-only plugins from cache mid-session (no restart), or toggles
  agent-heavy plugins on/off (restart required)
---

# Plugin Lazy Loader

Load disabled plugins on demand without keeping them in every session's context window. Skills-only plugins are read directly from cache and executed inline. Agent-heavy plugins are toggled on and require a session restart.

## Procedure

### Step 1 — Resolve config paths and read plugin registry

Determine the Claude config directory: `$env:USERPROFILE\.claude` on Windows, `$HOME/.claude` on Unix/macOS. All paths below are relative to this directory.

Read two files to build the plugin catalog:

1. **Installed plugins:** `<config>/plugins/installed_plugins.json` — the `plugins` object has keys like `plugin-name@marketplace-name` with arrays of install records. Each record has `installPath`, `version`, and `scope`.
2. **Enabled plugins:** `<config>/settings.json` — the `enabledPlugins` object has keys like `plugin-name@marketplace-name` with boolean values.

If `installed_plugins.json` does not exist or has no entries, report "No plugins installed yet." and stop.

A plugin is **disabled** if it appears in `installed_plugins.json` but its `enabledPlugins` entry is either absent or `false`.

A plugin is **enabled** if its `enabledPlugins` entry is `true`.

### Step 2 — Detect mode

- User said "setup", "lazy setup", or "configure plugins" → go to **Setup Mode** (end of this file).
- User asked to **disable** an enabled plugin → go to Step 6.
- User named a specific plugin to load → skip to Step 4 (after classifying per Step 3).
- Otherwise → show the disabled-plugins catalog (Step 3).

### Step 3 — Present catalog

Display installed-but-disabled plugins:

```
DISABLED PLUGINS (installed, available on demand)
| # | Plugin | Type | Version | Marketplace |
|---|--------|------|---------|-------------|
| 1 | python-venv | skills-only | 0.1.1 | operator47-plugins |
...
```

To determine **Type**: check whether the `installPath` contains an `agents/` subdirectory with `.md` files. If yes: **agents+skills** (requires restart). If no: **skills-only** (can be lazy-loaded mid-session).

If no disabled plugins exist, report "All installed plugins are currently enabled." and stop.

After displaying, let the user pick one. Then classify:
- **skills-only** → Step 4
- **agents+skills** → Step 5

### Step 4 — Skills-only: lazy load from cache

The plugin stays disabled but its skill runs in the current session.

1. Resolve the `installPath` from the plugin's most recent install record.
2. List SKILL.md files at `<installPath>/skills/*/SKILL.md`.
3. If multiple skills exist, present them and let the user choose. If only one, proceed.
4. Read the chosen SKILL.md file using the Read tool.
5. **Follow the SKILL.md instructions exactly as written** — treat them as inline procedure instructions. Execute each step of the skill's procedure.
6. After completion, confirm: "Executed `<skill>` from disabled plugin `<plugin>`. Plugin remains disabled — no context cost."

No settings.json modification. The plugin stays disabled.

### Step 5 — Agent-heavy: enable and restart

Agent-heavy plugins cannot be lazy-loaded because the Agent tool dispatcher only recognizes agents from enabled plugins at session start.

1. Read `<config>/settings.json`.
2. Use the **Edit tool** to set `enabledPlugins["<plugin>@<marketplace>"]` to `true`. Do not rewrite the entire file — edit only the target key.
3. List the plugin's agents and skills (read from cache) so the user knows what becomes available.
4. Report: "Plugin `<plugin>` enabled. **Restart your session** for its N agents and M skills to load. Use `lazy disable <plugin>` when done to reclaim context."

### Step 6 — Disable a plugin

1. Read `<config>/settings.json`.
2. Use the **Edit tool** to set `enabledPlugins["<plugin>@<marketplace>"]` to `false`. Do not rewrite the entire file.
3. Report: "Plugin `<plugin>` disabled. It won't load in future sessions. Use `lazy load <plugin>` to access on demand."

For skills-only plugins, add: "Its skills can still be lazy-loaded mid-session without re-enabling."
For agent-heavy plugins, add: "Re-enabling requires a session restart for agents to load."

---

## Auto-index (SessionStart hook)

This plugin ships a `SessionStart` hook (`hooks/disabled_skills_index.py`, registered in `hooks/hooks.json`) that runs automatically while plugin-lazy is enabled — at session start, resume, clear, and after auto-compaction.

It reads the plugin registry and injects a compact, auto-generated index of every **disabled** plugin (one short "use-when" line each, ~50 tokens regardless of the plugin's real size), grouped by route:

- **skills-only** → lazy-load inline (Step 4), no restart
- **agent-heavy** → enable + restart (Step 5)

Effect: the model can **semantically** recognise a request that matches a disabled plugin and route into it, even though that plugin's full skill/agent definitions are not in context. This is what lets a request like "create a python venv" reach the disabled `python-venv` skill without the user typing `lazy load` first — and it is why expensive plugins can be kept **disabled but discoverable** instead of uninstalled.

The index is auto-derived from the live registry, so it always reflects the current disabled set with no manual maintenance. The hook fails open (emits nothing on any error) and never blocks a session. It provides **visibility only** — execution still goes through Step 4 / Step 5, and disabled plugins stay disabled (no settings change).

---

## Setup Mode

Guided post-install flow. Walks the user through all enabled plugins and helps them decide which to keep always-on vs lazy-load on demand. Invoke with `lazy setup`.

### Setup Step 1 — Build full plugin table

Using the registry data from Step 1, build a table of ALL installed plugins:

```
INSTALLED PLUGINS — context optimization guide
| # | Plugin | Type | Status | Context cost |
|---|--------|------|--------|--------------|
| 1 | plugin-lazy | skills-only | enabled | ~55 tokens |
...
```

To estimate **Context cost**: count skill descriptions (~50-100 tokens each) + agent definitions (~500-700 tokens each) by reading their files from cache.

To determine **Type**: check for `agents/` subdirectory in the install path.

### Setup Step 2 — Classify each plugin (cost × frequency)

Recommend **always-on** vs **disabled (on-demand)** based on **context cost × how
often it is used** — not on whether it is a "setup" tool.

Heuristic:
- Plugin is plugin-lazy itself → **always-on** (it's the loader)
- **Agent-heavy** (has `agents/`) → **keep DISABLED** (high cost, ~500-700 tokens/agent). The SessionStart auto-index keeps it discoverable; `lazy enable` + restart only when actually needed.
- **Skills-only, used in most sessions** → **always-on** (a skill description is cheap, ~50-380 tokens, and native auto-invoke is more reliable than any lazy nudge)
- **Skills-only, used occasionally** (init / setup / on-demand tools) → **keep DISABLED**; the auto-index surfaces it and it lazy-loads inline (no restart) when a request matches

Rule of thumb: enable only when a standing description cost is worth paying every
session for how often you use it; otherwise keep it disabled and let the auto-index
make it discoverable. **Prefer disable over delete** — a disabled plugin still
costs only ~one index line; an uninstalled one loses the capability entirely.

Present as suggestion, not decision. The user picks.

### Setup Step 3 — Ask user to confirm

Use `AskUserQuestion` with `multiSelect: true` to let the user pick which plugins to disable:

- List each enabled plugin (except plugin-lazy) as an option
- Mark recommended-to-disable plugins with "(recommended)" in the label
- Description: "Will not load at session start. Use 'lazy load <name>' to access on demand."

### Setup Step 4 — Apply and report

For each plugin the user selected to disable, use the **Edit tool** to set its `enabledPlugins` entry to `false` in settings.json. Batch into a single edit if possible.

Print a summary:

```
PLUGIN CONTEXT OPTIMIZATION COMPLETE

Disabled (lazy-loadable on demand):
  - python-venv (skills-only) — 'lazy load python-venv'
  - it-vendor-implementor (agents+skills) — 'lazy enable it-vendor-implementor' + restart

Still enabled (always-on):
  - plugin-lazy (~55 tokens)
  - session-review (~80 tokens)

Estimated context savings: ~Xk tokens per session
Changes take effect on next session restart.
```

---

## Rules

1. **Never uninstall.** Only toggle `enabledPlugins`. Never remove entries from `installed_plugins.json` or delete cache files.
2. **Never modify plugin source files.** Only `settings.json` is written to, and only the `enabledPlugins` object.
3. **Preserve settings.json structure.** Use the Edit tool for targeted key changes. Never rewrite the entire file.
4. **Skills-only lazy load is read-only on settings.** Step 4 does not touch settings.json.
5. **Agent-heavy path always requires restart.** Never claim agents are available without a restart.

## Common Pitfalls

**Plugin key format.** Keys use the format `plugin-name@marketplace-name`. Always use this exact format — do not omit the marketplace suffix.

**Multiple install records.** A plugin may have multiple entries in its array (different versions, scopes). Use the most recent one (last in array, or highest `lastUpdated` timestamp).

**Cache path may vary.** The `installPath` in `installed_plugins.json` is authoritative. Do not hardcode cache paths — always resolve from the registry.

**Skills that depend on agents.** Some skills in agent-heavy plugins assume they run within an agent context. If the user tries to lazy-load such a skill, warn them it may not function correctly without its agents. Recommend enabling the full plugin instead.

## Verification

After the skill completes, verify:

1. **Setup path:** all plugins listed with correct type; only user-selected plugins disabled; plugin-lazy itself never offered for disabling
2. **List path:** disabled plugins accurately listed with correct type
3. **Lazy-load path:** target SKILL.md read from cache and its procedure followed
4. **Enable path:** `settings.json` `enabledPlugins` shows the plugin as `true`
5. **Disable path:** `settings.json` `enabledPlugins` shows the plugin as `false`
6. **No side effects:** no settings.json keys other than the target `enabledPlugins` entry were modified
