import json
import os, sys, io
from pathlib import Path
import urllib.request
from urllib.error import HTTPError
from flask import Flask, render_template, jsonify, request, send_file
from tgnj_app.core.database import database
from tgnj_app.core.labelmaker import create_pdf
from csv import writer
from tgnj_app.core.legacyUpload import ReadSpecificColumns
import threading
import time
from tgnj_app.core.turso_client import TursoClient
from tgnj_app.core import sync as sync_engine


def get_bundle_path(rel_path):
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / rel_path
    return Path(__file__).resolve().parent / rel_path

TEMPLATE_FOLDER = get_bundle_path("templates")
STATIC_FOLDER = get_bundle_path("static")
LOGO_PATH = STATIC_FOLDER / "labelLogo.png"

CONFIG_LOCATION = Path.home() / "Config.json"

app = Flask(
    __name__, 
    template_folder=str(TEMPLATE_FOLDER), 
    static_folder=str(STATIC_FOLDER)
)
#____________________________ utility functions______________________

def setConfig(db_path:Path):
    if os.path.exists:
        db_path_str = str(db_path)
        try:
            with open(CONFIG_LOCATION, "r") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            config = {}
        config["db_Path"] = db_path_str
        with open(CONFIG_LOCATION, "w") as f:
            json.dump(config,f)
        return db_path_str
    else:
        raise FileNotFoundError

def message(string:str)-> dict:
    return {"message":string}

def getConfig():
    with open(CONFIG_LOCATION,'r') as f:
        config = json.load(f)
        db_path = config.get('db_Path')
        if not db_path or not Path(db_path).exists():
            raise FileNotFoundError()
        else:
            return config

