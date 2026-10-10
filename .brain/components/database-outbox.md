---
type: component
status: active
title: "Database Schemas & Outbox Queue Engine"
created: "2026-08-07"
updated: "2026-08-07"
tags:
  - component/database
  - database/sqlite
  - pattern/outbox
---

# Database Schemas & Outbox Queue Engine

## Overview
Defined in [`src/tgnj_app/core/database.py`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/database.py). Handles local SQLite database cache (`inventory.db`) with zero UI latency (< 1ms).

## Database Schemas

### 1. `inventory` Table
Natural compound key (`sku_group`, `sku_id`) e.g. `LAPIS-001`.

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
- `IN_STOCK`: Gemstone available in inventory.
- `DRAFT_ETSY` / `LISTED_ETSY`: Listing created or live on Etsy.
- `SOLD`: Item marked sold via manual entry or order receipt sync.
- `is_deleted = 1`: Soft-deleted tombstone (purged after 30 days).

### 2. `outbox` Table
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
* `ADD_ITEM`: Initial dimension creation.
* `UPDATE_FIELDS`: Updates ONLY dimension fields (`shape`, `weight`, `length`, `width`, `depth`). **Field Isolation: Forbidden fields (`etsy_listing_id`, `status`) are stripped to prevent field erasure.**
* `DELETE_ITEM`: Soft-deletes row (`is_deleted = 1`).
* `ASSIGN_ETSY_LISTING`: Sets `status`, `etsy_listing_id`, and `updated_at`.
* `MARK_SOLD`: Sets `status`, `sold_price`, `sold_channel`, `sold_at`, and `updated_at`.
* `RESTORE_ITEM` / `RESET_ETSY_DRAFT`: Restores item status back to `IN_STOCK`.

### 3. Metadata Tables
* `_sync_meta` (`key TEXT PRIMARY KEY, value TEXT`): Tracks sync watermarks (`last_push_time`, `last_pull_time`).
* `_etsy_config` (`key TEXT PRIMARY KEY, value TEXT`): Stores OAuth access tokens, refresh tokens, PKCE verifiers, API keys, and Etsy shop ID.

## Core Rules & Invariants
1. Every REST API endpoint mutating inventory state MUST enqueue an outbox row via `db.enqueue_mutation()`.
2. Direct disk write skipped if incoming remote pull data is identical to local cache data (No-Op optimization).
