#!/usr/bin/env bash
set -e

# install.sh — Multi-runtime installer for Obsidian Agent Memory Skill

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_NAME="obsidian-agent-memory"

echo "=========================================="
echo " Obsidian Agent Memory Skill Installer"
echo "=========================================="
echo "Source: ${SCRIPT_DIR}"
echo ""

install_target() {
    local target_dir="$1"
    local name="$2"

    echo "📦 Installing to ${name} (${target_dir}/${SKILL_NAME})..."
    mkdir -p "${target_dir}"
    
    if [ -d "${target_dir}/${SKILL_NAME}" ]; then
        echo "   ⚠️ Removing existing skill directory..."
        rm -rf "${target_dir}/${SKILL_NAME}"
    fi

    cp -R "${SCRIPT_DIR}" "${target_dir}/${SKILL_NAME}"
    echo "   ✅ Installed successfully to ${target_dir}/${SKILL_NAME}"
}

install_antigravity_plugin() {
    local plugin_dir="${HOME}/.gemini/config/plugins/obsidian-agent-memory-plugin/skills"
    echo "📦 Installing to Antigravity Plugin (${plugin_dir}/${SKILL_NAME})..."
    mkdir -p "${plugin_dir}"

    if [ -d "${plugin_dir}/${SKILL_NAME}" ]; then
        rm -rf "${plugin_dir}/${SKILL_NAME}"
    fi

    cp -R "${SCRIPT_DIR}" "${plugin_dir}/${SKILL_NAME}"
    echo "   ✅ Installed plugin skill to ${plugin_dir}/${SKILL_NAME}"
}

echo "Select target runtime to install skill:"
echo "  1) Google Antigravity Direct Skill (~/.gemini/antigravity/skills/)"
echo "  2) Google Antigravity Plugin (~/.gemini/config/plugins/)"
echo "  3) Claude Code (~/.claude/skills/)"
echo "  4) opencode (~/.config/opencode/skills/)"
echo "  5) Current Project (.agents/skills/)"
echo "  6) All of the above"
echo ""

read -p "Enter choice [1-6]: " choice

case "${choice}" in
    1)
        install_target "${HOME}/.gemini/antigravity/skills" "Google Antigravity Direct Skill"
        ;;
    2)
        install_antigravity_plugin
        ;;
    3)
        install_target "${HOME}/.claude/skills" "Claude Code"
        ;;
    4)
        install_target "${HOME}/.config/opencode/skills" "opencode"
        ;;
    5)
        install_target "$(pwd)/.agents/skills" "Project Local (.agents/skills/)"
        ;;
    6)
        install_target "${HOME}/.gemini/antigravity/skills" "Google Antigravity Direct Skill"
        install_antigravity_plugin
        install_target "${HOME}/.claude/skills" "Claude Code"
        install_target "${HOME}/.config/opencode/skills" "opencode"
        install_target "$(pwd)/.agents/skills" "Project Local (.agents/skills/)"
        ;;
    *)
        echo "❌ Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "🎉 Installation Complete!"