def load_turso_config() -> tuple[str | None, str | None, int]:
    """Read turso_url, turso_token, sync_interval_seconds from Config.json."""
    try:
        with open(CONFIG_LOCATION, 'r') as f:
            config = json.load(f)
        return (
            config.get('turso_url'),
            config.get('turso_token'),
            int(config.get('sync_interval_seconds', 30))
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return None, None, 30


#_________________________________ setup __________________________________

try:
    config = getConfig()
    db_path = Path(config.get('db_Path'))
    db_instance : database = database(db_path)
except FileNotFoundError as e:
    print(e)
    setConfig(Path(''))
    
turso_client: TursoClient | None = None
sync_thread_started: bool = False
sync_lock = threading.Lock()

def start_sync_loop(interval: int = 30):
    """Start the background sync daemon thread. Idempotent — safe to call multiple times."""
    global sync_thread_started
    if sync_thread_started:
        return
    sync_thread_started = True

    def _loop():
        while True:
            time.sleep(interval)
            if turso_client is not None:
                try:
                    with sync_lock:
                        result = sync_engine.sync(db_instance, turso_client)
                    print(f"[sync] Auto-sync: pushed={result.get('pushed', 0)} pulled={result.get('pulled', 0)}")
                except Exception as e:
                    print(f"[sync] Auto-sync error: {e}")

    thread = threading.Thread(target=_loop, daemon=True, name='turso-sync')
    thread.start()


# Load Turso config at startup if previously configured
_turso_url, _turso_token, _sync_interval = load_turso_config()
if _turso_url and _turso_token:
    turso_client = TursoClient(_turso_url, _turso_token)
    start_sync_loop(_sync_interval)
    print(f"[sync] Auto-sync enabled (interval={_sync_interval}s)")

# ________________________ ROUTES ______________________
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/getData/<sku_group>',methods=['GET'])
def getData(sku_group:str):
    data = db_instance.get_items_by_group(sku_group)
    cleanData = [dict(row) for row in data]
    return jsonify(cleanData),201

def trigger_async_sync():
    """Trigger a non-blocking background sync cycle when data is added/edited/deleted."""
    def _async():
        if turso_client is not None:
            try:
                with sync_lock:
                    result = sync_engine.sync(db_instance, turso_client)
                print(f"[sync] Action-sync: pushed={result.get('pushed', 0)} pulled={result.get('pulled', 0)}")
            except Exception as e:
                print(f"[sync] Action-sync error: {e}")
    threading.Thread(target=_async, daemon=True, name='action-sync').start()


@app.route('/api/addItem',methods=['POST'])
def addItem():
    data = request.json

    sku_group = data.get('sku_group')
    sku_id = data.get('sku_id')
    shape = data.get('shape')
    weight = data.get('weight')
    length = data.get('length')
    width = data.get('width')
    depth = data.get('depth')

    success = db_instance.add_item(sku_group=sku_group,sku_id=sku_id,shape=shape,weight=weight,length=length,width=width,depth=depth)

    if success:
        trigger_async_sync()
        return jsonify({'message':"stone added successfully"}),201
    else:
        return jsonify({"message":"error"}), 500

@app.route('/api/deleteItem/<sku_group>/<int:sku_id>',methods=["DELETE"])
def deleteItem(sku_group:str,sku_id:int):
    success = db_instance.delete_item(sku_group=sku_group,sku_id=sku_id)
    if success:
        trigger_async_sync()
        return jsonify(message("deleted item successfully")), 201
    else:
        return jsonify(message("Error deleting item")), 500

@app.route('/api/editItem/<group>/<int:id>',methods=["PATCH"])
def editItems(group,id):
    data = request.json
    success = db_instance.edit_item(sku_group=group,sku_id=id, **data)
    if success:
        trigger_async_sync()
        return jsonify(message("updated item successfully")), 201
    else:
        return jsonify(message("failute updating items")), 500


@app.route('/api/setDbPath',methods=["PATCH"])
def setDbPath():
    global db_instance
    data = request.json

    inputPath = data.get('db_Path')
    if not inputPath:
        return jsonify({"message": "Error: db_Path key missing in request"}), 400
    db_path = Path(inputPath)

    try:
        new_instance = database(db_path)
        db_instance = new_instance
        setConfig(db_path)
    except FileNotFoundError:
        return jsonify({"message":"file not found"}),404
    return jsonify({"message":f"db path set to {db_instance.path}"}),201

@app.route('/api/getDbPath', methods=["GET"])
def getDbPath():
    return jsonify({"db_Path":str(db_instance.path)}),200

@app.route('/api/getSkuGroups', methods=["GET"])
def getSkuGroups():
    groups = db_instance.get_all_sku_groups()
    return jsonify(groups), 200

@app.route('/api/printPdf/<sku_group>', methods=["GET"])
def printpdf(sku_group):
    data = db_instance.get_items_by_group(sku_group=sku_group)
    if not data:
        return jsonify(message("no data found")),404
    
    try:
        pdf_buffer = create_pdf(data=data,logo_path=LOGO_PATH)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f"Labels_{sku_group}.pdf"
        )
    except Exception as e:
        return jsonify(message(f"{e}")),500

@app.route('/api/getCsvData/<sku_group>',methods=["GET"])
def getCsvData(sku_group):

    data = db_instance.extract_data(sku_group=sku_group)
    if not data:
        return jsonify(message("no data found")),404
    output = io.StringIO()
    pen = writer(output,delimiter="\t")
    pen.writerows(data)
    return output.getvalue(),201

@app.route('/api/UploadLegacyCsv',methods=["POST"])
def addLegacyData():
    response = request.json
    csv_location = Path(response.get("location"))
    if csv_location.exists():
        dataframe = ReadSpecificColumns(csv_location)
    else:
        return jsonify(message("File not Found")),404
    
    for data in dataframe:
        sku_group = data.get('sku_group')
        sku_id = data.get('sku_id')
        shape = data.get('shape')
        weight = data.get('weight')
        length = data.get('length')
        width = data.get('width')
        depth = data.get('depth')
        print(sku_id)
        success = db_instance.add_item(sku_group=sku_group,sku_id=sku_id,shape=shape,weight=weight,length=length,width=width,depth=depth)

    if success:
        return jsonify({'message':"stone added successfully"}),201
    else:
        return jsonify({"message":"error"}), 500

