# TGNJ Inventory Manager

🚧 **Status: Active Development** _An internal inventory, Etsy integration, and multi-device cloud synchronization manager for TGNJ._

---

## 📖 Overview

TGNJ Inventory Manager is a local-first application designed to track itemized gemstone inventory and manage Etsy shop listings seamlessly. Rather than relying on spreadsheets, this application provides a dedicated interface that runs locally with instant UI response times (< 1ms) and background synchronization to **Turso Cloud DB Master**.

### Key Features
- **Always-Enqueue Outbox Architecture:** Local writes (`addItem`, `editItem`, `deleteItem`, `markSold`, `bulkPush`) append atomic mutations to a local SQLite `outbox` queue and respond instantly. A background `OutboxFlusher` thread drains mutations to Turso Cloud Master in strict FIFO order every 2 seconds.
- **Turso Cloud Master DB:** Turso serves as the single source of truth. Devices pull master updates every 30 seconds to keep local view caches 100% mirrored across laptops without race conditions or field-erasure bugs.
- **Etsy Integration Hub:**
  - **OAuth 2.0 PKCE Authorization:** Connect your Etsy seller account safely.
  - **Bulk Draft Publishing:** Push gemstone batches to Etsy with auto-matched shop sections, shipping profiles, custom property tags, and S3 photo attachments.
  - **Order & Sales Sync:** Fetch shop receipts and sold listings automatically, marking stones as `SOLD` with channel and price tracking.
  - **Live Inventory Cross-Check:** Detect deleted Etsy drafts with a 2-minute grace period buffer (protecting against Etsy search index lag).
- **Label Generation:** One-click PDF generation for printing custom inventory labels.
- **Data Import & Export:** Built-in tools for uploading legacy CSV data and exporting inventory groups.

---

## 🛠 Tech Stack

- **Language:** Python 3.12+
- **Backend:** Flask (RESTful API)
- **Database:** SQLite (Local View Cache & Outbox Queue) / Turso (Cloud Master DB)
- **Integrations:** Etsy v3 REST API (OAuth 2.0 PKCE, S3 Image Hosting)
- **Frontend:** HTML5, CSS3, JavaScript (Jinja2 Templates)
- **Container / Window:** PyWebview / Browser
- **Environment & Package Manager:** [uv](https://github.com/astral-sh/uv)

---

## 🚀 Getting Started

### 1. Prerequisites

Python 3.12+ installed. We recommend using `uv` for lightning-fast dependency management:

```bash
git clone https://github.com/your-username/tgnj-app.git
cd tgnj-app
```

### 2. Running the App

```bash
uv run src/tgnj_app/main.py
```

### 3. Configuring Turso Cloud Sync & Etsy Integration

1. **Turso Sync**: Enter your Turso database URL (`libsql://...`) and auth token via `/api/setTursoConfig` or the UI header.
2. **Etsy Integration**: Configure your Etsy API key, shared secret, and shop ID on the Etsy Hub page (`/etsy`), then authorize via OAuth.

---

## 📡 Internal API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/getData/<group>` | Fetch active items by SKU group. |
| `POST` | `/api/addItem` | Add stone to local SQLite & enqueue `ADD_ITEM` outbox mutation. |
| `PATCH` | `/api/editItem/<group>/<id>` | Update stone dimensions & enqueue `UPDATE_FIELDS` outbox mutation. |
| `DELETE` | `/api/deleteItem/<group>/<id>` | Soft-delete stone & enqueue `DELETE_ITEM` outbox mutation. |
| `POST` | `/api/markSold/<group>/<id>` | Mark stone as `SOLD` & enqueue `MARK_SOLD` outbox mutation. |
| `POST` | `/api/restoreItem/<group>/<id>` | Restore stone to `IN_STOCK` & enqueue `RESTORE_ITEM` outbox mutation. |
| `POST` | `/api/etsy/bulkPush` | Publish draft listings to Etsy & enqueue `ASSIGN_ETSY_LISTING` mutations. |
| `POST` | `/api/etsy/syncOrders` | Sync Etsy sales & receipts, updating sold statuses across databases. |
| `GET` | `/api/etsy/liveStats` | Fetch live Etsy stats & cross-check deleted drafts (2-min buffer). |
| `GET` | `/api/printPdf/<group>` | Generate and download custom label PDF. |
| `GET` | `/api/getCsvData/<group>` | Export group inventory to TSV/CSV format. |
| `PATCH` | `/api/setTursoConfig` | Save Turso URL & Auth Token. |
| `POST` | `/api/runSync` | Trigger a manual pull sync from Turso Master. |

---

## 📂 Project Structure

```text
tgnj-app/
├── src/
│   └── tgnj_app/
│       ├── core/
│       │   ├── database.py      # SQLite view cache & outbox queue
│       │   ├── sync.py          # OutboxFlusher & Turso pull sync engine
│       │   ├── turso_client.py   # Turso libSQL HTTP client
│       │   ├── etsy_client.py    # Etsy v3 API client (OAuth PKCE, listings)
│       │   ├── csv_exporter.py   # CSV export utilities
│       │   └── labelmaker.py     # PDF label generation
│       ├── gui/
│       │   ├── app.py           # Flask REST API & web routes
│       │   ├── static/          # CSS, JS (main & etsy hub)
│       │   └── templates/       # HTML views
│       └── main.py              # App entry point
├── tests/
│   └── test_tgnj_app.py         # Unit test suite
├── pyproject.toml
└── README.md
```

