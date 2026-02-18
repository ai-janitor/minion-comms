#!/usr/bin/env bash
set -euo pipefail

# minion-comms installer
# Usage: curl -sSL https://raw.githubusercontent.com/ai-janitor/minion-comms/main/scripts/install.sh | bash

REPO="https://github.com/ai-janitor/minion-comms.git"
RUNTIME_DIR="$HOME/.minion-comms"
MCP_CONFIG="$HOME/.claude.json"
DOCS_BASE_URL="https://raw.githubusercontent.com/ai-janitor/minion-comms/main/docs"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
die()   { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# ── Step 1: Install the Python package ──────────────────────────────────────

info "Installing minion-comms..."

if command -v pipx &>/dev/null; then
    info "Using pipx (isolated environment)"
    pipx install "git+${REPO}" --force 2>/dev/null \
        || pipx install "git+${REPO}" 2>/dev/null \
        || die "pipx install failed. Check Python 3.10+ is available."
elif command -v uv &>/dev/null; then
    info "Using uv"
    uv tool install "git+${REPO}" --force 2>/dev/null \
        || uv tool install "git+${REPO}" 2>/dev/null \
        || die "uv tool install failed."
elif command -v pip &>/dev/null; then
    warn "pipx/uv not found — falling back to pip (may pollute global env)"
    pip install "git+${REPO}" --user --break-system-packages 2>/dev/null \
        || pip install "git+${REPO}" --user 2>/dev/null \
        || pip install "git+${REPO}" 2>/dev/null \
        || die "pip install failed. Install pipx first: python3 -m pip install --user pipx"
else
    die "No Python package manager found. Install pipx: https://pipx.pypa.io"
fi

# Verify the command exists and PATH is set up
if ! command -v minion-comms &>/dev/null; then
    warn "minion-comms not found on PATH."
    echo ""
    warn "Add this to your shell config and restart your terminal:"
    if [[ "${SHELL:-}" == */zsh ]]; then
        warn "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc"
    elif [[ "${SHELL:-}" == */bash ]]; then
        warn "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    else
        warn "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.profile"
    fi
    echo ""
fi

# ── Step 2: Deploy runtime docs to ~/.minion-comms/ ─────────────────────────

info "Deploying onboarding docs to ${RUNTIME_DIR}..."

mkdir -p "${RUNTIME_DIR}/classes"

DOCS=(
    "PROTOCOL.md"
    "classes/lead.md"
    "classes/coder.md"
    "classes/builder.md"
    "classes/oracle.md"
    "classes/recon.md"
)

for doc in "${DOCS[@]}"; do
    curl -sSfL "${DOCS_BASE_URL}/${doc}" -o "${RUNTIME_DIR}/${doc}" \
        || warn "Failed to download ${doc} — you can copy it manually from the repo"
done

ok "Onboarding docs deployed to ${RUNTIME_DIR}/"

# ── Step 3: Configure MCP for Claude Code ───────────────────────────────────

info "Configuring MCP..."

# Prefer `claude mcp add` (knows the correct config location and format).
# Fall back to manual JSON edit of ~/.claude.json if claude CLI not available.
if command -v claude &>/dev/null; then
    claude mcp add --scope user minion-comms -- minion-comms 2>/dev/null \
        && ok "Configured minion-comms MCP (via claude mcp add)" \
        || warn "claude mcp add failed — configure manually: claude mcp add --scope user minion-comms -- minion-comms"
else
    info "claude CLI not found — configuring ${MCP_CONFIG} directly"

    add_mcp_entry() {
        local config="$1"
        if [ -f "$config" ] && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); exit(0 if 'minion-comms' in d.get('mcpServers',{}) else 1)" "$config" 2>/dev/null; then
            info "minion-comms already in ${config} — skipping"
            return
        fi

        if command -v jq &>/dev/null; then
            if [ -f "$config" ] && [ -s "$config" ]; then
                jq '.mcpServers["minion-comms"] = {"type": "stdio", "command": "minion-comms", "args": [], "env": {}}' "$config" > "${config}.tmp" \
                    && mv "${config}.tmp" "$config"
            else
                echo '{"mcpServers":{"minion-comms":{"type":"stdio","command":"minion-comms","args":[],"env":{}}}}' | jq . > "$config"
            fi
        elif command -v python3 &>/dev/null; then
            python3 -c "
import json, os
p = '$config'
d = json.load(open(p)) if os.path.isfile(p) and os.path.getsize(p) > 0 else {}
d.setdefault('mcpServers', {})['minion-comms'] = {'type': 'stdio', 'command': 'minion-comms', 'args': [], 'env': {}}
json.dump(d, open(p, 'w'), indent=2)
"
        else
            warn "Add manually: claude mcp add --scope user minion-comms -- minion-comms"
            return
        fi

        ok "Added minion-comms to ${config}"
    }

    add_mcp_entry "${MCP_CONFIG}"
fi

# ── Done ────────────────────────────────────────────────────────────────────

echo ""
ok "minion-comms installed!"
echo ""
echo "  Runtime dir:  ${RUNTIME_DIR}/"
echo "  MCP config:   ${MCP_CONFIG}"
echo ""
echo "  Usage:"
echo "    minion-comms              # run MCP server (stdio)"
echo "    claude                    # start Claude Code — minion-comms is available"
echo ""
echo "  First steps in a session:"
echo "    register(name, class)     # join the raid"
echo "    set_battle_plan(name, p)  # lead sets the plan"
echo "    cold_start(name)          # catch up after compaction"
echo ""
