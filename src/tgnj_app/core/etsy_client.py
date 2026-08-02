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

    def create_draft_listing(self, access_token: str, item: dict, taxonomy_id: int = 1, shipping_profile_id: int = None, readiness_state_id: int = None) -> dict:
        """
        Creates a draft listing on Etsy for TakshGems.
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
            
        gemstone_name = item.get("gemstone_name") or "Black Tourmaline Rutile Quartz"
        title = item.get("custom_title") or f"{weight:.2f} Ct.Natural High Quality {gemstone_name} Loose Gemstone {shape} Cabochon For Jewelry Making"
        
        description = item.get("custom_description") or (
            f"Natural {gemstone_name} Cabochon - High Quality Loose Gemstone\n\n"
            f"PRODUCT OVERVIEW\n"
            f"This listing is for a premium, hand-polished {gemstone_name} cabochon. Known for its striking contrast, "
            f"this natural clear quartz is filled with needle-like inclusions of Black Tourmaline (Rutile), creating a unique \"matrix\" or \"spider-web\" effect. "
            f"No two stones are ever exactly alike, making this a truly one-of-a-kind piece for your next jewelry project.\n\n"
            f"SPECIFICATIONS\n"
            f"SKU: {sku_str}\n"
            f"Gemstone: Natural {gemstone_name}\n"
            f"Shape: {shape}\n"
            f"Carat Weight: {weight:.2f} Cts\n"
            f"Dimensions: {length} x {width} x {depth} mm\n"
            f"Treatment: 100% Natural and Untreated\n\n"
            f"METAPHYSICAL PROPERTIES\n"
            f"{gemstone_name} is often called the \"stone of power.\" It is believed to be a strong grounding stone that clears energy blockages and protects the wearer from negativity. "
            f"Its unique balance of clear quartz and dark inclusions makes it a symbol of the union between light and shadow.\n\n"
            f"IDEAL USES\n"
            f"This stone is perfectly suited for custom rings, statement pendants, or boho-style earrings. "
            f"It is also a popular choice for crystal healing collections, meditation altars, or as a unique gift for gemstone collectors."
        )
        
        tags = item.get("custom_tags") or [gemstone_name, "Loose Gemstone", "Cabochon for Ring", "Jewelry Making", "Natural Stone", "Healing Crystal", "DIY Jewelry", f"{shape} Cabochon", "Unique Gemstone"]
        materials = [f"Natural {gemstone_name}", "Hand Polished Cabochon", "Untreated Gemstone"]
        
        payload = {
            "quantity": 1,
            "title": title[:140],
            "description": description,
            "price": price,
            "who_made": "i_did",
            "when_made": "2020_2026",
            "taxonomy_id": taxonomy_id,
            "shipping_profile_id": shipping_profile_id,
            "readiness_state_id": readiness_state_id,
            "sku": sku_str,
            "tags": tags[:13],
            "materials": materials[:5],
            "state": "draft",
            "type": "physical",
            "is_supply": True,
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
        """Attempts to fetch Photo A and Photo B from S3 and upload to Etsy listing."""
        group = sku_group.upper()
        sku_str = f"{group}-{int(sku_id):03d}"
        
        photo_urls = [
            (f"https://tgnj-pictures.s3.us-east-1.amazonaws.com/{group}/{sku_str}A.jpg", 1),
            (f"https://tgnj-pictures.s3.us-east-1.amazonaws.com/{group}/{sku_str}B.jpg", 2)
        ]
        
        for url, rank in photo_urls:
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(req) as resp:
                    if resp.status == 200:
                        img_bytes = resp.read()
                        res = self.upload_listing_image(access_token, listing_id, img_bytes, filename=f"{sku_str}_{rank}.jpg", rank=rank)
                        if res.get("listing_image_id"):
                            print(f"[etsy_client] Successfully uploaded image rank {rank} for listing {listing_id}!")
            except Exception as e:
                print(f"[etsy_client] Image fetch/upload skipped for {url}: {e}")

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

    def get_shop_listings_by_state(self, access_token: str, state: str = "active", limit: int = 100) -> dict:
        """Fetch live shop listings directly from Etsy by state ('active', 'draft', 'inactive', 'sold_out')."""
        url = f"{ETSY_API_BASE}/shops/{self.shop_id}/listings?state={state}&limit={limit}"
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
