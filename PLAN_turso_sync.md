# TGNJ Inventory — Turso Sync Integration

> **Result:** Multi-device offline-first sync added to TGNJ Inventory Manager using Turso Cloud as a free sync hub, with **zero frontend architecture changes** and **no new pip dependencies**.

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

## What Was Wrong With Syncthing

The user previously synced `inventory.db` across devices using Syncthing.
This worked for single-user-at-a-time, but had fundamental risks:

| Risk | Consequence |
|---|---|
| Split-brain conflicts | `.sync-conflict-*.db` files appear — manual merge required |
| WAL/journal corruption | Syncing a half-written WAL file corrupts the database |
| No row-level granularity | One user's edit locks the entire file |
| No offline-write safety | Must wait for file sync before writing |

**The Turso solution replaces binary-file-sync with row-level database sync — same
outcome (data on all devices), but safe under concurrent use.**

---

## Architecture (Implemented)

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

**Key principles preserved:**
- **Frontend is unchanged** — reads/writes through the same Flask API routes
- **Local SQLite is always the source of truth**
- **Sync is background, incremental, last-write-wins**
- **Turso uses pure Python (`urllib`)** — no new pip dependencies
- **Works fully offline** — sync resumes when connectivity returns
- **Sync is opt-in via the UI** — until you configure Turso, the app behaves exactly as it did before

---

## Phase 0: Turso Account & Database Setup (one-time)

> Requires the Turso CLI. Run these commands once per deployment.

```bash
# Install CLI
curl -sSfL https://get.turso.tech/install.sh | bash

# Create account & database
turso auth login
turso db create tgnj-inventory

# Get credentials
turso db show tgnj-inventory              # → URL
turso db tokens create tgnj-inventory     # → auth token

# Create table
turso db shell tgnj-inventory <<SQL
CREATE TABLE inventory (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_group    TEXT    NOT NULL,
    sku_id       INTEGER NOT NULL,
    shape        TEXT,
    weight       REAL,
    length       INTEGER,
    width        INTEGER,
    depth        INTEGER,
    created_at   TEXT DEFAULT '',
    updated_at   TEXT DEFAULT '',
    is_deleted   INTEGER DEFAULT 0
);
SQL
```

The `created_at`, `updated_at`, and `is_deleted` columns enable incremental sync
(only send changed rows) and soft deletes (propagate deletes across devices).

---

## Implementation Summary

All phases complete. Each item below is a **working feature** in the codebase.

---

### Phase A — turso_client.py + database.py schema  ✅

**Files:** `src/tgnj_app/core/turso_client.py` (new, 116 lines), `src/tgnj_app/core/database.py` (modified, 262 lines)

#### `turso_client.py`

Pure-stdlib HTTP client wrapping Turso's REST API (`POST /v2/pipeline`).

| Feature | Detail |
|---|---|
| `execute(sql, args)` | Single statement, returns parsed dict or `None` |
| `execute_batch(statements)` | Multiple statements in one HTTP call |
| `query_rows(sql, args)` | SELECT convenience — returns `list[dict]` with column names |
| `ensure_schema()` | Idempotent table creation for `inventory` + `_sync_meta` |
| Arg serialization | Auto-detects `null`, `float`, `integer`, `text` types |
| Schema conversion | Auto-converts `libsql://` → `https://` for `urllib` |
| Error handling | `URLError`, `HTTPError`, `TimeoutError`, `json.JSONDecodeError` — all return `None`, never raise |
| Timeout | 60s |

#### `database.py` — Schema Changes

Auto-run in `__init__` (idempotent via try/except):

```sql
ALTER TABLE inventory ADD COLUMN created_at  TEXT DEFAULT '';
ALTER TABLE inventory ADD COLUMN updated_at  TEXT DEFAULT '';
ALTER TABLE inventory ADD COLUMN is_deleted  INTEGER DEFAULT 0;
CREATE TABLE IF NOT EXISTS _sync_meta (key TEXT PRIMARY KEY, value TEXT);
```

