---
type: component
status: active
updated: "2026-09-02"
tags:
  - component/ebay
  - feature/refresh-engine
---

# eBay Refresh Engine & Operations Hub

## Overview
The **eBay Refresh Engine** analyzes active eBay listings and listing quality reports to solve Cassini algorithmic decay (the 90-day cliff) by executing rolling batch refreshes.

## Core Capabilities
1. **Report Parser (`ebay_refresh.py`):** Parses both eBay Listing Quality Reports (`.xlsx`) and Active Listings Reports (`.csv`).
2. **Automated Urgency Ranking:** Groups listings by SKU prefix (e.g. `A3`, `CP01`, `FS01`, `PP01`) and ranks groups by Refresh Urgency (`urgency_score = stale_percentage * avg_age_days`).
3. **Winner Shielding:** Automatically protects listings with `watchers >= 2`, `sales > 0`, or high daily search impressions from being ended.
4. **`Action=End` Generator:** Produces eBay Seller Hub Reports compliant CSV files (`Action,Item number,EndCode`) to cancel stale listings in bulk.
5. **eBay Operations Hub (`/ebay`):** Flask UI for viewing auto-recommended SKU queues, inspecting triage previews, and downloading action CSVs.
