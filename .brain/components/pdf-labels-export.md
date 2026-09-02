---
type: component
status: active
title: "Jewel Label Generator & CSV Importer/Exporter"
created: "2026-08-07"
updated: "2026-08-07"
tags:
  - component/reporting
  - pdf/reportlab
  - data/csv
---

# Jewel Label Generator & CSV Importer/Exporter

## Overview
Covers PDF jewel tag printing, CSV/TSV inventory exporting, and legacy spreadsheet data migration.

## Modules

### 1. [`labelmaker.py`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/labelmaker.py)
* Uses ReportLab to generate printable PDF jewel label tags for itemized gemstone inventory.
* Includes barcode formatting, SKU group/id placement, weight, dimensions, and shape metrics tailored for physical gemstone tags.

### 2. [`csv_exporter.py`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/csv_exporter.py)
* Generates tab-separated (TSV) and comma-separated (CSV) inventory exports.
* Allows batch filtering by status (`IN_STOCK`, `SOLD`, `LISTED_ETSY`), SKU group, or date range.

### 3. [`legacyUpload.py`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/legacyUpload.py)
* Legacy spreadsheet importer tool to parse legacy gemstone spreadsheets into the modern SQLite database and enqueue `ADD_ITEM` outbox mutations.
