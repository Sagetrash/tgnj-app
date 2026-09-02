---
type: component
status: active
title: "Etsy OpenAPI v3 & AWS S3 Photo Integration"
created: "2026-08-07"
updated: "2026-08-07"
tags:
  - component/etsy
  - integration/s3
  - auth/oauth2
---

# Etsy OpenAPI v3 & AWS S3 Photo Integration

## Overview
Defined in [`src/tgnj_app/core/etsy_client.py`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/etsy_client.py). Manages bulk draft listing creation, shop section assignments, shipping profiles, custom property tags, order receipt sync, and AWS S3 photo attachments.

## Key Features & Invariants

### 1. OAuth 2.0 PKCE Authorization
* PKCE pair generated via [`EtsyClient.generate_pkce_pair()`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/core/etsy_client.py#L26-L34).
* Required scopes: `listings_r`, `listings_w`, `shops_r`, `shops_w`, `transactions_r`.
* Automatic token refresh mechanism using refresh tokens stored in `_etsy_config`.

### 2. AWS S3 Photo Fetching & Auto-Compression
* Fetch URL pattern: `https://tgnj-pictures.s3.us-east-1.amazonaws.com/{sku_group}/{SKU}A.jpg` and `B.jpg`.
* Concurrent image download during bulk listing.
* Compression rule: If downloaded photo exceeds **1MB**, automatically resizes to maximum 2000px dimension at 90% JPEG quality before sending multipart form-data to Etsy API.

### 3. Draft Deletion Guard Safety Rule
* Defined in [`sync_deleted_etsy_drafts`](file:///mnt/Driver_E/My%20Files/projects/tgnj-app/src/tgnj_app/gui/app.py#L716-L757).
* If Etsy API returns 0 live IDs or fails due to network/401/auth issues, local draft listed statuses are **NEVER reset**. Prevents accidental draft clearing on API connection drop.
