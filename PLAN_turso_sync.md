# TGNJ Inventory — Turso Sync Integration Plan

> **Goal:** Add multi-device offline-first sync to TGNJ Inventory Manager using Turso Cloud as a free sync hub, with **zero frontend architecture changes** and **no new pip dependencies**.

---

## Current Architecture

```
Browser (Vanilla JS) ──HTTP──▶ Flask (Python) ──SQL──▶ SQLite file
   (index.html + script.js)      (app.py, routes)        (inventory.db)
```

- **Frontend:** Vanilla JS, `fetch()` to Flask endpoints
- **Backend:** Flask with raw `sqlite3` module
- **Database:** Single `inventory` table: `(id, sku_group, sku_id, shape, weight, length, width, depth)`
- **Sync:** None built in — Syncthing used for file-level sync
- **Auth:** None — single user, no login

---

## Current Workflow & Pain Points

The user currently syncs `inventory.db` across devices using **Syncthing**.
This works because only one device uses the DB at a time. But as the business scales
and concurrent access becomes necessary, Syncthing's file-level sync introduces risks:

| Risk | Consequence |
|---|---|
| Split-brain conflicts | `.sync-conflict-*.db` files appear — manual merge required |
| WAL/journal corruption | Syncing a half-written WAL file corrupts the database |
| No row-level granularity | One user's edit locks the entire file |
| No offline-write safety | Must wait for file sync before writing |

**The Turso plan replaces binary-file-flood with row-level database sync — same
outcome (data on all devices), but safe under concurrent use.**

---

## Target Architecture

```
Device A                                  Device B
Browser (unchanged)                        Browser (unchanged)
    │                                          │
    ▼                                          ▼
Flask (unchanged routes)                   Flask (unchanged routes)
    │                                          │
    ▼                                          ▼
database.py  +  sync.py                   database.py  +  sync.py
    │               │                          │               │
    ▼               │                          ▼               │
local SQLite       │                    local SQLite          │
(source of truth)  │                    (source of truth)     │
    │               │                          │               │
    └───────┬───────┘                          └───────┬───────┘
            │ Push changed rows (upsert)              │
            │ Pull changed rows (last-write-wins)     │
            ▼                                          ▼
        ┌──────────────────────────────────────────────────┐
        │              Turso Cloud (free tier)              │
        │         distributed SQLite sync hub               │
        │     5GB storage, 500M reads/mo, 10M writes/mo     │
        │     100 databases, no credit card required        │
        │     no inactivity pause                           │
        └──────────────────────────────────────────────────┘
```

**Key principles:**
- **Frontend is unchanged** — reads/writes through the same Flask API routes
- **Local SQLite is always the source of truth**
- **Sync is background, incremental, last-write-wins**
- **Turso is pure Python (`urllib`)** — no new pip dependencies
- **Works fully offline** — sync resumes when connectivity returns
- **Sync is opt-in via the UI** — until you configure Turso, the app behaves exactly as it does today

---

## Phase 0: Turso Account & Database Setup (one-time, ~10 min)

> Run these commands manually. They require the Turso CLI — not accessible in this environment.

### 0.1 — Install Turso CLI

```bash
curl -sSfL https://get.turso.tech/install.sh | bash
```

### 0.2 — Create Account & Database

```bash
turso auth login
turso db create tgnj-inventory
```

### 0.3 — Get Credentials

```bash
turso db show tgnj-inventory                 # → URL (e.g. https://tgnj-inventory-org.turso.io)
turso db tokens create tgnj-inventory        # → auth token (starts with "eyJ...")
```

### 0.4 — Create Table on Turso

```bash
turso db shell tgnj-inventory <<SQL
CREATE TABLE inventory (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_group    TEXT    NOT NULL,
    sku_id       INTEGER NOT NULL,
    shape        TEXT    NOT NULL,
    weight       REAL    NOT NULL,
    length       INTEGER NOT NULL,
    width        INTEGER NOT NULL,
    depth        INTEGER NOT NULL,
    created_at   TEXT    DEFAULT (datetime('now')),
    updated_at   TEXT    DEFAULT (datetime('now')),
    is_deleted   INTEGER DEFAULT 0,
    UNIQUE(sku_group, sku_id)
);
SQL
```

