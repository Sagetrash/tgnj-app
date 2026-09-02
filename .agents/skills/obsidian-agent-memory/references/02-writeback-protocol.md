# 02. Write-Back Protocol

**Goal:** Every session leaves the vault more accurate and complete than it found it. The vault is an agent-first brain — agents autonomously add, update, prune, and reindex information.

---

## 1. What to Write Back

Capture knowledge that would benefit future agent sessions:
- **Decisions & Rationale**: Architectural decisions (ADRs) explaining *why* a technology or structure was chosen.
- **Architecture Facts**: System design, data flow, component boundaries, constraints.
- **Discoveries & Gotchas**: Hard-won insights, bug root causes, API quirks, non-obvious setup requirements.
- **Session State**: Work completed, open questions, immediate next steps.
- **Corrections**: Fixing stale notes, outdated assumptions, or wrong paths.

---

## 2. Destination Routing Table

| Knowledge Type | Destination Path | Template |
|---|---|---|
| Architectural Decision | `.brain/decisions/YYYY-MM-DD-<slug>.md` | `templates/decision.md` |
| Architecture Overview | `.brain/architecture.md` | `templates/architecture.md` |
| Discoveries & Gotchas | `.brain/discoveries.md` | `templates/discovery.md` |
| Session Summary | `.brain/session-logs/YYYY-MM-DD.md` | `templates/session-log.md` |
| Current Status & Next Steps | `.brain/project-state.md` | `templates/project-state.md` |
| Cross-Project Resource | `30 Resources/<topic>.md` | Standard OFM note |
| Terms & Definitions | `.brain/glossary.md` | Standard OFM note |

---

## 3. The 5-Step Write-Back Loop

1. **Decide**: Is this worth keeping? Will a future session care? Skip ephemeral chat. Prune or archive stale notes.
2. **Write**: Create or append to the appropriate note using standard frontmatter, wikilinks, and a 1–2 sentence summary in the first paragraph.
3. **Reindex**: Update the branch's `registry.yaml` (add/modify `notes[]` entry) AND mirror the change in `INDEX.md`. Bump `updated: YYYY-MM-DD`.
4. **Validate**: Verify all wikilinks resolve and frontmatter YAML parses cleanly.
5. **Commit**: Perform a Git commit with clear commit message discipline.

---

## 4. Git Commit Discipline

- **Commit Message Format**: Use conventional scoping: `vault(<area>): <description>` (e.g. `vault(.brain): add token rotation decision and reindex`).
- **Ignore App Config**: Never commit `.obsidian/` application churn unless explicitly asked.
- **Fallback**: If Git is unavailable, log pending edits in `.brain/pending-commits.md` and notify the human.

---

## 5. Agent Autonomy & Judgment

- **Discretion**: The agent has explicit discretion to add, update, or prune information it deems worth keeping for future sessions.
- **Don't Delete Without a Trace**: Before pruning or deleting a note, ensure it is archived in `40 Archive/` or that a superseding note explicitly links to it.
- **When in Doubt**: Keep it, update it, or flag it — never silently drop user-authored content or unresolved decisions.

---

## 6. Full Agent Rules (DO / DON'T / ASK)

### DO
- Follow templates for new notes; always include frontmatter.
- Use wikilinks `[[Note]]` for internal navigation; markdown links `[text](url)` for web URLs.
- Keep registry summaries short (1–2 sentences) so other agents don't need to open note bodies.
- Bump `updated:` dates on modified notes and registries.
- Fix broken links, missing registry entries, and orphan notes created or found during editing.

### DON'T
- Don't write secrets, credentials, tokens, or private keys into any note or vault.
- Don't delete content without archiving or updating links first.
- Don't leave `INDEX.md` and `registry.yaml` out of sync.
- Don't nest tags 3+ levels deep (e.g. avoid `#a/b/c/d`).
- Don't duplicate knowledge — link instead. If a fact exists in two places, pick one authoritative location and link to it.
- Don't commit vault noise (`.obsidian/` churn, unintended binary attachments).

### ASK
- Ask the human when instructions conflict with vault safety rules.
- Ask before pruning user-authored notes if context is unclear.
- Ask when unsure whether a fact belongs in the vault at all (prefer keeping + flagging over dropping).
