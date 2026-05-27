# Migration Notes: learning-cycle

## Architecture Change

| | Dev repo (agent) | Public repo (skill) |
|---|---|---|
| Plugin type | Agent (`agents/learner.md`) | Skill (`skills/learning-cycle/SKILL.md`) |
| Execution | Subagent with `memory: local` | Inline skill + `Agent(Explore)` delegation |
| Memory | Opaque `.claude/agent-memory-local/` | Transparent `.learning-cycle/` folder at project root |
| Model | Pinned to Opus via `model: opus` | Session model (user controls) |
| Version | 0.2.2 | 1.0.0 (clean break) |

## Why v1.0.0

The agent-to-skill conversion is a new architecture, not an evolution. The skill runs inline in the main thread with file-based persistence — fundamentally different from the subagent with opaque memory. Version 1.0.0 signals a clean contract.

## What Changed

### Agent → Skill (Hybrid B)

The skill runs inline for interaction (AskUserQuestion, output formatting, propose-accept flow) but delegates evidence gathering to an `Agent(Explore)` subagent for isolated, read-only heavy lifting.

- Steps 1-2 (load config, identify subject): inline — sees conversation context
- Step 3 (gather evidence): delegated to `Agent(Explore)` — isolated, fast
- Steps 4-8 (action note, patterns, proposals, apply, memory): inline — direct output to user

### `memory: local` → `.learning-cycle/` Folder

| Aspect | Before | After |
|--------|--------|-------|
| Storage | `.claude/agent-memory-local/learning-cycle-learner/` | `.learning-cycle/` at project root (config, memory, notes) |
| Visibility | Opaque | Human-readable, editable, self-contained |
| Version control | Not tracked | Can be committed or gitignored as one unit |
| Cross-machine | Not portable | Travels with the repo |
| Conflict resolution | Agent internal memory wins | User edits = ground truth |
| Discovery | Hidden in `.claude/` internals | Registered in CLAUDE.md on bootstrap |
| Cleanup | Must know internal path | `rm -rf .learning-cycle/` removes everything |

### Lazy-Loadability

The agent-based plugin required `enabledPlugins` toggle + session restart. The skill-based plugin can be lazy-loaded mid-session via `lazy load learning-cycle` (plugin-lazy Step 4).

## Tradeoff Summary

**What got better:**
- Context efficiency (~80 tokens at rest vs ~600)
- Lazy-loadable without restart
- Memory is transparent, portable, version-controllable — self-contained in `.learning-cycle/`
- Structured output prints directly to user (no summary truncation)

**What got worse:**
- No Opus guarantee (session model may be Sonnet)
- No free-form mid-cycle conversation (structured AskUserQuestion gates)
- Evidence comes back as summary from Explore agent (some detail loss)

**What stayed the same:**
- Core Kolb cycle (CE → RO → AC → AE)
- Propose-then-consent flow
- 8-section structured output format
- Config and memory extension surfaces (now in `.learning-cycle/` folder)
- Decision framework for evaluating patterns

## Migration Guide (from dev plugin)

1. Remove the dev plugin: uninstall or disable `learning-cycle` from the dev repo
2. Install from public repo: `plugin add operator47-plugins`
3. Enable: the skill loads as `learning-cycle` (not `learner`)
4. First run: the skill offers to bootstrap `.learning-cycle/` folder and register in `CLAUDE.md`
5. Migrate config: copy `learner.config.md` content into `.learning-cycle/config.md`
6. Migrate memory: copy `learner-memory.md` content into `.learning-cycle/memory.md`
7. Invocation: `/learning-cycle` or natural language ("run a learning cycle on X")
8. Cleanup: delete old root files (`learner.config.md`, `learner-memory.md`) and agent memory at `.claude/agent-memory-local/learning-cycle-learner/`

## Downgrade Path (Hybrid B → C)

At release time, if Agent delegation in Step 3 is deemed not worth the complexity, replace the `Agent(Explore)` spawn with inline `Read`/`Grep`/`Bash` commands. All other steps unchanged. This is a content-only diff in SKILL.md.