> The `created_at`, `updated_at`, and `is_deleted` columns enable incremental sync
(only send changed rows) and soft deletes (propagate deletes across devices).

---

## Implementation Phases

Each phase is self-contained, reversible, and testable before moving to the next.

---

### Phase A — turso_client.py + database.py schema

| Sub-step | Description | Rollback |
|---|---|---|
| A1 | Copy real DB, work on copy | Delete copy |
| A2 | Write `turso_client.py` (stdlib HTTP client, ~60 lines) | Delete file |
| A3 | Add sync columns to local schema (idempotent ALTER TABLE) | Restore from backup |
| A4 | Modify CRUD methods (soft delete, timestamps) | Revert file changes |
| A5 | Remove `sold_item()` stub | Verify no references |

**Test:** App still opens, reads/writes work same as before.

---

### Phase B — sync.py engine

| Sub-step | Description | Test |
|---|---|---|
| B1 | Write `sync_push()`, `sync_pull()`, `sync()` | `--dry-run` flag verifies queries without hitting Turso |
| B2 | Write `initial_sync()` first-sync logic | Run against empty Turso DB |
| B3 | End-to-end single device sync test | Add/edit/delete, verify Turso mirrors local |

**Test:** `python -m tgnj_app.core.sync --dry-run --db copy.db` runs without errors.

---

### Phase C — app.py routes + sync thread

| Sub-step | Description |
|---|---|
| C1 | Add `/api/getTursoConfig`, `/api/setTursoConfig` routes |
| C2 | Add `/api/runSync`, `/api/getSyncStatus` routes |
| C3 | Background sync daemon thread |
| C4 | Start-up config loading from `Config.json` |

**Test:** Endpoints return correct values, sync thread logs activity.

---

### Phase D — Frontend UI

| Sub-step | Description |
|---|---|
| D1 | Add Turso URL + token fields to `index.html` header |
| D2 | Add `getTursoConfig()`, `setTursoConfig()`, `syncNow()` to `script.js` |
| D3 | Add sync status polling (every 10s) |
| D4 | Style additions to `style.css` |

**Test:** UI elements appear, buttons call correct endpoints.

---

### Phase E — End-to-end test

| Sub-step | Description |
|---|---|
| E1 | Configure Turso on Device A, add items, verify sync reaches Turso |
| E2 | Configure Turso on Device B, verify items appear |
| E3 | Edit same row on both devices, verify last-write-wins |
| E4 | Disconnect internet, edit offline, reconnect, verify sync resumes |
| E5 | Deploy to production: swap real DB, run migration script |

**Test:** All scenarios pass.

---

## Phase Details

### Phase A — `src/tgnj_app/core/turso_client.py`

Pure-stdlib HTTP client wrapping Turso's REST API.

#### Responsibilities

- Execute SQL statements on Turso Cloud via `POST /v2/pipeline`
- Handle connection errors gracefully (return `None` on failure)
- Provide simple `execute(sql, args)` and `execute_batch(statements)` methods

#### Key Design

```python
import json, urllib.request
from urllib.error import URLError

class TursoClient:
    def __init__(self, url: str, token: str):
        self.base_url = url.rstrip('/')
        self.token = token

    def execute(self, sql: str, args: list = None) -> dict | None:
        # Build request body, call POST /v2/pipeline, parse response
        # Return None on network/timeout/HTTP error (caller handles offline)

    def execute_batch(self, statements: list[dict]) -> dict | None:
        # Multiple statements in one pipeline call
        # Each statement: {"sql": "...", "args": [...]}
```

#### Dependencies

**Zero.** `urllib` and `json` are stdlib.

