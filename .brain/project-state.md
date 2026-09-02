---
type: project
status: active
health: healthy
updated: "2026-08-07"
tags:
  - project/state
---

# Project State — TGNJ Inventory Manager (`tgnj-app`)

## Overview
Local-first inventory management system designed for TakshGems (TGNJ) to manage gemstone inventory, publish bulk Etsy listings with automated S3 photo attachments, and synchronize local SQLite data across multiple laptops using a Turso Cloud DB Master.

## Current Health & Status
- **Health**: `healthy`
- **Active Focus**: Skill setup and memory brain initialization (`obsidian-agent-memory`).

## Architecture & Core Modules
- Architecture: [[architecture]]
- Core Modules:
  - `src/tgnj_app/core/database.py` — Local SQLite cache (`inventory.db`) & atomic outbox queue
  - `src/tgnj_app/core/sync.py` — `OutboxFlusher` (2s push daemon) & remote pull engine (30s interval)
  - `src/tgnj_app/core/turso_client.py` — Zero-dependency Turso libSQL HTTP client
  - `src/tgnj_app/core/etsy_client.py` — Etsy OpenAPI v3 REST client & S3 photo compressor
  - `src/tgnj_app/gui/app.py` — Flask REST API endpoints & UI routing

## Active Next Steps
- [x] Initialize `.brain/` Obsidian vault memory structure.
- [ ] Maintain session logs and Architecture Decision Records (ADRs) during ongoing development.