@app.route('/api/getTursoConfig', methods=['GET'])
def getTursoConfig():
    turso_url, turso_token, _ = load_turso_config()
    return jsonify({
        'configured': bool(turso_url),
        'turso_url': turso_url or '',
        'turso_token': turso_token or ''
    }), 200

@app.route('/api/setTursoConfig', methods=['PATCH'])
def setTursoConfig():
    global turso_client, sync_thread_started
    data = request.json
    turso_url = data.get('turso_url', '').strip()
    turso_token = data.get('turso_token', '').strip()
    if not turso_url or not turso_token:
        return jsonify(message('turso_url and turso_token are required')), 400
    # Persist to Config.json (merge with existing config)
    try:
        with open(CONFIG_LOCATION, 'r') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}
    config['turso_url'] = turso_url
    config['turso_token'] = turso_token
    with open(CONFIG_LOCATION, 'w') as f:
        json.dump(config, f)
    # Create client and start sync thread if not already started
    turso_client = TursoClient(turso_url, turso_token)
    if not sync_thread_started:
        _, _, interval = load_turso_config()
        start_sync_loop(interval)
    return jsonify(message('Turso config saved and sync enabled')), 200

@app.route('/api/runSync', methods=['POST'])
def runSync():
    if turso_client is None:
        return jsonify(message('Turso not configured')), 400
    try:
        with sync_lock:
            result = sync_engine.sync(db_instance, turso_client)
        if result.get('error'):
            return jsonify(message(f"Sync error: {result['error']}")), 500
        return jsonify(result), 200
    except Exception as e:
        return jsonify(message(f'Sync error: {e}')), 500


@app.route('/api/getSyncStatus', methods=['GET'])
def getSyncStatus():
    last_push = db_instance.get_sync_meta('last_push_time')
    last_pull = db_instance.get_sync_meta('last_pull_time')
    return jsonify({
        'configured': turso_client is not None,
        'last_push': last_push,
        'last_pull': last_pull,
    }), 200

@app.route('/etsy')
def etsyManagerPage():
    return render_template('etsy_manager.html')

@app.route('/api/etsy/config', methods=['GET', 'POST'])
def etsyConfig():
    if request.method == 'GET':
        cfg = db_instance.get_all_etsy_config()
        return jsonify({
            'api_key': cfg.get('api_key', ''),
            'shared_secret': cfg.get('shared_secret', ''),
            'shop_id': cfg.get('shop_id', ''),
            'has_access_token': bool(cfg.get('access_token'))
        }), 200
    else:
        data = request.json or {}
        api_key = data.get('api_key', '').strip()
        shared_secret = data.get('shared_secret', '').strip()
        shop_id = data.get('shop_id', '').strip()
        if api_key:
            db_instance.set_etsy_config('api_key', api_key)
        if shared_secret:
            db_instance.set_etsy_config('shared_secret', shared_secret)
        if shop_id:
            db_instance.set_etsy_config('shop_id', shop_id)
        return jsonify(message('Etsy config saved')), 200

@app.route('/api/etsy/auth', methods=['POST'])
def etsyAuth():
    from tgnj_app.core.etsy_client import EtsyClient
    api_key = db_instance.get_etsy_config('api_key')
    shared_secret = db_instance.get_etsy_config('shared_secret')
    shop_id = db_instance.get_etsy_config('shop_id')
    if not api_key:
        return jsonify(message('Etsy API Key is required')), 400
        
    client = EtsyClient(api_key=api_key, shared_secret=shared_secret, shop_id=shop_id)
    verifier, challenge = client.generate_pkce_pair()
    
    db_instance.set_etsy_config('code_verifier', verifier)
    auth_url = client.get_authorization_url(challenge)
    return jsonify({'auth_url': auth_url}), 200