#### Error Handling

- `URLError`, `TimeoutError` → return `None` (offline)
- HTTP 4xx/5xx → log warning, return `None`
- Never raises — caller chooses how to handle

---

### Phase A — Modify `src/tgnj_app/core/database.py`

#### A.3 — Constructor Changes (`__init__`)

- Accept optional `turso_client: TursoClient` parameter
- Run schema migration (ADD COLUMN if not exists) after opening connection
- Initialize `_sync_meta` table:

```sql
CREATE TABLE IF NOT EXISTS _sync_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
```

#### A.4 — CRUD Changes

| Method | Change |
|---|---|
| `add_item()` | Include `created_at`, `updated_at` in INSERT |
| `edit_item()` | Add `updated_at = datetime('now')` to SET clause |
| `delete_item()` | **Soft delete**: `UPDATE SET is_deleted = 1, updated_at = datetime('now') WHERE ...` |
| `get_items_by_group()` | Add `WHERE COALESCE(is_deleted, 0) = 0` |
| `get_item_by_sku()` | Add `WHERE COALESCE(is_deleted, 0) = 0` |
| `extract_data()` | Add filter for non-deleted rows |

#### A.5 — Remove Stub

- Remove `sold_item()` method

#### New Sync Methods

```python
def get_changes_since(self, timestamp: str) -> list[dict]:
    """
    SELECT * FROM inventory
    WHERE updated_at > ?
    ORDER BY updated_at ASC
    Returns rows modified since last push (including soft-deletes).
    """

def apply_remote_change(self, row: dict):
    """
    INSERT OR REPLACE INTO inventory (id, sku_group, sku_id, ...)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    Only applied if remote updated_at >= local updated_at (last-write-wins).
    """

def get_sync_meta(self, key: str) -> str | None:
    """Read from _sync_meta table."""

def set_sync_meta(self, key: str, value: str):
    """Write to _sync_meta table (INSERT OR REPLACE)."""

def get_all_items(self) -> list[dict]:
    """Fetch all rows (for initial migration / full-sync)."""

def get_count(self) -> int:
    """Return total non-deleted row count."""
```

---

### Phase B — `src/tgnj_app/core/sync.py`

Bidirectional sync engine. A single `sync()` function orchestrates push then pull.

#### B.1 — `sync_push(db, turso)`

```
1. last_push = db.get_sync_meta('last_push_time') or '1970-01-01'
2. changes = db.get_changes_since(last_push)
3. if no changes: return (nothing to push)
4. For each changed row:
     - If is_deleted == 1:
         DELETE FROM inventory WHERE id = ?    (on Turso)
       Else:
         INSERT OR REPLACE INTO inventory (...) VALUES (...)    (on Turso)
5. db.set_sync_meta('last_push_time', datetime.utcnow().isoformat())
```

#### B.1 — `sync_pull(db, turso)`

```
1. last_pull = db.get_sync_meta('last_pull_time') or '1970-01-01'
2. remote_changes = turso.execute(
       "SELECT * FROM inventory WHERE updated_at > ? ORDER BY updated_at ASC",
       [last_pull])
3. if no remote_changes: return
4. For each remote row:
     - db.apply_remote_change(remote_row)
5. db.set_sync_meta('last_pull_time', datetime.utcnow().isoformat())
```

#### B.1 — `sync(db, turso)`

```
1. sync_push(db, turso)
2. sync_pull(db, turso)
3. Return {"pushed": n, "pulled": m, "timestamp": now}
```

#### B.2 — `initial_sync(db, turso)`

```python
def initial_sync(db, turso):
    local_count = db.get_count()
    remote_result = turso.execute("SELECT COUNT(*) as c FROM inventory")
    remote_count = remote_result['rows'][0]['c'] if remote_result else 0

    if local_count == 0 and remote_count > 0:
        # New device — pull everything from Turso
        ...
    elif local_count > 0 and remote_count == 0:
        # First time uploading — push everything to Turso
        ...
    else:
        # Both have data — merge (last-write-wins via sync())
        sync(db, turso)
```

