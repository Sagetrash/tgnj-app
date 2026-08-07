# AGENTS.md — Developer & AI Agent Context Guide

This document serves as the authoritative guide for AI agents and developers building, refactoring, or maintaining the **TGNJ Inventory Manager** (`tgnj-app`) codebase.

---

## 1. System Mission & Core Domain

**TGNJ Inventory Manager** is a local-first management system designed for TakshGems (TGNJ) to manage itemized gemstone inventory, publish bulk Etsy draft listings with S3 photo attachments, and synchronize data across multiple laptops using a **Turso Cloud DB Master**.

### Key Architectural Pillars:
1. **Local-First Speed (< 1ms UI latency):** All user mutations (`addItem`, `editItem`, `deleteItem`, `markSold`) write directly to a local SQLite database cache (`inventory.db`) and respond immediately to the UI.
2. **Always-Enqueue Outbox Pattern:** Local mutations atomically insert JSON payloads into a local SQLite `outbox` queue table. A background thread ([OutboxFlusher](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/sync.py#L45-L170)) drains mutations to Turso Master DB in strict FIFO order every 2 seconds.
3. **Turso Master DB (Single Source of Truth):** Turso Cloud DB (libSQL HTTP API) serves as the master store. Devices pull remote changes every 30 seconds to mirror state without field erasure or multi-laptop race conditions.
4. **Etsy OpenAPI v3 Hub:** Connects to Etsy via OAuth 2.0 PKCE. Manages bulk draft listing creation, automated S3 photo fetching/compression (`{SKU}A.jpg` and `{SKU}B.jpg`), shop section assignment, shipping profiles, custom property tags, and order receipt synchronization.

---

## 2. Codebase Map & Module Responsibilities

```text
tgnj-app/
├── src/
│   └── tgnj_app/
│       ├── main.py                  # Application entry point & browser launcher
│       ├── core/
│       │   ├── database.py          # Local SQLite DB manager & outbox queue helper
│       │   ├── sync.py              # OutboxFlusher daemon & Turso pull sync engine
│       │   ├── turso_client.py       # Zero-dependency Turso libSQL HTTP API client
│       │   ├── etsy_client.py        # Etsy OpenAPI v3 REST client (OAuth PKCE & S3)
│       │   ├── labelmaker.py         # ReportLab PDF label generator
│       │   ├── csv_exporter.py       # Inventory TSV/CSV exporter
│       │   └── legacyUpload.py       # Legacy spreadsheet importer
│       └── gui/
│           ├── app.py               # Flask REST API endpoints & route handlers
│           ├── templates/
│           │   ├── index.html       # Inventory view & settings modal HTML template
│           │   └── etsy_manager.html # Etsy Operations Hub & Bulk Publisher HTML
│           └── static/
│               ├── script.js        # Main inventory UI logic & settings modal JS
│               ├── etsy_hub.js      # Bulk publisher UI & order sync JS
│               └── style.css        # Shared app styling
├── tests/
│   └── test_tgnj_app.py             # Complete unit test suite (Unittest)
├── pyproject.toml                   # Project metadata & uv dependencies
├── README.md                        # High-level overview & setup instructions
└── AGENTS.md                        # AI Agent & developer technical context guide
```

---

## 3. Database Schemas & Key Invariants

The application uses **SQLite** locally ([database.py](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/database.py)) and mirrors the schema on **Turso Cloud DB** ([turso_client.py](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/turso_client.py)).

### A. `inventory` Table
Natural compound key: (`sku_group`, `sku_id`) e.g., `LAPIS-001`.

```sql
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_group TEXT NOT NULL,
    sku_id INTEGER NOT NULL,
    shape TEXT,
    weight REAL,
    length INTEGER,
    width INTEGER,
    depth INTEGER,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    is_deleted INTEGER DEFAULT 0,
    status TEXT DEFAULT 'IN_STOCK',
    etsy_listing_id TEXT DEFAULT '',
    sold_price REAL DEFAULT 0.0,
    sold_channel TEXT DEFAULT '',
    sold_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_inventory_updated_at ON inventory(updated_at);
```

#### Status Lifecycle:
- `IN_STOCK`: Item active in inventory, ready to be listed or printed.
- `DRAFT_ETSY` / `LISTED_ETSY`: Item uploaded to Etsy as a draft or published listing.
- `SOLD`: Item marked as sold (via Etsy receipt sync or manual sale entry).
- `is_deleted = 1`: Soft-deleted tombstone. Purged after 30 days.

### B. `outbox` Table
```sql
CREATE TABLE IF NOT EXISTS outbox (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    sku_group  TEXT NOT NULL,
    sku_id     INTEGER NOT NULL,
    action     TEXT NOT NULL,
    payload    TEXT NOT NULL
);
```

#### Mutation Action Types:
- `ADD_ITEM`: Payload contains full initial stone dimensions.
- `UPDATE_FIELDS`: Payload contains ONLY changed dimension fields (`shape`, `weight`, `length`, `width`, `depth`). **Forbidden fields (`etsy_listing_id`, `status`) are stripped to prevent field erasure.**
- `DELETE_ITEM`: Soft-deletes row (`is_deleted = 1`).
- `ASSIGN_ETSY_LISTING`: Payload contains `status`, `etsy_listing_id`, and `updated_at`.
- `MARK_SOLD`: Payload contains `status`, `sold_price`, `sold_channel`, `sold_at`, and `updated_at`.
- `RESTORE_ITEM` / `RESET_ETSY_DRAFT`: Restores item back to `IN_STOCK`.

### C. Metadata Tables
- `_sync_meta` (`key TEXT PRIMARY KEY, value TEXT`): Tracks sync watermarks (`last_push_time`, `last_pull_time`).
- `_etsy_config` (`key TEXT PRIMARY KEY, value TEXT`): Stores Etsy API keys, shared secrets, OAuth access tokens, refresh tokens, PKCE verifiers, and shop ID.

---

## 4. Synchronization Protocols & Rules

### A. Push Sync ([OutboxFlusher](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/sync.py#L45-L170))
1. When local API mutates inventory, it MUST call `db.enqueue_mutation(sku_group, sku_id, action, payload)`.
2. `OutboxFlusher` runs every 2 seconds, popping up to 50 rows in FIFO order (`ORDER BY id ASC`).
3. Converts mutations to targeted field SQL updates on Turso.
4. On success, flushes deleted entries from the local `outbox` by ID. If Turso is unreachable, entries remain queued safely.

### B. Pull Sync ([sync_pull](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/sync.py#L239-L280))
1. Runs every 30 seconds in background loop.
2. Queries Turso for `SELECT * FROM inventory WHERE updated_at >= ?` using `last_pull_time` minus 120 seconds (`PULL_OVERLAP_SECONDS = 120`).
3. Calls [apply_remote_changes](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/database.py#L237-L323). If local view cache data is identical to incoming remote data, disk write is skipped (No-Op optimization).

---

## 5. Etsy OpenAPI v3 & Image Integration

- **OAuth 2.0 PKCE:** PKCE pair generated via [EtsyClient.generate_pkce_pair()](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/etsy_client.py#L26-L34). Scopes used: `listings_r listings_w shops_r shops_w transactions_r`.
- **S3 Photo Fetch & Optimization:** During bulk push ([upload_s3_photos_for_listing](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/etsy_client.py#L352-L405)), the app concurrently fetches `https://tgnj-pictures.s3.us-east-1.amazonaws.com/{group}/{SKU}A.jpg` and `B.jpg`. If image > 1MB, compresses to max 2000px at 90% JPEG quality before sending multipart form-data to Etsy.
- **Draft Deletion Guard:** [sync_deleted_etsy_drafts](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/gui/app.py#L716-L757) includes safety guards: if Etsy API fails or returns empty/401 results, it NEVER resets local listed statuses.

---

## 6. Testing & Development Instructions

### Running Tests
Run the test suite using `uv`:

```bash
uv run python -m unittest discover tests
```

### Critical Rules for AI Agents:
1. **Never Bypass Outbox Enqueueing:** Every new REST API endpoint or method mutating inventory state MUST enqueue an outbox mutation via `db.enqueue_mutation()`.
2. **Field Isolation in Outbox:** Never allow outbox `UPDATE_FIELDS` mutations to touch status or listing fields. Strictly enforce `ALLOWED_EDIT_FIELDS` in `sync.py`.
3. **Zero External Dependencies for HTTP:** Keep `turso_client.py` and `etsy_client.py` using Python standard library `urllib.request` / `urllib.error` to maintain low binary footprint.
4. **Preserve Clickable File Links:** When reporting work or outputting markdown, always format clickable file links using standard markdown `[filename](file:///path/to/file)` without nested backticks.
5. **Use TEST SKU Group for Integration Testing:** When performing live API or database integration testing, ALWAYS use the dedicated `TEST` SKU group (`sku_group = 'TEST'`) to ensure production gemstone inventory is never altered or polluted.
6. **Enforce Proper Git Standards:** Follow conventional commit standards (`feat:`, `fix:`, `test:`, `docs:`), perform changes on dedicated feature branches, and run pre-commit test verification before creating commits.

---

## 7. Git Workflow & Version Control Guidelines

### A. Branch Management
- **Feature Branches:** Perform development and refactoring on dedicated feature branches (e.g., `feature/ebay-integration`, `fix/sync-watermark`) rather than committing directly to `main`.
- **Branch Naming:** Use concise, lower-case, hyphen-separated branch names prefixed with `feature/`, `fix/`, `docs/`, or `refactor/`.

### B. Commit Standards & Conventional Commits
- **Conventional Commit Prefixes:**
  - `feat:` New feature or capability additions.
  - `fix:` Bug fixes, error handling, or schema corrections.
  - `test:` Unit test additions or test suite updates.
  - `docs:` Documentation or `AGENTS.md` context guide updates.
  - `refactor:` Code restructuring without functional changes.
- **Atomic Scope:** Keep commits focused and atomic. Group related code modifications, corresponding unit tests, and documentation into a single logical commit.

### C. Pre-Commit Verification Rules
1. **Never Commit Broken Code:** Always execute unit test suite (`uv run python -m unittest discover tests`) and verify all tests pass prior to staging or committing.
2. **Audit Staged Files:** Run `git status` and `git diff` to verify that temporary data files, test databases (`inventory.db`), API credentials, or scratch scripts are not staged.


