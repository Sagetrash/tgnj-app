---
type: decision
status: approved
title: Adopt agentskills.io Specification and 5 Modular Subdocs
created: 2026-08-07
updated: 2026-08-07
tags:
  - decision
  - specification
  - agentskills
---

# Adopt agentskills.io Specification and 5 Modular Subdocs

## Context
AI coding agents (such as Claude Code, opencode, Google Antigravity, Cursor, and Gemini CLI) require portable, standardized skill definitions. Monolithic skill files overload context windows and reduce retrieval efficiency during project orientation.

## Decision
We adopt the [agentskills.io](https://agentskills.io) open specification for the root `SKILL.md` file, using YAML frontmatter properties (`name`, `version`, `license`, `author`, `description`).

We decouple detailed protocol procedures into 5 modular reference subdocuments located in `references/`:
1. `01-retrieval-protocol.md` — Targeted search, grep rules, and reading pitfalls.
2. `02-writeback-protocol.md` — 5-step write-back loop and Git commit discipline.
3. `03-metadata-schema.md` — Frontmatter YAML schema, OFM syntax, and `.base` database queries.
4. `04-index-tree-system.md` — PARA + Zettelkasten logarithmic index scaling.
5. `05-two-vault-architecture.md` — Global GPS vs project `.brain/` integration.

## Alternatives Considered
- **Monolithic SKILL.md**: Rejected due to high token overhead on every skill activation.
- **Agent-Specific Plugins**: Rejected to maintain cross-agent portability without custom lock-in.

## Consequences
- **Positive**: Lightweight entrypoint in `SKILL.md`; on-demand loading of specialized reference documents; compatible with all major agent frameworks.
- **Negative**: Requires maintaining link integrity and synchronizing metadata across subdocs.

## Related Notes
- [[architecture]]
- [[project-state]]
