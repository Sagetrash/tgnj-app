# TGNJ Inventory Manager

🚧 **Status: Under Development** _This is an internal project built specifically for TGNJ and serves as a personal learning initiative to explore Python-based desktop application architecture._

---

## 📖 Overview

TGNJ Inventory Manager is a lightweight, local-first application designed to track and manage itemized stone data. Rather than using complex spreadsheets or cloud-based SaaS, this tool provides a dedicated, searchable interface that runs entirely on your local machine.

### Learning Objectives

- **Hybrid Desktop Apps:** Using `pywebview` to bridge a Flask/web backend with a native window.
- **Database Optimization:** Implementing SQLite **Write-Ahead Logging (WAL)** for faster performance on local drives.
- **Modern Tooling:** Mastering `uv` for lightning-fast, reproducible Python environments.

---

## 🛠 Tech Stack

- **Language:** Python 3.12+
- **Backend:** Flask (RESTful API)
- **Database:** SQLite (Optimized with WAL mode)
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
git clone [https://github.com/your-username/tgnj-app.git](https://github.com/your-username/tgnj-app.git)
cd tgnj-app

```

### 3. Running the App

You don't need to manually set up a virtual environment; `uv` handles it automatically:

```bash
uv run src/tgnj_app/main.py

```

---

## 📂 Project Structure

```text
tgnj-app/
├── src/
│   └── tgnj_app/
│       ├── core/           # Database wrapper & SQL logic
│       ├── gui/            # Flask API, CSS, and Templates
│       └── main.py         # Application entry point & window launch
├── pyproject.toml          # Project metadata & dependencies
└── README.md

```

---

## 📡 Internal API

The GUI communicates with a local Flask server via these endpoints:

| Method   | Endpoint               | Description                     |
| -------- | ---------------------- | ------------------------------- |
| `GET`    | `/api/getData/<group>` | Fetch items by SKU group.       |
| `POST`   | `/api/addItem`         | Add a new item to the database. |
| `DELETE` | `/api/deleteItem/<id>` | Remove an item from inventory.  |

---

## 📝 Roadmap / To-Do

- [ ] Implement bulk CSV import for legacy data.
- [ ] Add image upload support for stone identification.
- [ ] Refine CSS for better high-DPI display support.
- [ ] Automated local database backups.

---

## 📜 License

Internal use only. (Or insert MIT/GPL here if you plan to open-source the code later).

```
