# INDEX — TGNJ Inventory Manager Brain

> Machine registry: `registry.yaml`

## Core Overview
- [[project-state]] — Current project status, health, module map, and roadmap
- [[architecture]] — High-level system architecture and component interaction model

## Component Specifications (Full Depth)
- [[components/database-outbox]] — Local SQLite cache, schemas (`inventory`, `outbox`), outbox mutation types, and field isolation rules
- [[components/sync-engine]] — Turso Cloud DB HTTP client, 2s `OutboxFlusher` push daemon, 30s `sync_pull` engine, and no-op diffing
- [[components/etsy-s3-integration]] — Etsy OpenAPI v3 OAuth 2.0 PKCE, bulk draft publisher, AWS S3 image compression, and draft guard safety rules
- [[components/pdf-labels-export]] — ReportLab PDF jewel tag labelmaker, TSV/CSV inventory exporter, and legacy spreadsheet importer
- [[components/flask-frontend-ui]] — Application entry point, Flask REST API endpoints, HTML templates, dynamic JS logic, and styling
- [[components/ebay-refresh-engine]] — eBay quality report parser, automated SKU urgency ranking, winner protection shield, and Action=End CSV generator

## Architectural Decisions
<!-- Add decision records in decisions/ folder -->

## Session Logs
- [[session-logs/2026-08-07]] — Session log for 2026-08-07
- [[session-logs/2026-09-02]] — Session log for 2026-09-02
