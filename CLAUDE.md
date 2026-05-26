# operator47-plugins

Claude Code plugin marketplace. Plugins live under `plugins/<name>/`.

## Layout

- `plugins/<name>/skills/` — invocable skills
- `plugins/<name>/agents/` — autonomous agents (when needed)
- `plugins/<name>/.claude-plugin/plugin.json` — manifest
- `.claude-plugin/marketplace.json` — registry of all plugins

## Plugin authoring

Re-derive current rules from Anthropic plugin-development public docs via WebFetch at the moment of authoring. Do not rely on cached copies.

## Gotchas

- YAML `description:` in SKILL.md — never put unquoted `: ` inside the value. The skill silently disappears from the loader.

## Cache refresh

After plugin edits, users must run `/plugin update operator47-plugins` for installed instances to pick up changes.
