---
type: architecture
status: active
title: "TGNJ System Architecture"
created: "2026-08-07"
updated: "2026-08-07"
tags:
  - architecture
---

# TGNJ System Architecture

## Overview
TGNJ Inventory Manager is a local-first system designed for zero UI latency (< 1ms). Local user operations write directly to a local SQLite database (`inventory.db`) and immediately populate an atomic `outbox` queue table.

## Component Boundaries & Data Flow

```mermaid
graph TD
    UI[Flask GUI / Script.js] -->|Local Mutation < 1ms| DB[(Local SQLite inventory.db)]
    DB -->|Enqueue Payload| Outbox[(Local Outbox Table)]
    OutboxFlusher[OutboxFlusher Daemon 2s] -->|Pop FIFO 50| Outbox
    OutboxFlusher -->|Push Mutations| Turso[(Turso Cloud DB Master)]
    PullEngine[Pull Sync Engine 30s] -->|Pull remote updated_at| Turso
    PullEngine -->|Apply remote diffs| DB
    UI -->|Bulk Draft Listing| EtsyClient[Etsy OpenAPI v3 Client]
    EtsyClient -->|Fetch SKU photos| S3[AWS S3 Bucket]
    EtsyClient -->|Create Listing + Upload Images| EtsyAPI[Etsy OpenAPI v3]
```

## Core Constraints & Invariants
1. **Local-First Speed**: Direct local SQLite writes respond immediately to the UI without awaiting network.
2. **Outbox Enqueue Mandatory**: All REST API endpoints mutating inventory MUST call `db.enqueue_mutation()`.
3. **Field Isolation**: `UPDATE_FIELDS` mutations MUST NOT overwrite `etsy_listing_id` or `status` to prevent field erasure race conditions across multi-laptop setups.
4. **Zero-Dependency HTTP Clients**: `turso_client.py` and `etsy_client.py` use standard library `urllib` to maintain zero binary bloat.

## Related
- [[project-state]]