#### Dry-Run Mode

```python
# python -m tgnj_app.core.sync --dry-run --db copy.db
# Prints what would be pushed/pulled without making any changes.
```

---

### Phase C — Modify `src/tgnj_app/gui/app.py`

#### C.1-C.2 — New Flask Routes

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/getTursoConfig` | Return current Turso URL + whether sync is configured |
| `PATCH` | `/api/setTursoConfig` | Accept `{"turso_url": "...", "turso_token": "..."}` — save to config, create TursoClient, start sync thread |
| `POST` | `/api/runSync` | Trigger a full sync cycle immediately, return result |
| `GET` | `/api/getSyncStatus` | Return `{"last_sync": "...", "configured": true, "pending": 0}` |

#### C.3 — Background Sync Thread

```python
def start_sync_loop(db_instance, interval=30):
    def loop():
        while True:
            if db_instance.turso and db_instance.turso_configured:
                try:
                    sync.sync(db_instance, db_instance.turso)
                except Exception as e:
                    print(f"Sync error: {e}")
            time.sleep(interval)
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
```

- `interval` configurable via `Config.json` key `sync_interval_seconds`
- Starts only after Turso is configured via `/api/setTursoConfig`
- Daemon thread — exits when Flask stops

#### C.4 — Start-up Changes

```python
# After db_instance is created
turso_url, turso_token = load_turso_config()  # reads Config.json
if turso_url and turso_token:
    turso_client = TursoClient(turso_url, turso_token)
    db_instance.turso = turso_client
    db_instance.turso_configured = True
    start_sync_loop(db_instance)
```

#### Updated `Config.json` Format

```json
{
    "db_Path": "C:/Users/you/Documents/inventory.db",
    "turso_url": "https://tgnj-inventory-myorg.turso.io",
    "turso_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "sync_interval_seconds": 30
}
```

All fields optional. Sync is opt-in.

---

### Phase D — Frontend UI

#### D.1 — `index.html` Changes

Add to the header area (alongside the existing DB path):

```html
<div class="turso-config">
  <label for="turso_url">Turso URL:</label>
  <input type="text" id="turso_url" onblur="setTursoConfig()" />
  <label for="turso_token">Token:</label>
  <input type="password" id="turso_token" onblur="setTursoConfig()" />
  <span id="sync-status"></span>
  <button onclick="syncNow()">Sync Now</button>
</div>
```

#### D.2-D.3 — `script.js` Additions

```javascript
async function getTursoConfig() {
    // GET /api/getTursoConfig → populate turso_url, turso_token fields
}

async function setTursoConfig() {
    // PATCH /api/setTursoConfig → save turso config
}

async function syncNow() {
    // POST /api/runSync → update sync-status span with result
}

// On page load: call getTursoConfig()
// Periodic: GET /api/getSyncStatus every 10 seconds to update sync-status
```

---

### Phase D — `scripts/migrate_to_turso.py`

Standalone Python script (runs once per device):

```python
"""
Usage: python scripts/migrate_to_turso.py --db /path/to/inventory.db --url <turso_url> --token <turso_token>

Reads all rows from local inventory.db and pushes them to Turso.
Sets _sync_meta timestamps so subsequent syncs know everything is up-to-date.
"""
```

Steps:
1. Connect to local SQLite
2. Run schema migration (add sync columns)
3. Backfill timestamps for existing rows
4. Push every row to Turso via `INSERT OR REPLACE`
5. Set `last_push_time` and `last_pull_time` in `_sync_meta`
6. Print summary: `Migrated {n} rows to Turso`

---

## Data Flow: End-to-End Example

### Normal operation (Device A adds a stone):

```
1. User fills form in browser, clicks "Add Item"
2. Browser POST /api/addItem → Flask
3. Flask calls db_instance.add_item(...)
4. database.py INSERTs into local SQLite (with updated_at)
5. Within 30 seconds, sync thread:
   a. sync_push(): SELECT updated_at > last_push_time → finds new row
   b. Upserts into Turso via HTTP API
   c. Updates last_push_time