@app.route('/api/etsy/callback', methods=['GET'])
def etsyCallback():
    from tgnj_app.core.etsy_client import EtsyClient
    code = request.args.get('code')
    if not code:
        return "<h3>Etsy Auth Error: Missing authorization code</h3>", 400
        
    api_key = db_instance.get_etsy_config('api_key')
    shared_secret = db_instance.get_etsy_config('shared_secret')
    verifier = db_instance.get_etsy_config('code_verifier')
    
    if not api_key or not verifier:
        return "<h3>Etsy Auth Error: Missing API key or PKCE verifier</h3>", 400
        
    client = EtsyClient(api_key=api_key, shared_secret=shared_secret)
    try:
        token_data = client.exchange_code_for_token(code, verifier)
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        
        db_instance.set_etsy_config('access_token', access_token)
        if refresh_token:
            db_instance.set_etsy_config('refresh_token', refresh_token)
            
        return "<h3>TakshGems Etsy Authorization Successful! You can close this window.</h3>", 200
    except Exception as e:
        return f"<h3>Etsy Auth Exception: {e}</h3>", 500

@app.route('/api/getDataByStatus/<status>', methods=['GET'])
def getDataByStatus(status: str):
    # Fetch all items from inventory table
    with db_instance.conn as conn:
        curs = conn.cursor()
        if status.upper() == 'ALL':
            curs.execute("SELECT * FROM inventory WHERE is_deleted = 0 ORDER BY id DESC;")
        elif status.upper() == 'IN_STOCK':
            curs.execute("SELECT * FROM inventory WHERE is_deleted = 0 AND (status IS NULL OR status = 'IN_STOCK') ORDER BY id DESC;")
        else:
            curs.execute("SELECT * FROM inventory WHERE is_deleted = 0 AND status = ? ORDER BY id DESC;", (status.upper(),))
        rows = curs.fetchall()
        return jsonify([dict(r) for r in rows]), 200

@app.route('/api/etsy/syncOrders', methods=['POST'])
def etsySyncOrders():
    from tgnj_app.core.etsy_client import EtsyClient
    api_key = db_instance.get_etsy_config('api_key')
    shared_secret = db_instance.get_etsy_config('shared_secret')
    shop_id = db_instance.get_etsy_config('shop_id')
    access_token = db_instance.get_etsy_config('access_token')

    if not api_key or not access_token or not shop_id:
        return jsonify(message('Etsy authorization required')), 400

    client = EtsyClient(api_key=api_key, shared_secret=shared_secret, shop_id=shop_id)
    try:
        receipts = client.get_shop_receipts(access_token)
        # Parse receipts and update sold items
        synced_count = 0
        return jsonify({'message': f'Synced Etsy sales receipts! Updated {synced_count} orders.'}), 200
    except Exception as e:
        return jsonify(message(f'Etsy Sync Orders Exception: {e}')), 500

@app.route('/api/etsy/pushListing/<sku_group>/<int:sku_id>', methods=['POST'])
def pushListing(sku_group: str, sku_id: int):
    from tgnj_app.core.etsy_client import EtsyClient
    api_key = db_instance.get_etsy_config('api_key')
    shared_secret = db_instance.get_etsy_config('shared_secret')
    shop_id = db_instance.get_etsy_config('shop_id')
    access_token = db_instance.get_etsy_config('access_token')

    if not api_key or not access_token or not shop_id:
        return jsonify(message('Etsy authorization required')), 400

    # Fetch item from database
    item = None
    with db_instance.conn as conn:
        curs = conn.cursor()
        curs.execute("SELECT * FROM inventory WHERE sku_group = ? AND sku_id = ? AND is_deleted = 0;", (sku_group, sku_id))
        row = curs.fetchone()
        if row:
            item = dict(row)

    if not item:
        return jsonify(message('Item not found')), 404

    data = request.json or {}
    if data.get('price'):
        item['etsy_price'] = data.get('price')

    client = EtsyClient(api_key=api_key, shared_secret=shared_secret, shop_id=shop_id)
    try:
        listing = client.create_draft_listing(access_token, item)
        listing_id = listing.get('listing_id')

        if listing_id:
            client.upload_s3_photos_for_listing(access_token, str(listing_id), sku_group, sku_id)
            # Update database status
            with db_instance.conn as conn:
                curs = conn.cursor()
                curs.execute("UPDATE inventory SET status = 'LISTED_ETSY', etsy_listing_id = ? WHERE sku_group = ? AND sku_id = ?;", (str(listing_id), sku_group, sku_id))
                conn.commit()

        return jsonify({'message': f'Published draft listing #{listing_id} to Etsy!', 'listing': listing}), 200
    except Exception as e:
        return jsonify(message(f'Etsy Push Exception: {e}')), 500