#### `database.py` — CRUD Changes

| Method | Change |
|---|---|
| `add_item()` | INSERT includes `created_at`, `updated_at = datetime('now')` |
| `edit_item()` | SET clause includes `updated_at = datetime('now')` + `WHERE COALESCE(is_deleted, 0) = 0` |
| `delete_item()` | **Soft delete**: `UPDATE ... SET is_deleted = 1, updated_at = datetime('now') WHERE ...` |
| `get_items_by_group()` | `WHERE ... AND COALESCE(is_deleted, 0) = 0` |
| `get_item_by_sku()` | `WHERE ... AND COALESCE(is_deleted, 0) = 0` |
| `extract_data()` | `WHERE ... AND COALESCE(is_deleted, 0) = 0` |
| `sold_item()` | **Removed** |

#### `database.py` — New Sync Methods

| Method | Purpose | Lines |
|---|---|---|
| `get_changes_since(timestamp)` | Returns rows modified after timestamp (including soft-deletes) for push | 17 |
| `apply_remote_changes(rows)` | Batch upsert — last-write-wins on `updated_at` comparison per row | 29 |
| `get_sync_meta(key)` | Read from `_sync_meta` table | 13 |
| `set_sync_meta(key, value)` | Write to `_sync_meta` table | 14 |
| `get_all_items()` | All non-deleted rows (for initial sync / migration) | 12 |
| `get_count()` | Non-deleted row count | 13 |
| `purge_old_tombstones(days=30)` | Permanently delete soft-delete rows older than `days` | 16 |

---

### Phase B — sync.py engine ✅

**File:** `src/tgnj_app/core/sync.py` (new, 249 lines)

Bidirectional sync engine with batch operations, dry-run mode, and first-sync logic.

#### `sync_push(db, turso)`

```
1. last_push = get_sync_meta('last_push_time') or '1970-01-01'
2. changes = get_changes_since(last_push)
3. if no changes: return 0
4. Batch upsert rows to Turso (250 per batch via execute_batch)
5. If all pushed: set_sync_meta('last_push_time', now)
```

#### `sync_pull(db, turso)`

```
1. last_pull = get_sync_meta('last_pull_time') or '1970-01-01'
2. remote_rows = query_rows("SELECT * FROM inventory WHERE updated_at >= ?", [last_pull])
3. if None (unreachable) or empty: return 0
4. apply_remote_changes(remote_rows) — last-write-wins per row
5. set_sync_meta('last_pull_time', now)
```

#### `sync(db, turso)`

Runs push then pull, triggers tombstone pruning, returns `{pushed, pulled, timestamp}`.

#### `initial_sync(db, turso)`

Three-way first-sync logic:

| Local | Remote | Action |
|---|---|---|
| Empty | Has data | Pull everything to new device |
| Has data | Empty | Push everything (first upload) |
| Has data | Has data | Merge via last-write-wins sync() |

#### `purge_old_tombstones(db, turso, days=30)`

Deletes `is_deleted=1` rows older than 30 days from both Turso and local SQLite.

#### Dry-Run Mode

```bash
python -m tgnj_app.core.sync --dry-run --db copy.db
```

Prints what would be pushed/pulled without hitting Turso. Uses a no-op `_DryRunTurso` client.

---

### Phase C — app.py routes + sync thread ✅

**File:** `src/tgnj_app/gui/app.py` (modified, 295 lines)

#### New Startup Logic

```python
# After db_instance created:
turso_url, turso_token, sync_interval = load_turso_config()  # reads Config.json
if turso_url and turso_token:
    turso_client = TursoClient(turso_url, turso_token)
    start_sync_loop(sync_interval)  # daemon thread
```

