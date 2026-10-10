# 04. Index Tree System & Vault Layout

**Goal:** Ensure vault browsing remains fast and logarithmic ($O(\log N)$) as the knowledge base grows to hundreds or thousands of notes.

---

## 1. Organizing Principles

- **Links over Folders**: A file lives in one folder but can link to unlimited others. Prefer flat/shallow folders + rich wikilinks over deep nested folder hierarchies.
- **Maps of Content (MOCs)**: Index notes that link all notes of a specific topic. They act as the visual navigation layer.
- **Tags are Signals, Not Structure**: Use tags for discovery and filtering, not to dictate file locations. Limit tags to $\le 2$ levels.
- **Folders for True Separation**: Keep folders shallow ($\le 2–3$ levels) to demarcate major areas (e.g. `10 Projects/`, `decisions/`, `session-logs/`).

---

## 2. Proven Vault Systems

| System | Core Idea | Best For |
|---|---|---|
| **PARA** | Organize by actionability: **P**rojects, **A**reas, **R**esources, **A**rchives | Work, task execution, active projects |
| **Zettelkasten** | Atomic notes (one idea per note), densely linked | Long-term knowledge base, research |
| **Johnny Decimal** | Permanent `XX.YY` numbered IDs, bounded 10x10 scope | Systematic numbered cross-system filing |
| **Hybrid (Recommended)** | PARA top-level folders + Zettelkasten atomic notes + MOC/INDEX navigation | Practical agent memory, scales seamlessly |

---

## 3. Recommended Hybrid Directory Layout

```
vault/
├── INDEX.md                     ← Root index map (area links + summaries)
├── registry.yaml                ← Root machine registry (summary-only)
├── 10 Projects/                 ← Active projects (PARA)
│   ├── INDEX.md                 ← Branch map
│   ├── registry.yaml            ← Branch registry
│   └── <project>/
│       ├── project-state.md     ← Active status & next steps
│       ├── decisions/           ← ADR notes (YYYY-MM-DD-<slug>.md)
│       ├── architecture.md      ← System design facts
│       ├── discoveries.md        ← Gotchas & insights
│       └── session-logs/        ← Daily session logs (YYYY-MM-DD.md)
├── 20 Areas/                    ← Ongoing responsibilities
│   ├── INDEX.md
│   └── registry.yaml
├── 30 Resources/                ← Reference material (never-stale)
│   ├── INDEX.md
│   └── registry.yaml
├── 40 Archive/                  ← Completed / retired notes
│   └── INDEX.md
├── 90 Meta/                     ← Vault infrastructure
│   ├── templates/               ← Note templates
│   └── glossary.md              ← Terms & acronyms
└── attachments/                 ← Embedded images, PDFs, files
```

---

## 4. Organization DO / DON'T

- **DO** keep folder structures shallow ($\le 2–3$ levels); let links carry depth.
- **DO** create a branch `INDEX.md` + `registry.yaml` when a directory grows past ~20–30 notes.
- **DON'T** build an 8-level tag hierarchy (`#a/b/c/d/e`); duplicate tags degrade discovery.
- **DON'T** leave orphan notes piling up (notes with zero incoming/outgoing links).
- **DON'T** move or rename a note without updating its wikilinks and registry path.

---

## 5. The Index Tree Architecture

### Why Logarithmic Scaling Matters
A vault grows. Reading 2,000 notes to answer one question is wasteful and degrades agent context windows. The index tree bounds the read cost: **reading grows logarithmically with vault size, not linearly.**

### Structure Rules
1. The **root** `INDEX.md` and `registry.yaml` always exist.
2. Each **top-level area** (`10 Projects`, `30 Resources`, etc.) has its own `INDEX.md` + `registry.yaml`.
3. A branch gets a **sub-index** when it exceeds ~20–30 notes or ~150 lines of registry. The parent `INDEX.md` links to the sub-index; individual notes are removed from parent `registry.yaml` and replaced with a single pointer entry.

---

## 6. `INDEX.md` Format Specification

An `INDEX.md` file is the human-readable navigation map.

```markdown
# INDEX — 10 Projects

> Branch registry: `10 Projects/registry.yaml`

## Projects
- [[auth]] — RS256 JWT auth service (active)
- [[billing]] — Stripe integration (risky — see [[billing/state]])

## Decisions
- [[2026-08-05 token rotation]] — Approved refresh token rotation

## Sub-indexes
- [[10 Projects/legacy/INDEX]] — Retired monolith notes
```

---

## 7. Creating a Sub-Index (Step-by-Step)

1. Create `NEWBRANCH/INDEX.md` and `NEWBRANCH/registry.yaml`.
2. Move individual entries out of the parent `registry.yaml` into `NEWBRANCH/registry.yaml`.
3. Leave a pointer entry in parent `registry.yaml`:
   ```yaml
   - name: Legacy Monolith Notes
     type: index
     path: "NEWBRANCH/INDEX.md"
     summary: Pointer to sub-index for legacy monolith notes.
   ```
4. Update parent `INDEX.md` with a `## Sub-indexes` link.
5. Bump `updated:` date fields in both registries.
6. Commit changes to Git.

---

## 8. Freshness & Staleness Rules

- Every `registry.yaml` and `INDEX.md` carries an `updated: YYYY-MM-DD` field.
- The 5-step write-back loop ensures indices stay current after every editing session.
- If an agent finds a stale entry (wrong summary, invalid path, outdated status), it MUST immediately correct the entry and commit the fix.