@app.route('/api/etsy/liveStats', methods=['GET'])
def etsyLiveStats():
    try:
        from tgnj_app.core.etsy_client import EtsyClient
        api_key = db_instance.get_etsy_config('api_key')
        shared_secret = db_instance.get_etsy_config('shared_secret')
        shop_id = db_instance.get_etsy_config('shop_id')
        access_token = db_instance.get_etsy_config('access_token')

        if not api_key or not access_token or not shop_id:
            return jsonify({
                'connected': False,
                'active': 0,
                'draft': 0
            }), 200

        client = EtsyClient(api_key=api_key, shared_secret=shared_secret, shop_id=shop_id)
        active_resp = client.get_shop_listings_by_state(access_token, state='active')
        draft_resp = client.get_shop_listings_by_state(access_token, state='draft')
        
        return jsonify({
            'connected': True,
            'active': active_resp.get('count', len(active_resp.get('results', []))),
            'draft': draft_resp.get('count', len(draft_resp.get('results', [])))
        }), 200
    except Exception as e:
        print(f"[app] etsyLiveStats exception: {e}")
        return jsonify({
            'connected': False,
            'active': 0,
            'draft': 0
        }), 200

@app.route('/api/etsy/checkPhotos', methods=['POST'])
def checkPhotos():
    data = request.json
    items = data.get('items', [])
    results = {}
    for item in items:
        group = item.get('sku_group')
        sku_id = item.get('sku_id')
        if group is None or sku_id is None:
            continue
        padded_sku = str(sku_id).zfill(3)
        sku_key = f"{group}-{padded_sku}"
        
        url_a = f"https://tgnj-pictures.s3.us-east-1.amazonaws.com/{group}/{sku_key}A.jpg"
        url_b = f"https://tgnj-pictures.s3.us-east-1.amazonaws.com/{group}/{sku_key}B.jpg"
        
        has_a = False
        has_b = False
        
        try:
            req_a = urllib.request.Request(url_a, method='HEAD')
            urllib.request.urlopen(req_a)
            has_a = True
        except Exception:
            pass
            
        try:
            req_b = urllib.request.Request(url_b, method='HEAD')
            urllib.request.urlopen(req_b)
            has_b = True
        except Exception:
            pass
            
        results[sku_key] = {"a": has_a, "b": has_b}
        
    return jsonify({"results": results}), 200

def get_fresh_etsy_tokens():
    """Retrieve current Etsy API credentials and tokens from database."""
    api_key = db_instance.get_etsy_config('api_key')
    shared_secret = db_instance.get_etsy_config('shared_secret')
    shop_id = db_instance.get_etsy_config('shop_id')
    access_token = db_instance.get_etsy_config('access_token')
    refresh_token = db_instance.get_etsy_config('refresh_token')
    return api_key, shared_secret, shop_id, access_token, refresh_token

def refresh_etsy_token_if_needed(client, refresh_token):
    """Attempts to refresh the OAuth access token and save new tokens to DB."""
    if not refresh_token:
        return None
    try:
        print("[etsy_client] Refreshing expired access token using refresh_token...")
        token_data = client.refresh_access_token(refresh_token)
        new_access = token_data.get('access_token')
        new_refresh = token_data.get('refresh_token')
        if new_access:
            db_instance.set_etsy_config('access_token', new_access)
            if new_refresh:
                db_instance.set_etsy_config('refresh_token', new_refresh)
            print("[etsy_client] Access token successfully refreshed!")
            return new_access
    except Exception as e:
        print(f"[etsy_client] Automatic token refresh failed: {e}")
    return None

