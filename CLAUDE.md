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

## Development workflow

### Branches

- `main` — always releasable, single long-lived branch
- Feature branches: `<plugin>/<description>`, `fix/<description>`, `docs/<description>`, `new/<plugin>`
- Squash merge only — PR title becomes the commit message

### CI validation

Every PR and push to main runs `.github/scripts/validate.sh` + gitleaks secret scan.

What CI checks:
1. All `plugin.json` — valid JSON, required fields (name, version, description, author), semver, dir name matches name field
2. `marketplace.json` — valid JSON, source paths exist, bidirectional sync with plugin dirs
3. `SKILL.md` — YAML frontmatter has `name:` and `description:`, warns on unquoted `: `
4. Every plugin dir has at least one skill or agent

### Local validation

```bash
bash .github/scripts/validate.sh
```

### Release process

Tag with `<plugin>-v<version>` (e.g. `plugin-lazy-v1.0.0`). Version in tag must match `plugin.json`.

Pushing a tag triggers `.github/workflows/release.yml` which validates the tag, checks version match, runs `validate.sh`, and creates a GitHub Release with auto-generated notes.

## Cache refresh

After plugin edits, users must run `/plugin update operator47-plugins` for installed instances to pick up changes.
