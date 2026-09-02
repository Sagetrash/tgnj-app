# 01. Retrieval Protocol & Pitfalls Reference

**Goal:** Reach the exact knowledge needed with the minimum file reads. Follow this strict 6-step order; never skip steps or perform indiscriminate recursive directory reads.

---

## The 6-Step Retrieval Protocol

### Step 1 — Orient (1 file, ~50–150 lines)
Read the vault root `INDEX.md` (or `.brain/INDEX.md`). If it does not exist, read `registry.yaml`. You now know the main branches and key notes.

### Step 2 — Narrow (1 file)
Identify the relevant branch from the root index. Read that branch's `INDEX.md` and/or `registry.yaml`. For a deep branch, follow sub-index pointers.

### Step 3 — Select (by summary)
From the branch registry, pick notes whose `summary` matches your task. **Do not open notes whose summaries are irrelevant.**

### Step 4 — Read (targeted)
Read only the selected notes (`path` from the registry). Use heading or block references when you only need a specific section (e.g., `[[Note#Heading]]`).

### Step 5 — Search as the Needle (Grep)
If the index path dead-ends or you need something not listed in the registry:
1. Run `rg -l "pattern" <vault>` for a fast first-pass search.
2. Search with a specific, targeted query — never a bare scan.
3. Read the top 3–5 matches and confirm relevance from their frontmatter `type`/`status`/`summary` before reading full note bodies.
4. *Rule:* Prefer `rg` over `find`. Use `find` only to confirm if a file path exists.

### Step 6 — Validate Knowledge Freshness
Before acting on vault knowledge, sanity check:
- Is the note's `status` current (`active` vs `deprecated`)?
- Does the `updated` date look too old for a fast-moving component?
- Is there a newer decision that `supersedes` it?

> [!WARNING] Stale facts risk
> Stale facts are a bigger risk than missing facts. If you act on a note that appears stale or contradicts current codebase reality, explicitly state this to the user.

---

## Orphan & Dead-Link Hygiene

- **Orphan Note:** A note with no incoming or outgoing wikilinks. Fix by linking it to an `INDEX.md` / MOC or moving it to `40 Archive/`.
- **Dead Link:** A wikilink `[[Note Name]]` pointing to a file that does not exist. Fix the link path or create the missing target note.
- **Hygiene Rule:** Whenever performing retrieval or write-back, check for dead links or orphans created or encountered in that branch, fix them, and commit the fix.

---

## Pitfalls & Gotchas Reference

| Pitfall | Reality / Prevention |
|---|---|
| `file=` vs `path=` targeting | CLI `file=` resolves wikilink-style (no path/ext); `path=` is exact relative path from vault root. Mixing them causes "not found" errors. |
| Wikilinks don't auto-rename for text agents | Renaming/moving a file does NOT auto-update plain text links. Grep the vault for `[[old name]]` and update every reference. |
| Frontmatter must be first | Content before the initial `---` fence breaks YAML properties parsing. Frontmatter MUST be lines 1–N. |
| `#` in filenames | `[[Note # Name]]` breaks heading link syntax. Avoid `#` in filenames. |
| Inline fields vs properties | Dataview reads inline `key:: value`; Bases reads ONLY frontmatter properties. Keep metadata in frontmatter for compatibility. |
| Empty vs missing property | `status != "done"` excludes notes where `status` is missing. Queries must handle missing fields deliberately. |
| Tag sprawl | Duplicate/uncontrolled tags accumulate quickly. Keep $\le 10$ active tags, $\le 2$ levels deep (e.g. `#project/backend`). |
| Stale registry entries | Registry usefulness depends entirely on freshness. Fix stale `summary`, `path`, or `status` entries on sight. |
| Orphan notes | Notes with no links get lost. Always link new notes to an `INDEX.md` or MOC. |
| Huge vault slowness | Sub-indexes and shallow folders keep vault indexing fast for both agents and Obsidian app. |
| `.obsidian/` churn | App config churns constantly. Keep `.obsidian/` gitignored in project repos. |
| Hidden `.brain/` in tools | If file tools skip dotfolders, explicitly verify tool settings allow reading `.brain/`. |
| Secrets in vault | Vaults are versioned in Git. Never store API keys, tokens, or passwords in a vault note. |

---

## Resources & Official Documentation

- **Obsidian Help (Official)**: https://help.obsidian.md
- **Obsidian Flavored Markdown**: https://help.obsidian.md/obsidian-flavored-markdown
- **Properties Schema**: https://help.obsidian.md/properties
- **Bases Specification**: https://obsidian.md/help/bases
- **Callouts Guide**: https://obsidian.md/help/callouts
- **Obsidian CLI**: https://help.obsidian.md/cli
- **Local REST API + MCP Plugin**: https://github.com/coddingtonbear/obsidian-local-rest-api
- **kepano/obsidian-skills**: https://github.com/kepano/obsidian-skills
- **Dataview Plugin**: https://github.com/blacksmithgu/obsidian-dataview
- **Agent Skills Specification**: https://agentskills.io/specification
