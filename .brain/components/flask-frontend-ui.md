---
type: component
status: active
title: "Flask REST Server & Frontend UI"
created: "2026-08-07"
updated: "2026-08-07"
tags:
  - component/frontend
  - backend/flask
  - ui/vanillacss
---

# Flask REST Server & Frontend UI

## Overview
Defined in [`src/tgnj_app/gui/app.py`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/gui/app.py), [`src/tgnj_app/main.py`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/main.py), and static/template assets.

## Architecture

### 1. Application Entry Point ([`main.py`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/main.py))
* Launches background threads (`OutboxFlusher` and `sync_pull` background loops).
* Starts Flask WSGI server on local loopback.
* Launches system default browser pointing to the local Flask application.

### 2. Flask REST Endpoints ([`app.py`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/gui/app.py))
* Item operations: `/api/addItem`, `/api/editItem`, `/api/deleteItem`, `/api/markSold`, `/api/restoreItem`.
* Etsy Hub: OAuth PKCE flow routes (`/etsy/login`, `/etsy/callback`), bulk publisher `/api/etsy/bulk-publish`, section/profile query endpoints, order receipt sync `/api/etsy/sync-orders`.
* Exports: `/api/exportCsv`, `/api/generateLabelsPdf`.

### 3. Frontend UI Assets
* **Templates**: [`index.html`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/gui/templates/index.html) (main inventory table & settings modal), [`etsy_manager.html`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/gui/templates/etsy_manager.html) (Etsy operations hub).
* **JavaScript**: [`script.js`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/gui/static/script.js) (inventory table interactions & instant local UI mutations), [`etsy_hub.js`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/gui/static/etsy_hub.js) (bulk upload UI & order sync).
* **CSS**: [`style.css`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/gui/static/style.css) (dark mode glassmorphism UI styling).