6. Device B's next sync cycle:
   d. sync_pull(): SELECT updated_at > last_pull_time from Turso
   e. Finds Device A's new row
   f. apply_remote_change() → INSERT OR REPLACE into Device B's local SQLite
7. Browser on Device B does not auto-refresh — user refreshes the group
   (No live subscription. Acceptable for inventory work.)
```

### Offline scenario:

```
1. User adds/edit/deletes items — all writes go to local SQLite (works instantly)
2. Background sync thread attempts sync every 30 seconds
3. HTTP request to Turso fails (no internet)
4. Sync silently catches the error, tries again in 30 seconds
5. When internet returns:
   a. sync_push() sends queued changes (identified by updated_at)
   b. sync_pull() gets changes from other devices
   c. Last-write-wins resolves any conflicts
```

### Multi-device conflict:

```
Device A edits row id=5 (shape='round') at 10:00:00
Device B edits row id=5 (shape='pear') at 10:01:00

When both sync:
- Turso stores shape='pear' (Device B's update, later timestamp)
- Device A syncs: sees Turso's updated_at > local → overwrites with 'pear'
- Both devices converge on 'pear'

This is safe for single-user-per-device inventory work.
```

---

## Rollback / Safety

| Scenario | Safeguard |
|---|---|
| Turso unreachable | Local SQLite works fine. Sync retries next cycle. No data loss. |
| Wrong Turso URL/token | `turso_client.execute()` returns None. Sync logs warning, skips. |
| Duplicate sync on first run | `INSERT OR REPLACE` is idempotent. Running `migrate_to_turso.py` twice is safe. |
| Conflict between devices | Last-write-wins on `updated_at` timestamp. No data loss — latest edit wins. |
| Corrupt local DB | The local SQLite file is untouched by sync if Turso is unreachable. |
| Turso data gets wiped | Re-run `migrate_to_turso.py` to re-upload. |

### Code-Level Guardrails

- `turso_client.py` — every HTTP call wrapped in try/except, never raises, returns `None`
- `sync.py` — never mutates local data without verifying Turso responded successfully
- `database.py` — schema migrations wrapped in `try/except OperationalError`
- `app.py` — sync thread errors are logged, never crash Flask

---

## Summary: All Files Changed

| File | Action | Lines |
|---|---|---|
| `src/tgnj_app/core/turso_client.py` | **Create** | ~60 |
| `src/tgnj_app/core/sync.py` | **Create** | ~130 |
| `src/tgnj_app/core/database.py` | **Edit** | ~50 added, ~5 removed |
| `src/tgnj_app/gui/app.py` | **Edit** | ~60 added |
| `src/tgnj_app/gui/templates/index.html` | **Edit** | ~15 added |
| `src/tgnj_app/gui/static/script.js` | **Edit** | ~40 added |
| `src/tgnj_app/gui/static/style.css` | **Edit** | ~10 added |
| `scripts/migrate_to_turso.py` | **Create** | ~80 |
| `pyproject.toml` | **No change** | No new dependencies |

**Total new Python:** ~320 lines
**Total new JS:** ~40 lines
**Total new HTML:** ~15 lines
**New pip deps:** 0

---

## Turso Free Tier Limits vs. Expected Usage

| Metric | Turso Free Tier | Estimated Usage (single inventory table) | Headroom |
|---|---|---|---|
| Storage | 5 GB | <1 MB | 5000x |
| Rows read / mo | 500 million | ~100k | 5000x |
| Rows written / mo | 10 million | ~1k | 10000x |
| Syncs / mo | 3 GB | <10 MB | 300x |
| Databases | 100 | 1 | 100x |

**You are extremely unlikely to hit any free tier limit.**
