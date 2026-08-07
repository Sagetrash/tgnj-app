# TGNJ Inventory Manager

🚧 **Status: Active Development** — *An internal gemstone inventory, Etsy OpenAPI v3 integration, and multi-device cloud synchronization manager for TakshGems (TGNJ).*

---

## 📖 Overview

**TGNJ Inventory Manager** is a local-first application designed to track itemized gemstone inventory and seamlessly manage Etsy shop listings. Built for sub-millisecond local UI response times (< 1ms), all user operations execute instantly against a local SQLite database view cache while background threads handle atomic mutations to **Turso Cloud DB Master** and integration with **Etsy OpenAPI v3**.

### Key Features
- ⚡ **Local-First Architecture:** Instant UI responses (< 1ms) for reads and writes (`addItem`, `editItem`, `deleteItem`, `markSold`).
- 🔄 **Always-Enqueue Outbox Pattern:** Local writes atomically append structured JSON mutations to a local `outbox` table. A background `OutboxFlusher` thread drains mutations to Turso Cloud Master DB in strict FIFO order every 2 seconds.
- ☁️ **Turso Cloud Master DB:** Turso serves as the single source of truth. Devices pull master updates every 30 seconds (with a 120s lookback overlap buffer) to keep local view caches 100% synchronized across laptops without race conditions or field erasure.
- 🧡 **Etsy Operations Hub:**
  - **OAuth 2.0 PKCE Authorization:** Secure consent flow without storing static passwords.
  - **Bulk Draft Publisher:** Batch push gemstones to Etsy with automatic category mapping (Cabochons `6648`), shipping profiles, readiness states, and custom property tags.
  - **S3 Photo Fetch & Optimization:** Concurrently downloads `{SKU}A.jpg` and `{SKU}B.jpg` from Amazon S3 (`tgnj-pictures.s3.us-east-1.amazonaws.com`), optimizes images to max 2000px, and uploads to Etsy listings.
  - **Sales & Receipt Sync:** Automatically syncs Etsy orders, updating gemstone statuses to `SOLD` with sold price and channel tracking.
  - **Live Inventory Cross-Check:** Detects deleted Etsy drafts with a 2-minute grace period buffer to protect against Etsy search index lag.
- 🏷️ **Label Generation:** One-click PDF label generation for printing custom inventory labels.
- 📊 **Import & Export:** Export SKU group inventory to TSV/CSV format or import legacy spreadsheets.

---

## 🏗 System Architecture

```text
                       [ User Action / UI ]
                                │
                                ▼
                 ┌──────────────────────────────┐
                 │ Local SQLite Database        │  <-- Instant UI response (< 1ms)
                 │ ├─ inventory (View Cache)    │
                 │ └─ outbox (Mutation Queue)   │
                 └──────────────┬───────────────┘
                                │
                    Background Threads (Daemon)
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌───────────────────────┐ ┌───────────────────────┐
        │ OutboxFlusher Thread  │ │ Pull Sync Thread      │
        │ (Drains FIFO queue to │ │ (Pulls Master updates │
        │  Turso every 2s)      │ │  every 30s)           │
        └───────────┬───────────┘ └───────────┬───────────┘
                    │                         │
                    └───────────┬─────────────┘
                                ▼
                 ┌──────────────────────────────┐
                 │ Turso Cloud Master DB        │  (Single Source of Truth)
                 └──────────────────────────────┘
```

---

## 🛠 Tech Stack

- **Language:** Python 3.12+
- **Backend Framework:** Flask (RESTful API & Web Routes)
- **Database Engine:** SQLite (Local View Cache & Outbox Queue) / Turso (Cloud Master DB via libSQL HTTP API)
- **Integrations:** Etsy OpenAPI v3 REST API (OAuth 2.0 PKCE), Amazon S3 Image Hosting
- **Frontend Stack:** HTML5, Vanilla CSS3, JavaScript (Jinja2 Templates)
- **PDF Generation:** ReportLab
- **Package & Environment Manager:** [uv](https://github.com/astral-sh/uv)

---

## 🚀 Getting Started

### 1. Prerequisites & Installation

Clone the repository and ensure Python 3.12+ is installed along with `uv`:

```bash
git clone https://github.com/your-username/tgnj-app.git
cd tgnj-app
```

### 2. Running the Application

Launch the application using `uv`:

```bash
uv run src/tgnj_app/main.py
```

The application will start the Flask server at `http://127.0.0.1:5000` and automatically open your default browser.

### 3. Configuring Turso Sync & Etsy Credentials

Open the **Settings Modal** from the UI header:
1. **Turso Cloud Sync:** Enter your Turso database URL (`libsql://your-db.turso.io`) and Auth Token.
2. **Etsy Operations:** Configure your Etsy API Keystring (Client ID), Shared Secret, and Shop ID (`takshgems`), then click **Connect TakshGems Shop** to complete OAuth authorization.

---

## 📡 Key REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/getData/<sku_group>` | Fetch active items by SKU group |
| `POST` | `/api/addItem` | Add stone to local SQLite & enqueue `ADD_ITEM` outbox mutation |
| `PATCH` | `/api/editItem/<group>/<id>` | Update stone dimensions & enqueue `UPDATE_FIELDS` outbox mutation |
| `DELETE` | `/api/deleteItem/<group>/<id>` | Soft-delete stone & enqueue `DELETE_ITEM` outbox mutation |
| `POST` | `/api/markSold/<group>/<id>` | Mark stone as `SOLD` & enqueue `MARK_SOLD` outbox mutation |
| `POST` | `/api/restoreItem/<group>/<id>` | Restore stone to `IN_STOCK` & enqueue `RESTORE_ITEM` outbox mutation |
| `POST` | `/api/etsy/bulkPush` | Publish draft listings to Etsy & upload S3 photos |
| `POST` | `/api/etsy/syncOrders` | Sync Etsy sales & receipts across local and cloud databases |
| `GET` | `/api/etsy/liveStats` | Fetch live Etsy stats & cross-check deleted drafts |
| `GET` | `/api/printPdf/<sku_group>` | Generate and download custom label PDF |
| `GET` | `/api/getCsvData/<sku_group>` | Export group inventory to CSV format |
| `PATCH` | `/api/setTursoConfig` | Update Turso URL & Auth Token configuration |
| `POST` | `/api/runSync` | Trigger an immediate manual pull sync from Turso Master |

---

## 🧪 Testing

Run the test suite using `uv`:

```bash
uv run python -m unittest discover tests
```

---

## 📂 Project Structure

```text
tgnj-app/
├── src/
│   └── tgnj_app/
│       ├── main.py              # App entry point & browser launcher
│       ├── core/
│       │   ├── database.py      # SQLite view cache & outbox queue helper
│       │   ├── sync.py          # OutboxFlusher daemon & Turso pull sync engine
│       │   ├── turso_client.py   # Turso libSQL HTTP client
│       │   ├── etsy_client.py    # Etsy OpenAPI v3 REST client (OAuth PKCE & S3)
│       │   ├── csv_exporter.py   # CSV export utilities
│       │   └── labelmaker.py     # PDF label generation
│       └── gui/
│           ├── app.py           # Flask REST API & web routes
│           ├── static/          # CSS, JS (main & etsy hub)
│           └── templates/       # HTML views
├── tests/
│   └── test_tgnj_app.py         # Unit test suite
├── pyproject.toml               # Project dependencies & configuration
├── AGENTS.md                    # AI agent context & guidelines
└── README.md                    # Project overview & documentation
```

For developer guidelines, database invariants, and AI agent prompt context, see [AGENTS.md](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/AGENTS.md).


