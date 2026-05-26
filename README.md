# operator47-plugins

Claude Code plugin marketplace by operator47. Context optimization and workflow automation plugins.

## Plugins

| Plugin | Category | Description |
|--------|----------|-------------|
| **plugin-lazy** | workflow | Lazy-load disabled plugins on demand. Reduce context window usage by keeping plugins disabled until you need them. |
| **session-review** | workflow | Review what's open, pending, or stale in the current chat session before closing or continuing. Surface-only — never edits any file. |
| **python-venv** | development | Set up a Python virtual environment (.venv) in the current project. Prefers uv, falls back to stdlib `python -m venv`. Handles requirements.txt, pyproject.toml, and .gitignore. |

## Install

In a Claude Code CLI session:

```
/plugin marketplace add https://github.com/asynchronos/operator47-plugins.git
/plugin install plugin-lazy@operator47-plugins
/plugin install session-review@operator47-plugins
/plugin install python-venv@operator47-plugins
```

Verify with `/plugin list`.

## plugin-lazy

Manages your Claude Code plugin context budget. Instead of loading every plugin at session start, disable the ones you don't use often and lazy-load them on demand.

**What it does:**

- **`lazy setup`** — guided wizard that classifies your plugins as always-on vs lazy-loadable, then disables the ones you pick
- **`lazy load <plugin>`** — reads a skills-only plugin from cache and runs it inline, without enabling it
- **`lazy enable <plugin>`** — enables an agent-heavy plugin (requires session restart)
- **`lazy disable <plugin>`** — disables a plugin so it stops consuming context

**How it works:** Skills-only plugins are read directly from the plugin cache and executed inline — no settings change, no restart. Agent-heavy plugins require toggling `enabledPlugins` in settings.json and a session restart because the Agent dispatcher only loads agents at startup.

**Context cost:** ~130 tokens when enabled (just the skill description in the frontmatter). The full 184-line procedure loads only when invoked.

## session-review

Takes stock of your current Claude Code session before you close or switch context. Produces a six-section report covering what's done, in-flight, deferred, and at risk of being lost.

**Sections:** Done This Session, In-Flight, Open Offers, Deferred, State Drift, Suggested Next — each with persistence tags (`[in-git]`, `[in-TODO]`, `[in-log]`, `[chat-only]`) so you can see at a glance what would survive closing the session.

**How to use:** Type `/session-review` or say "review the session", "what's open", "checkpoint before closing".

**Context cost:** ~80 tokens when enabled (just the skill description). The full procedure loads only when invoked.

## python-venv

Scaffolds a Python virtual environment in the current working directory, installs any project dependencies, ensures the venv is gitignored, and prints activation instructions.

**What it does:**

- Detects existing `.venv/` — offers Reuse / Recreate / Abort (never deletes without confirmation)
- Probes for `uv` on PATH — uses the fast path when available, falls back to stdlib `python -m venv`
- Creates `.venv/` (dot-prefixed, PEP 405 convention)
- Installs from `requirements.txt` and/or `pyproject.toml` (editable mode) if present
- Appends `.venv/` to `.gitignore` (idempotent — skips if already ignored)
- Prints a compact report: Python version, package count, activation hints for all three shells

**How to use:** Say "set up a Python venv", "create a virtual environment", or "scaffold venv for this project".

**Context cost:** ~80 tokens when enabled (just the skill description). The full 197-line procedure loads only when invoked.

## Init-once plugins and plugin-lazy

Some plugins are "init-once" — you invoke them to scaffold something, and then they have no reason to stay loaded. Keeping them enabled wastes context tokens on every subsequent turn. **plugin-lazy** solves this.

**Example: python-venv**

python-venv scaffolds a `.venv/` directory, installs dependencies, and prints activation hints. Once the venv exists, you don't need the plugin again until the next project. Instead of keeping it enabled:

```
lazy load python-venv    # loads the skill from cache, scaffolds the venv, exits
```

`lazy load` reads the skill directly from the plugin cache and executes it inline — no settings change, no session restart. The full 197-line procedure runs once, does its job, and the context window stays clean for the rest of the session.

**Which plugins benefit from lazy-loading?**

| Plugin | Pattern | Keep enabled? |
|--------|---------|---------------|
| **python-venv** | Scaffolds venv once per project | No — `lazy load` when needed |
| **session-review** | Invoked on demand, each session | Either — low context cost (~80 tokens) |
| **plugin-lazy** | Must be enabled to lazy-load others | Yes — always on |

**General rule:** If a plugin is skills-only and you use it less than once per session, disable it and `lazy load` on demand.

## Update

```
/plugin update plugin-lazy
/plugin update session-review
/plugin update python-venv
```

## Local development

1. Clone this repo.
2. Edit files under `plugins/<plugin>/`.
3. Bump `version` in `plugins/<plugin>/.claude-plugin/plugin.json` (semver).
4. Commit and push.
5. On each machine: `/plugin update <plugin>`.

## License

MIT