#### New Flask Routes

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/getTursoConfig` | Returns `{configured, turso_url, turso_token}` from Config.json |
| `PATCH` | `/api/setTursoConfig` | Accepts `{turso_url, turso_token}`, persists to Config.json, creates TursoClient, starts sync loop |
| `POST` | `/api/runSync` | Triggers immediate sync, returns `{pushed, pulled, timestamp}` |
| `GET` | `/api/getSyncStatus` | Returns `{configured, last_push, last_pull}` from `_sync_meta` |

#### Background Sync Thread

```python
def start_sync_loop(interval=30):
    # Daemon thread, idempotent (safe to call multiple times)
    while True:
        time.sleep(interval)
        with sync_lock:
            result = sync_engine.sync(db_instance, turso_client)
```

- Thread lock (`sync_lock`) prevents concurrent sync collisions
- Interval configurable via `Config.json` key `sync_interval_seconds`
- Starts only when Turso is configured
- Errors are logged, never crash Flask

---

### Phase D — Frontend UI ✅

#### `index.html` — Turso Config in Header

```html
<div class="turso-config" id="turso-config">
  <input type="text" id="turso_url" placeholder="Turso URL" onblur="saveTursoConfig()" />
  <input type="password" id="turso_token" placeholder="Turso Token" onblur="saveTursoConfig()" />
  <span id="sync-status" class="sync-status"></span>
  <span class="button" id="sync-btn" onclick="syncNow()">Sync</span>
</div>
```

#### `script.js` — Sync UI Functions (110 lines added)

| Function | Purpose |
|---|---|
| `loadTursoConfig()` | GET `/api/getTursoConfig`, populate fields, show status |
| `saveTursoConfig()` | PATCH `/api/setTursoConfig` on blur |
| `syncNow()` | POST `/api/runSync`, button disables during sync, shows result count `↑N ↓N`, refreshes table on change |
| `refreshTableOnly()` | Reloads current group data without touching form fields |
| `pollSyncStatus()` | GET `/api/getSyncStatus` every 10s, shows last sync time, auto-refreshes table on new pulls |
| `setSyncStatus(state, text)` | Updates `#sync-status` element with state class and text |

#### `style.css` — (minor additions needed for `.turso-config`, `.sync-status`)

---

### Phase E — Migration Script ✅

**File:** `scripts/migrate_to_turso.py` (new, 125 lines)

```bash
python scripts/migrate_to_turso.py --db /path/to/inventory.db --url <turso_url> --token <turso_token>
```

Steps:
1. Connect to local SQLite
2. Run idempotent schema migration (add sync columns, create `_sync_meta`)
3. Backfill NULL/empty timestamps on existing rows
4. Push every non-deleted row to Turso via `INSERT OR REPLACE`
5. Set `last_push_time` and `last_pull_time` in `_sync_meta`
6. Safe to run multiple times — idempotent

---

## Data Flow: How It Works

### Normal operation (Device A adds a stone):

```
1. User fills form in browser, clicks "Add Item"
2. Browser POST /api/addItem → Flask
3. Flask calls db_instance.add_item(...)
4. database.py INSERTs into local SQLite (with updated_at)
5. Within 30 seconds, sync thread:
   a. sync_push(): SELECT updated_at > last_push_time → finds new row
   b. Upserts into Turso via HTTP API (batch pipeline)
   c. Updates last_push_time
6. Device B's next sync cycle:
   d. sync_pull(): SELECT updated_at > last_pull_time from Turso
   e. Finds Device A's new row
   f. apply_remote_changes() → INSERT OR REPLACE into Device B's local SQLite
7. Device B's UI auto-refreshes if last_pull_time changed (pollSyncStatus detects it)
```

### Offline scenario:

```
1. User adds/edit/deletes items — all writes go to local SQLite (works instantly)
2. Background sync thread attempts sync every 30 seconds
3. HTTP request to Turso fails (no internet)
4. Sync silently catches the error, tries again in 30 seconds
5. When internet returns:
   a. sync_push() sends queued changes (identified by updated_at timestamps)
   b. sync_pull() gets changes from other devices
   c. Last-write-wins resolves any conflicts
6. No data loss — local SQLite is always the source of truth
```