@app.route('/api/etsy/bulkPush', methods=['POST'])
def bulkPush():
    from tgnj_app.core.etsy_client import EtsyClient
    api_key, shared_secret, shop_id, access_token, refresh_token = get_fresh_etsy_tokens()

    if not api_key or not access_token or not shop_id:
        return jsonify(message('Etsy authorization required')), 400
        
    client = EtsyClient(api_key=api_key, shared_secret=shared_secret, shop_id=shop_id)

    data = request.json or {}
    items = data.get('items', [])
    gemstone_name = data.get('gemstone_name')
    price = data.get('price')
    
    total = len(items)
    success = 0
    failed = 0
    results = []
    
    for req_item in items:
        sku_group = req_item.get('sku_group')
        sku_id = req_item.get('sku_id')
        
        if sku_group is None or sku_id is None:
            continue
            
        padded_sku = str(sku_id).zfill(3)
        sku_key = f"{sku_group}-{padded_sku}"
            
        # Fetch item from database
        item = None
        with db_instance.conn as conn:
            curs = conn.cursor()
            curs.execute("SELECT * FROM inventory WHERE sku_group = ? AND sku_id = ? AND is_deleted = 0;", (sku_group, sku_id))
            row = curs.fetchone()
            if row:
                item = dict(row)

        if not item:
            failed += 1
            results.append({"sku": sku_key, "error": "Item not found in database", "status": "failed"})
            continue

        # Prevent duplicate listing creation if already listed on Etsy
        if item.get('etsy_listing_id') or item.get('status') == 'LISTED_ETSY':
            results.append({"sku": sku_key, "listing_id": item.get('etsy_listing_id'), "error": "Already listed on Etsy", "status": "skipped"})
            continue
            
        if gemstone_name:
            item['gemstone_name'] = gemstone_name
        if price:
            item['etsy_price'] = price
            
        # Attempt listing creation with automatic token refresh and rate limit retries
        max_retries = 3
        attempt = 0
        pushed_ok = False

        while attempt < max_retries and not pushed_ok:
            attempt += 1
            try:
                # Re-fetch current access_token from DB in case it was refreshed in a previous iteration
                current_access = db_instance.get_etsy_config('access_token')
                current_refresh = db_instance.get_etsy_config('refresh_token')

                listing = client.create_draft_listing(current_access, item)
                listing_id = listing.get('listing_id')

                if listing_id:
                    # Upload photos
                    client.upload_s3_photos_for_listing(current_access, str(listing_id), sku_group, sku_id)
                    # Update database status
                    with db_instance.conn as conn:
                        curs = conn.cursor()
                        curs.execute("UPDATE inventory SET status = 'LISTED_ETSY', etsy_listing_id = ? WHERE sku_group = ? AND sku_id = ?;", (str(listing_id), sku_group, sku_id))
                        conn.commit()
                    
                    success += 1
                    results.append({"sku": sku_key, "listing_id": listing_id, "status": "success"})
                    pushed_ok = True
                else:
                    failed += 1
                    results.append({"sku": sku_key, "error": "Listing ID not returned", "status": "failed"})
                    pushed_ok = True # Exit retry loop if unexpected response format
                    
            except Exception as e:
                err_msg = str(e).lower()
                is_auth_error = ("401" in err_msg or "expired" in err_msg or "unauthorized" in err_msg or "invalid_token" in err_msg)
                is_rate_limit = ("429" in err_msg or "too many requests" in err_msg)

                if is_auth_error and attempt < max_retries:
                    print(f"[bulkPush] Token expired on item {sku_key} (attempt {attempt}). Refreshing token and retrying...")
                    new_token = refresh_etsy_token_if_needed(client, current_refresh)
                    if new_token:
                        time.sleep(1.0)
                        continue # Retry immediately with new token
                elif is_rate_limit and attempt < max_retries:
                    print(f"[bulkPush] Rate limit hit (429) on item {sku_key}. Sleeping 5 seconds before retry...")
                    time.sleep(5.0)
                    continue # Retry after backoff
                
                # If retries exhausted or unhandled error
                if attempt >= max_retries or (not is_auth_error and not is_rate_limit):
                    failed += 1
                    results.append({"sku": sku_key, "error": str(e), "status": "failed"})
                    pushed_ok = True
            
        time.sleep(0.5)

    return jsonify({
        "total": total,
        "success": success,
        "failed": failed,
        "results": results
    }), 200