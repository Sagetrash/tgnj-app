---
type: architecture
status: active
title: Obsidian Agent Memory Architecture
created: 2026-08-07
updated: 2026-08-07
tags:
  - architecture
  - skill
---

# Obsidian Agent Memory Architecture

## Overview
`obsidian-for-agents` defines a standardized memory system that allows AI agents to read and write persistent context across sessions using standard Markdown vaults and per-project `.brain/` folders.

## Layout & Components
```mermaid
graph TD
  SKILL[SKILL.md (agentskills.io spec)] --> REFS[references/]
  SKILL --> TEMPLATES[templates/]
  SKILL --> SCRIPTS[scripts/]
  SKILL --> EXAMPLES[examples/]
  
  REFS --> R1[01-retrieval-protocol.md]
  REFS --> R2[02-writeback-protocol.md]
  REFS --> R3[03-metadata-schema.md]
  REFS --> R4[04-index-tree-system.md]
  REFS --> R5[05-two-vault-architecture.md]

  SCRIPTS --> VHEALTH[vault-health.py]
  SCRIPTS --> INSTALL[install.sh]
```

## Core Protocol Constraints
- **Logarithmic Context Retrieval**: Reading begins at `INDEX.md` and `registry.yaml` summaries.
- **5-Step Write-Back Loop**: Decide $\rightarrow$ Write $\rightarrow$ Reindex $\rightarrow$ Validate $\rightarrow$ Commit.
- **Dual Representation**: `INDEX.md` (human) and `registry.yaml` (machine) must remain synchronized.

## Related Notes
- [[decisions/2026-08-07-adopt-agentskills-io-spec]]
- [[discoveries]]
- [[project-state]]
