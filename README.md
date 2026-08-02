# TGNJ Inventory Manager

🚧 **Status: Under Development** _This is an internal project built specifically for TGNJ and serves as a personal learning initiative to explore Python-based desktop application architecture._

---

## 📖 Overview

TGNJ Inventory Manager is a local-first application designed to track and manage itemized stone data. Rather than relying entirely on complex spreadsheets or cloud-based SaaS, this tool provides a dedicated, searchable interface that runs on your local machine, with seamless background synchronization to the cloud.

### Key Features
- **Local-First Architecture:** Operates entirely locally using an optimized SQLite database (WAL mode).
- **Turso Cloud Sync:** Bi-directional synchronization with Turso (libSQL) ensuring your data is backed up and accessible across devices, with last-write-wins conflict resolution.
- **Data Import & Export:** Built-in tools for uploading legacy CSV data and extracting current database tables to CSV format.
- **Label Generation:** One-click PDF generation for printing custom inventory labels.

### Learning Objectives
- **Hybrid Desktop Apps:** Using `pywebview` to bridge a Flask/web backend with a native window.
- **Cloud-Edge Synchronization:** Implementing robust bi-directional sync engines.
- **Modern Tooling:** Mastering `uv` for lightning-fast, reproducible Python environments.

---

## 🛠 Tech Stack

- **Language:** Python 3.12+
- **Backend:** Flask (RESTful API)
- **Database:** SQLite (Local) / Turso (Cloud Sync)
- **Frontend:** HTML5, CSS3, JavaScript (Jinja2 Templates)
- **Container:** PyWebview
- **Environment:** [uv](https://github.com/astral-sh/uv)

---

## 🚀 Getting Started

### 1. Prerequisites

This project is **cross-platform** (Windows, macOS, Linux). You will need Python installed. We highly recommend using `uv` for dependency management.

### 2. Installation

Clone the repository and install dependencies using `uv`:

```bash
git clone https://github.com/your-username/tgnj-app.git
cd tgnj-app
```

### 3. Running the App

You don't need to manually set up a virtual environment; `uv` handles it automatically:

```bash
uv run src/tgnj_app/main.py
```

### 4. Configuring Turso Sync

1. Create a Turso database and obtain your database URL (`libsql://...`) and auth token.
2. Launch the app and click the **Sync** button in the UI header.
3. Enter your Turso credentials to enable automatic background synchronization.

---

## 📂 Project Structure

```text
tgnj-app/
├── src/
│   └── tgnj_app/
│       ├── core/           # Database wrapper, Turso client, Sync engine, PDF generation
│       ├── gui/            # Flask API, CSS, JS, and Templates
│       │   ├── static/     # Static assets (JS, CSS, Logos)
│       │   └── templates/  # HTML views
│       └── main.py         # Application entry point & window launch
├── scripts/                # Utility scripts (e.g., initial Turso migration)
├── pyproject.toml          # Project metadata & dependencies
└── README.md
```

---

## 📡 Internal API

The GUI communicates with a local Flask server via these primary endpoints:

| Method   | Endpoint                  | Description                               |
| -------- | ------------------------- | ----------------------------------------- |
| `GET`    | `/api/getData/<group>`    | Fetch active items by SKU group.          |
| `POST`   | `/api/addItem`            | Add a new item to the database.           |
| `PATCH`  | `/api/editItem/<id>`      | Update an existing item's details.        |
| `DELETE` | `/api/deleteItem/<id>`    | Soft-delete an item from inventory.       |
| `GET`    | `/api/printPdf/<group>`   | Generate and download a label PDF.        |
| `GET`    | `/api/getCsvData/<group>` | Export group inventory to CSV format.     |
| `POST`   | `/api/UploadLegacyCsv`    | Import inventory data from a legacy CSV.  |
| `PATCH`  | `/api/setTursoConfig`     | Update and save Turso sync credentials.   |
| `POST`   | `/api/runSync`            | Manually trigger a database sync cycle.   |

---

## 📝 Roadmap / To-Do

- [x] Implement bulk CSV import for legacy data.
- [x] Local-first cloud sync with Turso.
- [x] Automated PDF label generation.
- [ ] Add image upload support for stone identification.
- [ ] Refine CSS for better high-DPI display support.
