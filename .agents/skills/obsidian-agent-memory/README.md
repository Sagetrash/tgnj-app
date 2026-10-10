# Obsidian Agent Memory Skill

[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-agentskills.io-purple)](https://agentskills.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An agent-agnostic skill protocol that turns [Obsidian Markdown](https://obsidian.md) vaults and per-project `.brain/` directories into long-term, persistent memory for AI coding agents (such as Google Antigravity, Claude Code, opencode, Cursor, Codex, and Gemini CLI).

---

## Overview

AI agent chat memory is ephemeral. Source code alone doesn't explain *why* architectural decisions were made or what edge cases were discovered.

This skill equips AI agents to:
- **Maintain a Per-Project Brain (`.brain/`)**: Persist architectural decisions (ADRs), system design facts, discoveries, gotchas, and session logs in standard plain Markdown + YAML frontmatter.
- **Perform $O(\log N)$ Knowledge Retrieval**: Read `INDEX.md` and `registry.yaml` summaries first instead of parsing entire vault file trees.
- **Execute 5-Step Write-Back Loops**: Update notes, reindex metadata, sanitize broken links/orphans, and commit changes cleanly via Git.

---

## Repository Layout

```
.
├── SKILL.md                          # Primary agent entry point & core rules
├── README.md                         # Human documentation & setup guide
├── LICENSE                           # MIT License
├── references/                       # Detailed protocol subdocuments
│   ├── 01-retrieval-protocol.md      # Targeted reading, grep & 13 pitfalls
│   ├── 02-writeback-protocol.md      # 5-step write-back loop & Git discipline
│   ├── 03-metadata-schema.md         # Frontmatter, registry.yaml, OFM, Bases & Dataview
│   ├── 04-index-tree-system.md       # PARA + Zettelkasten logarithmic index tree
│   └── 05-two-vault-architecture.md  # Global GPS vault vs per-project .brain/ & automation
├── templates/                        # Starter templates for note creation
│   ├── decision.md                   # ADR template
│   ├── session-log.md                # Daily session log template
│   ├── project-state.md              # Active status & health template
│   ├── architecture.md               # System design & diagram template
│   ├── discovery.md                  # Gotcha & insight template
│   ├── INDEX.md                      # Starter INDEX.md map
│   └── registry.yaml                 # Machine-readable registry
├── scripts/                          # Automated helper scripts
│   ├── vault-health.py               # Stdlib Python vault validator
│   └── install.sh                    # Multi-runtime installation helper
└── examples/                        # Worked examples
    ├── sample-brain/                 # Complete sample project memory brain
    └── global-vault/                 # Sample global GPS vault
```

---

## Installation

### 1. Google Antigravity (AGY Direct Skill)
```bash
git clone git@github.com:Sagetrash/second-brain-skill.git ~/.gemini/antigravity/skills/obsidian-agent-memory
```

### 2. Google Antigravity (AGY Plugin)
```bash
git clone git@github.com:Sagetrash/second-brain-skill.git ~/.gemini/config/plugins/obsidian-agent-memory-plugin/skills/obsidian-agent-memory
```

### 3. Claude Code
```bash
git clone git@github.com:Sagetrash/second-brain-skill.git ~/.claude/skills/obsidian-agent-memory
```

### 4. opencode
```bash
git clone git@github.com:Sagetrash/second-brain-skill.git ~/.config/opencode/skills/obsidian-agent-memory
```

### 5. Per-Project Skill (`.agents/skills/`)
```bash
git clone git@github.com:Sagetrash/second-brain-skill.git .agents/skills/obsidian-agent-memory
```

### Quick Installer Script
Alternatively, run the interactive multi-runtime installer:
```bash
./scripts/install.sh
```

---

## Initializing a Project Brain

To set up a `.brain/` in any project repository:

1. Create a `.brain/` directory at your project root.
2. Copy `templates/INDEX.md`, `templates/registry.yaml`, and `templates/project-state.md` into `.brain/`.
3. Replace all `{{placeholder}}` markers with real project values.
4. Add a pointer line to your repository's `AGENTS.md` (or prompt rules):
   ```markdown
   Project memory lives in `.brain/`. Start by reading `.brain/INDEX.md`.
   ```

---

## Automated Vault Health Check

Run the zero-dependency Python health validator to check your `.brain/` vault for dead links, orphan notes, stale registries, or invalid frontmatter:

```bash
python3 scripts/vault-health.py .brain
```

---

## License

[MIT License](LICENSE).