### Multi-device conflict:

```
Device A edits row id=5 (shape='round') at 10:00:00
Device B edits row id=5 (shape='pear') at 10:01:00

When both sync:
- Turso stores shape='pear' (Device B's update, later timestamp)
- Device A syncs: sees Turso's updated_at > local → overwrites with 'pear'
- Both devices converge on 'pear'

Safe for single-user-per-device inventory work.
```

### Tombstone pruning (automatic):

```
- Row deleted via soft delete: is_deleted = 1, updated_at = now
- Sync propagates DELETE to Turso (actually an INSERT OR REPLACE with is_deleted=1)
  → Turso: row is_deleted = 1 → effectively gone from queries
  → Other devices pull: row with is_deleted=1 → soft-deleted locally
- After 30 days: purge_old_tombstones() permanently DELETEs from both sides
```

---

## Rollback / Safety

| Scenario | Safeguard |
|---|---|
| Turso unreachable | Local SQLite works fine. Sync retries next cycle. No data loss. |
| Wrong Turso URL/token | `turso_client.execute()` returns None. Sync logs warning, skips. |
| Duplicate sync on first run | `INSERT OR REPLACE` is idempotent. Running `migrate_to_turso.py` twice is safe. |
| Conflict between devices | Last-write-wins on `updated_at` timestamp. Latest edit wins. |
| Corrupt local DB | The local SQLite file is untouched by sync if Turso is unreachable. |
| Turso data gets wiped | Re-run `migrate_to_turso.py` to re-upload. |

### Code-Level Guardrails

- `turso_client.py` — every HTTP call wrapped in try/except, never raises, returns `None`
- `sync.py` — never mutates local data without verifying Turso responded successfully
- `database.py` — schema migrations wrapped in `try/except OperationalError` (idempotent)
- `app.py` — sync thread errors are logged, never crash Flask
- `app.py` — `sync_lock` prevents concurrent sync cycles

---

## All Files Changed

| File | Action | Lines |
|---|---|---|
| `src/tgnj_app/core/turso_client.py` | **Create** | 116 |
| `src/tgnj_app/core/sync.py` | **Create** | 249 |
| `src/tgnj_app/core/database.py` | **Edit** | +140 added (schema migration, CRUD changes, 7 new sync methods), -5 removed (sold_item) |
| `src/tgnj_app/gui/app.py` | **Edit** | +110 added (Turso config loader, 4 new routes, sync thread, startup init) |
| `src/tgnj_app/gui/templates/index.html` | **Edit** | +15 added (Turso config fields in header) |
| `src/tgnj_app/gui/static/script.js` | **Edit** | +110 added (loadTursoConfig, saveTursoConfig, syncNow, refreshTableOnly, pollSyncStatus, setSyncStatus) |
| `src/tgnj_app/gui/static/style.css` | **Minor edit** | Styling for `.turso-config`, `.sync-status`, `.turso-input` |
| `scripts/migrate_to_turso.py` | **Create** | 125 |
| `pyproject.toml` | **No change** | No new dependencies |

**Total new Python:** ~490 lines (turso_client.py + sync.py + migrate_to_turso.py + database.py additions + app.py additions)
**Total new JS:** ~110 lines
**Total new HTML:** ~15 lines
**New pip deps:** 0

---

## Turso Free Tier Limits vs. Expected Usage

| Metric | Turso Free Tier | Estimated Usage (single inventory table) | Headroom |
|---|---|---|---|
| Storage | 5 GB | <1 MB | 5000x |
| Rows read / mo | 500 million | ~100k (poll + sync queries) | 5000x |
| Rows written / mo | 10 million | ~1k (business edits per month) | 10000x |
| Syncs / mo | 3 GB | <10 MB (tiny row payloads) | 300x |
| Databases | 100 | 1 | 100x |

**Extremely unlikely to hit any free tier limit.**
