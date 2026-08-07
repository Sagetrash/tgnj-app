import json
import base64
import hashlib
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ETSY_API_BASE = "https://openapi.etsy.com/v3/application"
ETSY_AUTH_URL = "https://www.etsy.com/oauth/connect"

class EtsyClient:
    def __init__(self, api_key: str = "", shared_secret: str = "", shop_id: str = "", redirect_uri: str = "http://localhost:5000/api/etsy/callback"):
        self.api_key = api_key.strip()
        self.shared_secret = shared_secret.strip()
        self.shop_id = shop_id.strip()
        self.redirect_uri = redirect_uri.strip()
        
    @property
    def api_key_header(self) -> str:
        if self.shared_secret:
            return f"{self.api_key}:{self.shared_secret}"
        return self.api_key
        
    @staticmethod
    def generate_pkce_pair():
        """Generate PKCE code_verifier and S256 code_challenge."""
        token = secrets.token_bytes(32)
        code_verifier = base64.urlsafe_b64encode(token).decode("utf-8").rstrip("=")
        
        hashed = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(hashed).decode("utf-8").rstrip("=")
        return code_verifier, code_challenge

    def get_authorization_url(self, code_challenge: str, state: str = "superstate") -> str:
        """Construct the OAuth 2.0 PKCE consent URL for Etsy."""
        scopes = [
            "listings_r",
            "listings_w",
            "shops_r",
            "shops_w",
            "transactions_r"
        ]
        params = {
            "response_type": "code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        return f"{ETSY_AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_token(self, code: str, code_verifier: str) -> dict:
        """Exchange OAuth authorization code for access token & refresh token."""
        url = "https://api.etsy.com/v3/public/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "code": code,
            "code_verifier": code_verifier
        }
        data = urlencode(payload).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        req = Request(url, data=data, headers=headers, method="POST")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[etsy_client] Token exchange error: {e.code} - {err_body}")
            raise Exception(f"Etsy Token exchange failed: {err_body}")
        except Exception as e:
            print(f"[etsy_client] Token exchange exception: {e}")
            raise e

    def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an expired OAuth access token using refresh_token."""
        url = "https://api.etsy.com/v3/public/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.api_key,
            "refresh_token": refresh_token
        }
        data = urlencode(payload).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        req = Request(url, data=data, headers=headers, method="POST")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[etsy_client] Token refresh error: {e.code} - {err_body}")
            raise Exception(f"Etsy Token refresh failed: {err_body}")
        except Exception as e:
            print(f"[etsy_client] Token refresh exception: {e}")
            raise e

    def get_shipping_profiles(self, access_token: str) -> list[dict]:
        """Fetch all shipping profiles for the shop."""
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/shipping-profiles"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}"
        }
        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("results", [])
        except Exception as e:
            print(f"[etsy_client] get_shipping_profiles error: {e}")
            return []

    def get_readiness_states(self, access_token: str) -> list[dict]:
        """Fetch readiness state definitions for the shop."""
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/readiness-state-definitions"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}"
        }
        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("results", [])
        except Exception as e:
            print(f"[etsy_client] get_readiness_states error: {e}")
            return []

    def get_shop_sections(self, access_token: str) -> list[dict]:
        """Fetch shop sections for the Etsy shop."""
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/sections"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}"
        }
        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("results", [])
        except Exception as e:
            print(f"[etsy_client] get_shop_sections error: {e}")
            return []

    def create_draft_listing(self, access_token: str, item: dict, taxonomy_id: int = 6648, shipping_profile_id: int = None, readiness_state_id: int = None, shop_section_id: int = None) -> dict:
        """
        Creates a draft listing on Etsy for TakshGems under Cabochons category (taxonomy_id=6648).
        """
        if not shipping_profile_id:
            profiles = self.get_shipping_profiles(access_token)
            if profiles:
                shipping_profile_id = profiles[0].get("shipping_profile_id")

        if not readiness_state_id:
            states = self.get_readiness_states(access_token)
            if states:
                readiness_state_id = states[0].get("readiness_state_id")

        group = item.get("sku_group", "").upper()
        sku_id = item.get("sku_id", 0)
        sku_str = f"{group}-{int(sku_id):03d}"
        
        shape = (item.get("shape") or "").strip().title()
        weight = float(item.get("weight") or 0.0)
        length = int(item.get("length") or 0)
        width = int(item.get("width") or 0)
        depth = int(item.get("depth") or 0)
        price = float(item.get("etsy_price") or 0.0)
        if price <= 0:
            price = 12.99
            
        gemstone_name = item.get("gemstone_name") or "Gemstone"
        title = item.get("custom_title") or f"{weight:.2f} Ct. Natural High Quality {gemstone_name} Loose Gemstone {shape} Cabochon For Jewelry Making"
        
        # Build Specifications Section (First)
        dims_str = f"{length} x {width} x {depth} mm" if (length or width or depth) else "N/A"
        specs_section = (
            f"SPECIFICATIONS\n"
            f"SKU: {sku_str}\n"
            f"Gemstone: Natural {gemstone_name}\n"
            f"Shape: {shape}\n"
            f"Carat Weight: {weight:.2f} Cts\n"
            f"Dimensions: {dims_str}\n"
            f"Treatment: 100% Natural and Untreated"
        )
        
        custom_notes = (item.get("custom_description") or "").strip()
        if custom_notes:
            description = f"{specs_section}\n\nDESCRIPTION\n{custom_notes}"
        else:
            description = specs_section
        
        # User requested tags left blank for post editing, and materials set to Natural Gemstone & Untreated Gemstone
        tags = item.get("custom_tags") if item.get("custom_tags") is not None else []
        materials = [f"Natural {gemstone_name}", "Untreated Gemstone"]
        
        payload = {
            "quantity": 1,
            "title": title[:140],
            "description": description,
            "price": price,
            "who_made": "collective",  # "A member of my shop"
            "when_made": "2020_2026",
            "taxonomy_id": taxonomy_id,
            "shipping_profile_id": shipping_profile_id,
            "readiness_state_id": readiness_state_id,
            "shop_section_id": shop_section_id,
            "sku": sku_str,
            "tags": tags[:13],
            "materials": materials[:5],
            "state": "draft",
            "type": "physical",
            "is_supply": True,  # "A supply or tool to make things"
            "item_length": float(length) if length > 0 else None,
            "item_width": float(width) if width > 0 else None,
            "item_height": float(depth) if depth > 0 else None,
            "item_dimensions_unit": "mm"
        }
        # Filter out None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/listings"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        req = Request(url, data=urlencode(payload, doseq=True).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[etsy_client] create_draft_listing error: {e.code} - {err_body}")
            raise Exception(f"Etsy API Create Listing failed: {err_body}")
        except Exception as e:
            print(f"[etsy_client] create_draft_listing exception: {e}")
            raise e

    def update_listing_property(self, access_token: str, listing_id: str, property_id: int, values: list, value_ids: list = None) -> dict:
        """
        Updates a specific property on an Etsy listing using PUT /v3/application/shops/{shop_id}/listings/{listing_id}/properties/{property_id}.
        """
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/listings/{listing_id}/properties/{property_id}"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "values": values
        }
        if value_ids:
            payload["value_ids"] = value_ids

        req = Request(url, data=urlencode(payload, doseq=True).encode("utf-8"), headers=headers, method="PUT")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[etsy_client] update_listing_property notice for prop #{property_id}: {e}")
            return {}

    def deactivate_listing(self, access_token: str, listing_id: str) -> dict:
        """
        Deactivates an active or draft Etsy listing by setting state='inactive'.
        Sends PATCH /v3/application/shops/{shop_id}/listings/{listing_id}.
        """
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/listings/{listing_id}"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "state": "inactive"
        }
        req = Request(url, data=urlencode(payload).encode("utf-8"), headers=headers, method="PATCH")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else str(e)
            print(f"[etsy_client] deactivate_listing HTTPError {e.code}: {err_body}")
            return {"error": err_body, "code": e.code}
        except Exception as e:
            print(f"[etsy_client] deactivate_listing exception: {e}")
            return {"error": str(e)}

    def reactivate_listing(self, access_token: str, listing_id: str) -> dict:
        """
        Reactivates an inactive Etsy listing by setting state='active'.
        Sends PATCH /v3/application/shops/{shop_id}/listings/{listing_id}.
        """
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/listings/{listing_id}"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "state": "active"
        }
        req = Request(url, data=urlencode(payload).encode("utf-8"), headers=headers, method="PATCH")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else str(e)
            print(f"[etsy_client] reactivate_listing HTTPError {e.code}: {err_body}")
            return {"error": err_body, "code": e.code}
        except Exception as e:
            print(f"[etsy_client] reactivate_listing exception: {e}")
            return {"error": str(e)}

    def update_listing_title(self, access_token: str, listing_id: str, new_title: str) -> dict:
        """
        Updates the title of an Etsy listing (e.g. renames draft to 'delete').
        Sends PATCH /v3/application/shops/{shop_id}/listings/{listing_id}.
        """
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/listings/{listing_id}"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "title": new_title
        }
        req = Request(url, data=urlencode(payload).encode("utf-8"), headers=headers, method="PATCH")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else str(e)
            print(f"[etsy_client] update_listing_title HTTPError {e.code}: {err_body}")
            return {"error": err_body, "code": e.code}
        except Exception as e:
            print(f"[etsy_client] update_listing_title exception: {e}")
            return {"error": str(e)}


    def delete_listing(self, access_token: str, listing_id: str) -> dict:
        """
        Deletes a draft, inactive, or sold-out Etsy listing.
        Sends DELETE /v3/application/listings/{listing_id}.
        """
        url = f"{ETSY_API_BASE}/listings/{listing_id}"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}"
        }
        req = Request(url, headers=headers, method="DELETE")
        try:
            with urlopen(req) as resp:
                if resp.status in (200, 204):
                    return {"success": True, "listing_id": listing_id}
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {"success": True}
        except HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else str(e)
            print(f"[etsy_client] delete_listing HTTPError {e.code}: {err_body}")
            return {"error": err_body, "code": e.code}
        except Exception as e:
            print(f"[etsy_client] delete_listing exception: {e}")
            return {"error": str(e)}




    def update_listing_inventory(self, access_token: str, listing_id: str, sku: str, price: float, quantity: int = 1, readiness_state_id: int = None) -> dict:
        """
        Updates the product inventory for an Etsy listing to assign its SKU and price.
        Sends PUT /v3/application/listings/{listing_id}/inventory.
        """
        if not readiness_state_id:
            states = self.get_readiness_states(access_token)
            if states:
                readiness_state_id = states[0].get("readiness_state_id")

        offering = {
            "price": float(price),
            "quantity": int(quantity),
            "is_enabled": True
        }
        if readiness_state_id:
            offering["readiness_state_id"] = readiness_state_id

        url = f"{ETSY_API_BASE}/listings/{listing_id}/inventory"
        payload = {
            "products": [
                {
                    "sku": sku,
                    "offerings": [offering]
                }
            ]
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        req = Request(url, data=data, headers=headers, method="PUT")
        try:
            with urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                print(f"[etsy_client] Successfully assigned SKU '{sku}' to Etsy listing #{listing_id}!")
                return result
        except HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[etsy_client] update_listing_inventory error: {e.code} - {err_body}")
            return {}
        except Exception as e:
            print(f"[etsy_client] update_listing_inventory exception: {e}")
            return {}

    def upload_listing_image(self, access_token: str, listing_id: str, image_bytes: bytes, filename: str = "image.jpg", rank: int = 1) -> dict:
        """Upload a binary image to an Etsy listing via multipart/form-data."""
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/listings/{listing_id}/images"
        
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = bytearray()
        
        # Add rank field
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="rank"\r\n\r\n{rank}\r\n'.encode("utf-8"))
        
        # Add image field
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(f'Content-Type: image/jpeg\r\n\r\n'.encode("utf-8"))
        body.extend(image_bytes)
        body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        }
        
        req = Request(url, data=bytes(body), headers=headers, method="POST")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[etsy_client] upload_listing_image error: {e.code} - {err_body}")
            return {}
        except Exception as e:
            print(f"[etsy_client] upload_listing_image exception: {e}")
            return {}

    def upload_s3_photos_for_listing(self, access_token: str, listing_id: str, sku_group: str, sku_id: int):
        """Attempts to fetch Photo A and Photo B from S3 concurrently and upload to Etsy listing."""
        group = sku_group.upper()
        sku_str = f"{group}-{int(sku_id):03d}"
        
        photo_urls = [
            (f"https://tgnj-pictures.s3.us-east-1.amazonaws.com/{group}/{sku_str}A.jpg", 1),
            (f"https://tgnj-pictures.s3.us-east-1.amazonaws.com/{group}/{sku_str}B.jpg", 2)
        ]
        
        def optimize_image_bytes(image_bytes: bytes) -> bytes:
            """Optimizes image to max 2000px at 90% quality if larger than 1MB."""
            if not image_bytes or len(image_bytes) < 1000000:
                return image_bytes
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(image_bytes))
                w, h = img.size
                if max(w, h) > 2000:
                    img.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
                out = io.BytesIO()
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(out, format="JPEG", quality=90, optimize=True)
                opt_bytes = out.getvalue()
                if len(opt_bytes) < len(image_bytes):
                    return opt_bytes
            except Exception as e:
                print(f"[etsy_client] Image optimization notice: {e}")
            return image_bytes

        def fetch_image(item):
            url, rank = item
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(req) as resp:
                    if resp.status == 200:
                        raw = resp.read()
                        return rank, optimize_image_bytes(raw)
            except Exception as e:
                print(f"[etsy_client] Image fetch skipped for {url}: {e}")
            return rank, None

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as executor:
            downloaded = list(executor.map(fetch_image, photo_urls))

        # Upload images sequentially to maintain rank order on Etsy
        for rank, img_bytes in sorted(downloaded, key=lambda x: x[0]):
            if img_bytes:
                res = self.upload_listing_image(access_token, listing_id, img_bytes, filename=f"{sku_str}_{rank}.jpg", rank=rank)
                if res.get("listing_image_id"):
                    print(f"[etsy_client] Successfully uploaded image rank {rank} for listing {listing_id}!")

    def get_shop_receipts(self, access_token: str, limit: int = 25) -> dict:
        """Fetch recent sales receipts / orders for the shop."""
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/receipts?limit={limit}"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}"
        }
        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[etsy_client] get_shop_receipts error: {e.code} - {err_body}")
            return {"count": 0, "results": []}
        except Exception as e:
            print(f"[etsy_client] get_shop_receipts exception: {e}")
            return {"count": 0, "results": []}

    def get_shop_receipt_transactions(self, access_token: str, limit: int = 50) -> dict:
        """Fetch transactions associated with shop receipts (includes SKU, price, listing_id)."""
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/transactions?limit={limit}"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}"
        }
        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[etsy_client] get_shop_receipt_transactions error: {e.code} - {err_body}")
            return {"count": 0, "results": []}
        except Exception as e:
            print(f"[etsy_client] get_shop_receipt_transactions exception: {e}")
            return {"count": 0, "results": []}

    def get_shop_listings_by_state(self, access_token: str, state: str = "active", limit: int = 100, offset: int = 0) -> dict:
        """Fetch live shop listings directly from Etsy by state ('active', 'draft', 'inactive', 'sold_out')."""
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/listings?state={state}&limit={limit}&offset={offset}"
        headers = {
            "x-api-key": self.api_key_header,
            "Authorization": f"Bearer {access_token}"
        }
        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[etsy_client] get_shop_listings_by_state error: {e.code} - {err_body}")
            return {"count": 0, "results": []}
        except Exception as e:
            print(f"[etsy_client] get_shop_listings_by_state exception: {e}")
            return {"count": 0, "results": []}

    def get_all_shop_listings_by_state(self, access_token: str, state: str = "active") -> list[dict]:
        """Fetch ALL shop listings for a given state across all pages via offset pagination."""
        all_results = []
        offset = 0
        limit = 100
        page_count = 0
        while True:
            page_count += 1
            res = self.get_shop_listings_by_state(access_token, state=state, limit=limit, offset=offset)
            results = res.get("results", [])
            all_results.extend(results)
            if len(results) < limit:
                break
            offset += limit
        print(f"[etsy_client] Fetched total {len(all_results)} '{state}' listing(s) across {page_count} page(s).")
        return all_results

