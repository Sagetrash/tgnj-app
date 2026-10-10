# 05. Two-Vault Architecture & Automation Layer

**Goal:** Provide seamless cross-project navigation while maintaining strict boundaries for project-specific memory, backed by a flexible automation tool hierarchy.

---

## 1. Global Vault vs. Per-Project Vault

| Vault Tier | Location | Purpose | Key Files |
|---|---|---|---|
| **Global Vault (GPS)** | User-defined (e.g. `~/brain/`) | Cross-project index, user coding preferences, reusable knowledge, project registry | `10 Projects/`, `20 Preferences/`, `registry.yaml` |
| **Per-Project Vault (Brain)** | `<repo>/.brain/` | Project memory: decisions, architecture, session logs, current state | `INDEX.md`, `registry.yaml`, `project-state.md` |

---

## 2. The Global Vault (The GPS)

The global vault acts as the agent's GPS across all user projects.

```
global-vault/
├── INDEX.md                     ← Root map
├── registry.yaml                ← Global project registry
├── 10 Projects/                 ← One entry per project (summary + vault_path)
│   ├── INDEX.md
│   └── registry.yaml
├── 20 Preferences/              ← Coding prefs: languages, style, tooling, conventions
├── 30 Knowledge/                ← General/reusable knowledge notes
├── 40 Archive/                  ← Retired projects & notes
└── 90 Meta/                     ← Global templates, glossary
```

### Global Registry Entry Example (`registry.yaml`)

```yaml
notes:
  - name: my-app
    type: project
    path: "10 Projects/my-app.md"
    summary: E-commerce backend; Node/TS, Postgres, Redis.
    vault_path: /home/user/code/my-app/.brain
    repo: https://github.com/user/my-app
    health: healthy
    status: active
    updated: 2026-08-07
```

> [!TIP] Retrieval Rule
> A new agent facing an unknown project reads the global registry $\rightarrow$ finds `vault_path` $\rightarrow$ jumps directly to the project vault's `.brain/INDEX.md`. It does NOT scan the user's disk.

---

## 3. The Per-Project Vault (The Brain)

The project vault lives inside the project root, named **`.brain/`** (hidden, short, unambiguous).

```
my-app/
├── .brain/                      ← Project memory vault
│   ├── INDEX.md                 ← Root map
│   ├── registry.yaml            ← Machine registry
│   ├── project-state.md         ← Current status & next steps
│   ├── decisions/               ← YYYY-MM-DD-<slug>.md ADRs
│   ├── architecture.md          ← System design facts
│   ├── discoveries.md           ← Gotchas & insights
│   ├── session-logs/            ← Daily session logs (YYYY-MM-DD.md)
│   └── glossary.md              ← Project terms & acronyms
├── AGENTS.md                    ← Pointer file referencing .brain/
├── .gitignore                   (Decide: commit .brain or ignore)
└── src/                         ← Application source code
```

### The `AGENTS.md` Pointer Note
A per-project `AGENTS.md` (or `CLAUDE.md`, or agent rule file) should contain a single pointer line:

```markdown
Project memory lives in `.brain/`. Start by reading `.brain/INDEX.md`.
```

---

## 4. New Project Handshake Protocol

When an AI agent enters a project codebase:

1. **Check for Pointer**: Read `AGENTS.md` / rules $\rightarrow$ sees `.brain/`.
2. **Read Index**: Read `.brain/INDEX.md` (and `.brain/registry.yaml`) to orient.
3. **Read Status**: Read `project-state.md` to get current status, health, and active next steps.
4. **Targeted Read**: Read 1–3 specific notes relevant to the task (per retrieval protocol).
5. **Execute**: Perform the engineering task.
6. **Write-Back & Commit**: Record decisions/discoveries, update `project-state.md`, reindex, and commit.

---

## 5. What NOT to Store in Vaults

- **Secrets & Credentials**: Never store API keys, tokens, SSH keys, passwords, or private environment variables in any note.
- **Raw Source Code**: Link to code files (`[filename](file:///path/to/file)`) or quote brief relevant snippets; do not copy whole source files into the vault.
- **Ephemeral Chat**: Keep transient prompt conversation out of the vault. Store only durable decisions, facts, and session logs.

---

## 6. Automation Layer (Optional Tools)

The file-based protocol works with **zero setup** — Obsidian does not need to be running. When Obsidian is actively running, optional automation interfaces are available.

### Priority Hierarchy for Agents
1. **Plain File Tools** (`view_file`, `write_to_file`, `replace_file_content`): Primary mechanism — always works headlessly without app dependencies.
2. **Grep/Search** (`grep_search` / `rg`): Fast text search across vault files.
3. **Obsidian CLI / Local REST API / MCP**: Used ONLY when Obsidian application is actively running and live app interaction is requested.

### Official Obsidian CLI (Requires Obsidian running)
- CLI syntax: `obsidian create name="Note" content="..."`, `obsidian search query="term"`, `obsidian property:set name=status value=done file="Note"`.
- **Targeting Distinction:** `file=<name>` resolves wikilink-style (no path or `.md` extension needed); `path=<path>` is exact relative path from vault root. Mixing them causes "not found" errors.
- Multi-vault selection: `obsidian vault="VaultName" <command>`.

### Local REST API & MCP Plugin (`obsidian-local-rest-api`)
- Plugin endpoint: `https://127.0.0.1:27124` with built-in MCP server at `/mcp/`.
- Enables CRUD operations, surgical section patching (heading/block/property level), and JsonLogic search while Obsidian is running.

### Third-Party Agent CLIs (e.g. `obsidian-agent-cli`)
- Python-based CLI with JSON output, AI workspace isolation, and automatic fallback from REST API to filesystem.
