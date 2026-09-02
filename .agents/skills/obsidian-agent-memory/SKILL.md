---
name: obsidian-agent-memory
version: 1.0.0
license: MIT
author: Sagetrash
description: >
  Global agent memory protocol using Obsidian Markdown vaults and .brain/
  project folders. ALWAYS activate on every project entry to orient the agent,
  retrieve context, record decisions and session state, and maintain the project
  knowledge graph. Do NOT skip this skill on any project.
---

# Obsidian Agent Memory Protocol

This skill defines how AI coding agents manage, retrieve, and write back knowledge using **Obsidian Markdown vaults** and per-project `.brain/` folders as long-term memory across sessions.

---

## 1. What is a Vault?

An Obsidian vault is **just a folder of plain Markdown files** (`.md`), YAML frontmatter properties, folders, and wikilinks (`[[Note]]`). 
- **No App Process Needed**: An agent never needs Obsidian running to use a vault. It operates directly on files on disk.
- **Rendering & Graph Layer**: Obsidian itself is merely a rendering, graph, and query UI built on top of standard plain-text files. Markdown is the lingua franca of AI tools.
- **Persistent Brain**: Session context dies when chat ends, but vault files persist across sessions.

---

## 2. Core Concepts

| Concept | Description | Agent Relevance |
|---|---|---|
| **Vault** | Folder of files treated as one workspace | Search and wikilink boundary is the entire vault folder. |
| **Note** | A `.md` file (filename = title by default) | Renaming a file changes its identity; text agents must grep `[[old name]]` to update links. |
| **Property / Frontmatter** | YAML block at the top of a note (`---` ... `---`) | Metadata layer. Key name and type consistency is required for querying. |
| **Wikilink** | `[[Note Name]]`, `[[Note#Heading]]`, `[[Note|display]]` | Connective graph tissue between notes. |
| **Backlink** | A link pointing *at* the current note | Uncovers related knowledge across notes. |
| **Tag** | `#tag`, `#nested/tag` | Filtering signal for discovery — not a replacement for folder/index structure. Keep $\le 2$ levels. |
| **Graph View** | Visual node graph of notes and links | Inferred purely from text wikilinks by agents. |
| **Daily Note** | Date-named note (e.g. `2026-08-07.md`) | Inbox for session-scoped facts before migrating to atomic notes. |
| **Canvas** | `.canvas` file (visual node graph) | JSON format; skip unless explicitly requested. |
| **Base** | `.base` file (property-based database view) | Structured, queryable YAML view over note frontmatter properties. |
| **Attachment** | Embedded files (`![[image.png]]`, PDFs, audio) | Stored in dedicated `attachments/` folder. |
| **`.obsidian/`** | Obsidian settings, plugins, themes config folder | App configuration directory. Do NOT edit or commit unless requested. |

---

## 3. References Sitemap

Read the following topic-specific documents in [references/](references/) on demand based on your current task:

| Document | When to Read |
|---|---|
| [01-retrieval-protocol.md](references/01-retrieval-protocol.md) | When searching for knowledge, orienting on a project, running `ripgrep`, or inspecting stale notes/dead links. |
| [02-writeback-protocol.md](references/02-writeback-protocol.md) | When saving session facts, writing Architecture Decision Records (ADRs), reindexing, or committing vault changes. |
| [03-metadata-schema.md](references/03-metadata-schema.md) | When formatting frontmatter YAML properties, writing `registry.yaml`, using wikilinks/callouts, or writing `.base` queries. |
| [04-index-tree-system.md](references/04-index-tree-system.md) | When organizing folders (PARA + Zettelkasten), creating `INDEX.md`, or splitting large branches into sub-indexes. |
| [05-two-vault-architecture.md](references/05-two-vault-architecture.md) | When linking global GPS vaults to project brains, performing new project handshakes, or using Obsidian CLI/REST fallback hierarchy. |

---

## 4. Standard Session Lifecycle

Every agent session working with a project MUST follow this 5-step loop:

1. **Orient**: Read `.brain/INDEX.md` (or `.brain/registry.yaml`) first. Do NOT glob-read the whole directory.
2. **Retrieve**: Follow `registry.yaml` summaries to read only the 1–3 notes relevant to your immediate task. Read `project-state.md` for current status.
3. **Execute**: Perform the requested coding or technical task.
4. **Write-back**: Capture decisions (ADRs in `.brain/decisions/`), discoveries, and updated state (`project-state.md` & `.brain/session-logs/`). Reindex `registry.yaml` and `INDEX.md`.
5. **Commit**: Clean dead links/orphans and commit changes via Git using `vault(<scope>): <description>` style.

---

## 5. Compact Agent Rules

### DO
- **Orient First**: Always start at `INDEX.md` or `registry.yaml`. Never recursive-scan a vault.
- **Use Frontmatter**: Every note MUST begin with standard YAML properties (`type`, `status`, `created`, `updated`, `tags`).
- **Use Wikilinks**: Link vault notes with `[[Note Name]]`. Use `[text](url)` for external HTTP links only.
- **Update Wikilinks on Rename**: When moving or renaming a note file, grep the vault for `[[Old Name]]` and update every reference.
- **Replace Template Placeholders**: When creating notes from `templates/`, replace all `{{placeholder}}` markers (e.g. `{{title}}`, `{{date}}`, `{{project}}`) with real values.
- **Keep Summaries Short**: Keep `registry.yaml` summaries to 1–2 actionable sentences.
- **Synchronize Mirrors**: Always update `INDEX.md` and `registry.yaml` together.
- **Bump Dates**: Update `updated: YYYY-MM-DD` on notes and registries whenever modifying them.
- **Fix What You Break**: Fix dead links, missing registry entries, and orphan notes created or found during editing.
- **Declare Staleness**: Explicitly inform the user if you rely on a note that appears stale or contradicts current codebase reality.

### DON'T
- **Do NOT Recursive Read**: Never parse or view all files in a vault.
- **Do NOT Duplicate Knowledge**: Link to existing notes instead of repeating facts in multiple files.
- **Do NOT Store Secrets**: Never write API keys, passwords, or credentials into any note or vault.
- **Do NOT Edit App Config**: Do not touch `.obsidian/` files unless specifically requested.
- **Do NOT Commit Vault Noise**: Keep `.obsidian/` churn and temporary files out of git commits.
- **Do NOT Nest Tags Deeply**: Limit tags to $\le 2$ levels (e.g. `#project/backend`).
- **Do NOT Leave Broken Links**: If you rename/move a note, update all wikilinks and registry entries referencing it.

### ASK
- **Safety Conflicts**: Ask when user instructions conflict with vault safety or freshness rules.
- **User Content Pruning**: Ask before deleting or heavily pruning user-authored notes.
- **Uncertain Inclusions**: Ask when unsure whether a fact belongs in the vault (prefer keeping + flagging over dropping).

---

## 6. Starter Templates & Examples

- **Templates**: Standard templates live in [templates/](templates/) (`decision.md`, `session-log.md`, `project-state.md`, `architecture.md`, `discovery.md`, `INDEX.md`, `registry.yaml`).
- **Examples**: A complete reference vault is located in [examples/sample-brain/](examples/sample-brain/).
