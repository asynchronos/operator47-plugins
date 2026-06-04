#!/usr/bin/env bash
set -euo pipefail

# Target repo root. Defaults to this script's repo (../..); an explicit first
# arg lets the test harness point validation at a throwaway fixture repo.
REPO_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"

if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is required but not found. Install: apt install jq (Linux), brew install jq (macOS), or winget install jqlang.jq (Windows)" >&2
    exit 1
fi

ERRORS=0
WARNINGS=0

err()  { echo "ERROR: $*" >&2; ERRORS=$((ERRORS + 1)); }
warn() { echo "WARN:  $*" >&2; WARNINGS=$((WARNINGS + 1)); }
info() { echo "INFO:  $*"; }

SEMVER_RE='^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$'

# ---------- 1. Validate plugin.json files ----------

info "=== Validating plugin.json files ==="

PLUGIN_DIRS=()
for pdir in "$REPO_ROOT"/plugins/*/; do
    [ -d "$pdir" ] || continue
    PLUGIN_DIRS+=("$pdir")
    dir_name="$(basename "$pdir")"
    pjson="$pdir.claude-plugin/plugin.json"

    if [ ! -f "$pjson" ]; then
        err "$dir_name: missing .claude-plugin/plugin.json"
        continue
    fi

    if ! jq empty "$pjson" 2>/dev/null; then
        err "$dir_name: plugin.json is not valid JSON"
        continue
    fi

    for field in name version description; do
        val="$(jq -r ".$field // empty" "$pjson")"
        if [ -z "$val" ]; then
            err "$dir_name: plugin.json missing required field '$field'"
        fi
    done

    author_name="$(jq -r '.author.name // empty' "$pjson")"
    if [ -z "$author_name" ]; then
        err "$dir_name: plugin.json missing required field 'author.name'"
    fi

    version="$(jq -r '.version // empty' "$pjson")"
    if [ -n "$version" ] && ! [[ "$version" =~ $SEMVER_RE ]]; then
        err "$dir_name: plugin.json version '$version' is not valid semver"
    fi

    json_name="$(jq -r '.name // empty' "$pjson")"
    if [ -n "$json_name" ] && [ "$json_name" != "$dir_name" ]; then
        err "$dir_name: directory name does not match plugin.json name '$json_name'"
    fi

    info "  $dir_name: plugin.json OK"
done

if [ ${#PLUGIN_DIRS[@]} -eq 0 ]; then
    warn "No plugin directories found under plugins/"
fi

# ---------- 2. Validate marketplace.json ----------

info "=== Validating marketplace.json ==="

MARKETPLACE="$REPO_ROOT/.claude-plugin/marketplace.json"

if [ ! -f "$MARKETPLACE" ]; then
    err "Missing .claude-plugin/marketplace.json"
else
    if ! jq empty "$MARKETPLACE" 2>/dev/null; then
        err "marketplace.json is not valid JSON"
    else
        # tr -d '\r': strip CR so a CRLF checkout (autocrlf=true on Windows,
        # where jq may emit \r\n) doesn't corrupt the parsed source paths.
        # No-op on LF input, so Linux CI behavior is unchanged.
        mp_sources="$(jq -r '.plugins[].source' "$MARKETPLACE" | tr -d '\r')"

        while IFS= read -r src; do
            [ -z "$src" ] && continue
            resolved="$REPO_ROOT/$src"
            if [ ! -d "$resolved" ]; then
                err "marketplace.json: source '$src' does not resolve to a directory"
            fi
        done <<< "$mp_sources"

        mp_names="$(jq -r '.plugins[].name' "$MARKETPLACE" | tr -d '\r' | sort)"

        dir_names=""
        for pdir in "${PLUGIN_DIRS[@]}"; do
            dir_names+="$(basename "$pdir")"$'\n'
        done
        dir_names="$(echo "$dir_names" | sed '/^$/d' | sort)"

        in_mp_not_dir="$(comm -23 <(echo "$mp_names") <(echo "$dir_names"))"
        in_dir_not_mp="$(comm -13 <(echo "$mp_names") <(echo "$dir_names"))"

        if [ -n "$in_mp_not_dir" ]; then
            while IFS= read -r name; do
                err "marketplace.json lists '$name' but no plugins/$name/ directory exists"
            done <<< "$in_mp_not_dir"
        fi

        if [ -n "$in_dir_not_mp" ]; then
            while IFS= read -r name; do
                err "plugins/$name/ exists but is not listed in marketplace.json"
            done <<< "$in_dir_not_mp"
        fi

        info "  marketplace.json OK"
    fi
fi

# ---------- 3. Validate SKILL.md frontmatter ----------

info "=== Validating SKILL.md frontmatter ==="

for skill_md in "$REPO_ROOT"/plugins/*/skills/*/SKILL.md; do
    [ -f "$skill_md" ] || continue
    rel_path="${skill_md#"$REPO_ROOT"/}"

    frontmatter="$(awk '/^---$/{if(++c==2)exit}c==1' "$skill_md")"

    if [ -z "$frontmatter" ]; then
        err "$rel_path: no YAML frontmatter found"
        continue
    fi

    if ! echo "$frontmatter" | grep -qE '^name:'; then
        err "$rel_path: frontmatter missing 'name:' field"
    fi

    if ! echo "$frontmatter" | grep -qE '^description:'; then
        err "$rel_path: frontmatter missing 'description:' field"
    fi

    desc_line="$(echo "$frontmatter" | grep -E '^description:' | head -1)"
    desc_value="${desc_line#description:}"
    desc_value="${desc_value# }"
    if [ -n "$desc_value" ] && echo "$desc_value" | grep -qE ': ' && ! echo "$desc_value" | grep -qE '^>|^["|'"'"']'; then
        warn "$rel_path: description value contains unquoted ': ' — may break YAML parsing"
    fi

    info "  $rel_path OK"
done

# ---------- 4. Structural checks ----------

info "=== Structural checks ==="

for pdir in "${PLUGIN_DIRS[@]}"; do
    dir_name="$(basename "$pdir")"

    has_skills=false
    has_agents=false

    if compgen -G "$pdir/skills/*/SKILL.md" > /dev/null 2>&1; then
        has_skills=true
    fi

    if compgen -G "$pdir/agents/*.md" > /dev/null 2>&1; then
        has_agents=true
    fi

    if ! $has_skills && ! $has_agents; then
        err "$dir_name: plugin has no skills (skills/*/SKILL.md) and no agents (agents/*.md)"
    fi

    info "  $dir_name: structure OK"
done

# ---------- Summary ----------

echo ""
echo "================================"
echo "Validation complete: $ERRORS error(s), $WARNINGS warning(s)"
echo "================================"

if [ "$ERRORS" -gt 0 ]; then
    exit 1
fi
