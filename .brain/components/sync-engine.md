---
type: component
status: active
title: "Turso Sync Engine & OutboxFlusher Daemon"
created: "2026-08-07"
updated: "2026-08-07"
tags:
  - component/sync
  - sync/turso
  - pattern/pubsub
---

# Turso Sync Engine & OutboxFlusher Daemon

## Overview
Defined in [`src/tgnj_app/core/sync.py`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/sync.py) and [`src/tgnj_app/core/turso_client.py`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/turso_client.py). Synchronizes data across multiple laptops using Turso Cloud DB Master (libSQL HTTP API).

## Sync Mechanisms

### 1. Push Sync ([`OutboxFlusher`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/sync.py#L45-L170))
* Daemon thread running every **2 seconds**.
* Pops up to 50 queued outbox rows in FIFO order (`ORDER BY id ASC`).
* Converts outbox payload into targeted field SQL updates on Turso Cloud DB.
* On successful HTTP 200 execution, deletes processed rows from local `outbox` by ID.
* If network or Turso Cloud is offline/unreachable, rows remain safely queued in local SQLite without data loss.

### 2. Pull Sync ([`sync_pull`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/sync.py#L239-L280))
* Daemon thread running every **30 seconds**.
* Queries Turso Master DB for remote rows updated since `last_pull_time` minus 120 seconds (`PULL_OVERLAP_SECONDS = 120`).
* Applies remote diffs into local SQLite cache via [`apply_remote_changes`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/database.py#L237-L323).
* Performs **No-Op optimization**: skips disk write if local view cache data matches incoming remote data.

## Zero-Dependency HTTP Requirement
`turso_client.py` uses standard library `urllib.request` / `urllib.error` exclusively to maintain a lightweight binary footprint without external heavy HTTP dependencies.
