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

db_instance: database | None = None

try:
    config = getConfig()
    if config.get('db_Path'):
        db_path = Path(config.get('db_Path'))
        db_instance = database(db_path)
except Exception as e:
    print(f"[app] Database startup notice: {e}")
    
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
            if turso_client is not None and db_instance is not None:
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
        if turso_client is not None and db_instance is not None:
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


@app.route('/api/setDbPath', methods=["PATCH", "POST"])
def setDbPath():
    global db_instance
    data = request.json or {}

    inputPath = data.get('db_Path') or data.get('db_path')
    create_new = data.get('create_new', False)
    
    if not inputPath:
        return jsonify({"message": "Error: db_Path key missing in request"}), 400
    db_path = Path(inputPath)

    try:
        if create_new:
            new_instance = database.create_new_database(db_path)
        else:
            new_instance = database(db_path)
            
        db_instance = new_instance
        setConfig(db_path)
        return jsonify({"message": f"db path set to {db_instance.path}"}), 201
    except FileNotFoundError:
        return jsonify({"message": "file not found", "suggest_create": True}), 404
    return jsonify({"message":f"db path set to {db_instance.path}"}),201

@app.route('/api/getDbPath', methods=["GET"])
def getDbPath():
    if db_instance:
        return jsonify({"db_Path": str(db_instance.path)}), 200
    return jsonify({"db_Path": ""}), 200

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
    if not db_instance:
        return jsonify({'api_key': '', 'shared_secret': '', 'shop_id': '', 'has_access_token': False}), 200
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
    api_key, shared_secret, shop_id, access_token, refresh_token = get_fresh_etsy_tokens()

    if not api_key or not access_token or not shop_id:
        return jsonify(message('Etsy authorization required')), 400

    client = EtsyClient(api_key=api_key, shared_secret=shared_secret, shop_id=shop_id)
    synced_count = 0
    
    try:
        # Engine 1: Fetch transactions associated with shop receipts
        tx_data = client.get_shop_receipt_transactions(access_token, limit=50)
        transactions = tx_data.get('results', [])
        
        with db_instance.conn as conn:
            curs = conn.cursor()
            for tx in transactions:
                listing_id = str(tx.get('listing_id', ''))
                sku = tx.get('sku', '').strip().upper()
                price_amount = tx.get('price', {}).get('amount', 0) / tx.get('price', {}).get('divisor', 100) if isinstance(tx.get('price'), dict) else float(tx.get('price') or 0.0)

                # Match by SKU (e.g. LP-014) or etsy_listing_id
                if sku and '-' in sku:
                    parts = sku.split('-')
                    if len(parts) >= 2 and parts[1].isdigit():
                        grp = parts[0]
                        s_id = int(parts[1])
                        curs.execute("""
                            UPDATE inventory 
                            SET status = 'SOLD', 
                                sold_price = ?, 
                                sold_channel = 'Etsy', 
                                etsy_listing_id = ?, 
                                sold_at = COALESCE(NULLIF(sold_at, ''), datetime('now')), 
                                updated_at = datetime('now') 
                            WHERE sku_group = ? AND sku_id = ? AND (status IS NULL OR status != 'SOLD');
                        """, (price_amount, listing_id, grp, s_id))
                        if curs.rowcount > 0:
                            synced_count += curs.rowcount
                elif listing_id:
                    curs.execute("""
                        UPDATE inventory 
                        SET status = 'SOLD', 
                            sold_price = ?, 
                            sold_channel = 'Etsy', 
                            sold_at = COALESCE(NULLIF(sold_at, ''), datetime('now')), 
                            updated_at = datetime('now') 
                        WHERE etsy_listing_id = ? AND (status IS NULL OR status != 'SOLD');
                    """, (price_amount, listing_id))
                    if curs.rowcount > 0:
                        synced_count += curs.rowcount

        # Engine 2: Safety net - Fetch listings with state 'sold_out'
        sold_out_data = client.get_shop_listings_by_state(access_token, state='sold_out', limit=100)
        sold_out_listings = sold_out_data.get('results', [])
        
        with db_instance.conn as conn:
            curs = conn.cursor()
            for listing in sold_out_listings:
                listing_id = str(listing.get('listing_id', ''))
                sku = listing.get('sku', '').strip().upper()
                price_amount = float(listing.get('price', {}).get('amount', 0) / listing.get('price', {}).get('divisor', 100)) if isinstance(listing.get('price'), dict) else float(listing.get('price') or 0.0)

                if sku and '-' in sku:
                    parts = sku.split('-')
                    if len(parts) >= 2 and parts[1].isdigit():
                        grp = parts[0]
                        s_id = int(parts[1])
                        curs.execute("""
                            UPDATE inventory 
                            SET status = 'SOLD', 
                                sold_price = ?, 
                                sold_channel = 'Etsy', 
                                etsy_listing_id = ?, 
                                sold_at = COALESCE(NULLIF(sold_at, ''), datetime('now')), 
                                updated_at = datetime('now') 
                            WHERE sku_group = ? AND sku_id = ? AND (status IS NULL OR status != 'SOLD');
                        """, (price_amount, listing_id, grp, s_id))
                        if curs.rowcount > 0:
                            synced_count += curs.rowcount

        if synced_count > 0:
            trigger_async_sync()

        # Engine 3: Clean up local items whose drafts/listings were deleted on Etsy.com
        deleted_reset_count = sync_deleted_etsy_drafts(client, access_token)

        msg = f'Synced Etsy sales! Updated {synced_count} sold items.'
        if deleted_reset_count > 0:
            msg += f' Reset {deleted_reset_count} items whose drafts were deleted on Etsy.com.'

        return jsonify({'message': msg}), 200
    except Exception as e:
        print(f"[app] etsySyncOrders exception: {e}")
        return jsonify(message(f'Etsy Sync Orders Exception: {e}')), 500

@app.route('/api/markSold/<sku_group>/<int:sku_id>', methods=['POST'])
def markSold(sku_group: str, sku_id: int):
    data = request.json or {}
    price = data.get('price', 0.0)
    channel = data.get('channel', 'Offline')
    
    with db_instance.conn as conn:
        curs = conn.cursor()
        curs.execute("""
            UPDATE inventory 
            SET status = 'SOLD', 
                sold_price = ?, 
                sold_channel = ?, 
                sold_at = datetime('now'), 
                updated_at = datetime('now') 
            WHERE sku_group = ? AND sku_id = ?;
        """, (price, channel, sku_group, sku_id))
        conn.commit()
        if curs.rowcount > 0:
            trigger_async_sync()
            return jsonify(message(f'Marked {sku_group}-{sku_id:03d} as SOLD')), 200
        else:
            return jsonify(message('Item not found')), 404

@app.route('/api/restoreItem/<sku_group>/<int:sku_id>', methods=['POST'])
def restoreItem(sku_group: str, sku_id: int):
    with db_instance.conn as conn:
        curs = conn.cursor()
        curs.execute("""
            UPDATE inventory 
            SET status = 'IN_STOCK', 
                updated_at = datetime('now') 
            WHERE sku_group = ? AND sku_id = ?;
        """, (sku_group, sku_id))
        conn.commit()
        if curs.rowcount > 0:
            trigger_async_sync()
            return jsonify(message(f'Restored {sku_group}-{sku_id:03d} to IN_STOCK')), 200
        else:
            return jsonify(message('Item not found')), 404

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
            sku_str = f"{sku_group.upper()}-{sku_id:03d}"
            client.update_listing_inventory(access_token, str(listing_id), sku_str, item.get('etsy_price', 12.99))
            client.upload_s3_photos_for_listing(access_token, str(listing_id), sku_group, sku_id)
            # Update database status
            with db_instance.conn as conn:
                curs = conn.cursor()
                curs.execute("""
                    UPDATE inventory 
                    SET status = 'LISTED_ETSY', 
                        etsy_listing_id = ?, 
                        updated_at = datetime('now') 
                    WHERE sku_group = ? AND sku_id = ?;
                """, (str(listing_id), sku_group, sku_id))
                conn.commit()
            trigger_async_sync()

        return jsonify({'message': f'Published draft listing #{listing_id} to Etsy!', 'listing': listing}), 200
    except Exception as e:
        return jsonify(message(f'Etsy Push Exception: {e}')), 500

def sync_deleted_etsy_drafts(client, access_token):
    """
    Cross-checks local database listings against live Etsy active & draft listings.
    If a draft/listing was deleted from Etsy.com, resets local item back to IN_STOCK.
    """
    reset_count = 0
    try:
        active_resp = client.get_shop_listings_by_state(access_token, state='active', limit=100)
        draft_resp = client.get_shop_listings_by_state(access_token, state='draft', limit=100)
        inactive_resp = client.get_shop_listings_by_state(access_token, state='inactive', limit=100)

        live_ids = set()
        for resp in [active_resp, draft_resp, inactive_resp]:
            for lst in resp.get('results', []):
                if lst.get('listing_id'):
                    live_ids.add(str(lst.get('listing_id')))

        from datetime import datetime, timezone
        with db_instance.conn as conn:
            curs = conn.cursor()
            curs.execute("SELECT sku_group, sku_id, etsy_listing_id FROM inventory WHERE is_deleted = 0 AND etsy_listing_id IS NOT NULL AND etsy_listing_id != '' AND (status IS NULL OR status = 'LISTED_ETSY');")
            rows = curs.fetchall()
            
            for row in rows:
                loc_id = str(row['etsy_listing_id'])
                if loc_id not in live_ids:
                    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    curs.execute("""
                        UPDATE inventory 
                        SET status = 'IN_STOCK', 
                            etsy_listing_id = NULL, 
                            updated_at = ? 
                        WHERE sku_group = ? AND sku_id = ?;
                    """, (now_str, row['sku_group'], row['sku_id']))
                    reset_count += curs.rowcount

                    if turso_client is not None:
                        try:
                            turso_client.execute("""
                                UPDATE inventory 
                                SET status = 'IN_STOCK', 
                                    etsy_listing_id = '', 
                                    updated_at = ? 
                                WHERE sku_group = ? AND sku_id = ?;
                            """, [now_str, row['sku_group'], row['sku_id']])
                        except Exception as te:
                            print(f"[sync] Turso draft reset notice for {row['sku_group']}-{row['sku_id']}: {te}")

            if reset_count > 0:
                conn.commit()
                trigger_async_sync()
                print(f"[sync] Reset {reset_count} local items whose Etsy drafts/listings were deleted on Etsy.com!")
    except Exception as e:
        print(f"[sync] sync_deleted_etsy_drafts error: {e}")
    return reset_count

@app.route('/api/etsy/liveStats', methods=['GET'])
def etsyLiveStats():
    try:
        from tgnj_app.core.etsy_client import EtsyClient
        api_key, shared_secret, shop_id, access_token, refresh_token = get_fresh_etsy_tokens()

        if not api_key or not access_token or not shop_id:
            return jsonify({
                'connected': False,
                'active': 0,
                'draft': 0,
                'reset_drafts': 0
            }), 200

        client = EtsyClient(api_key=api_key, shared_secret=shared_secret, shop_id=shop_id)
        
        # Cross-check and reset deleted drafts
        reset_count = sync_deleted_etsy_drafts(client, access_token)

        active_resp = client.get_shop_listings_by_state(access_token, state='active')
        draft_resp = client.get_shop_listings_by_state(access_token, state='draft')
        
        return jsonify({
            'connected': True,
            'active': active_resp.get('count', len(active_resp.get('results', []))),
            'draft': draft_resp.get('count', len(draft_resp.get('results', []))),
            'reset_drafts': reset_count
        }), 200
    except Exception as e:
        print(f"[app] etsyLiveStats exception: {e}")
        return jsonify({
            'connected': False,
            'active': 0,
            'draft': 0,
            'reset_drafts': 0
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
    import time
    from tgnj_app.core.etsy_client import EtsyClient
    api_key, shared_secret, shop_id, access_token, refresh_token = get_fresh_etsy_tokens()

    if not api_key or not access_token or not shop_id:
        return jsonify(message('Etsy authorization required')), 400
        
    client = EtsyClient(api_key=api_key, shared_secret=shared_secret, shop_id=shop_id)

    data = request.json or {}
    items = data.get('items', [])
    gemstone_name = data.get('gemstone_name')
    price = data.get('price')
    custom_description = data.get('custom_description', '')
    primary_color = data.get('primary_color', '')
    
    total = len(items)
    success = 0
    failed = 0
    results = []

    # Pre-fetch shipping profiles, readiness state, and shop sections once for entire batch
    shipping_profile_id = None
    readiness_state_id = None
    matched_section_id = None
    try:
        profiles = client.get_shipping_profiles(access_token)
        if profiles:
            shipping_profile_id = profiles[0].get("shipping_profile_id")
        states = client.get_readiness_states(access_token)
        if states:
            readiness_state_id = states[0].get("readiness_state_id")
        
        sections = client.get_shop_sections(access_token)
        if sections and gemstone_name:
            g_lower = gemstone_name.strip().lower()
            section_map = {sec.get("title", "").strip().lower(): sec.get("shop_section_id") for sec in sections if sec.get("title")}
            if g_lower in section_map:
                matched_section_id = section_map[g_lower]
            else:
                for sec_title, sec_id in section_map.items():
                    if g_lower in sec_title or sec_title in g_lower:
                        matched_section_id = sec_id
                        break
            if matched_section_id:
                print(f"[bulkPush] Auto-matched shop section '{gemstone_name}' -> Section ID #{matched_section_id}")
    except Exception as e:
        print(f"[bulkPush] Pre-fetch notice: {e}")

    batch_start_time = time.perf_counter()
    draft_times = []
    inv_times = []
    photo_times = []

    def process_single_item(req_item):
        item_start_time = time.perf_counter()
        sku_group = req_item.get('sku_group')
        sku_id = req_item.get('sku_id')
        
        if sku_group is None or sku_id is None:
            return None
            
        padded_sku = str(sku_id).zfill(3)
        sku_key = f"{sku_group}-{padded_sku}"
            
        # Fetch item from database using thread-safe connection
        import sqlite3 as sql
        db_uri = f"{db_instance.path.as_uri()}?mode=rw"
        item = None
        conn = sql.connect(db_uri, uri=True)
        conn.row_factory = sql.Row
        try:
            curs = conn.cursor()
            curs.execute("SELECT * FROM inventory WHERE sku_group = ? AND sku_id = ? AND is_deleted = 0;", (sku_group, sku_id))
            row = curs.fetchone()
            if row:
                item = dict(row)
        finally:
            conn.close()

        if not item:
            return {"sku": sku_key, "error": "Item not found in database", "status": "failed", "is_success": False}

        # Prevent duplicate listing creation if already listed on Etsy (locally or on Turso)
        if item.get('etsy_listing_id') or item.get('status') == 'LISTED_ETSY':
            return {"sku": sku_key, "listing_id": item.get('etsy_listing_id'), "error": "Already listed on Etsy", "status": "skipped", "is_success": False}

        if turso_client is not None:
            try:
                r_rows = turso_client.query_rows(
                    "SELECT etsy_listing_id, status FROM inventory WHERE sku_group = ? AND sku_id = ?;",
                    [sku_group, sku_id]
                )
                if r_rows and r_rows[0]:
                    r_lid = r_rows[0].get('etsy_listing_id')
                    r_status = r_rows[0].get('status')
                    if r_lid or r_status == 'LISTED_ETSY':
                        return {"sku": sku_key, "listing_id": r_lid, "error": "Already listed on Etsy (remote)", "status": "skipped", "is_success": False}
            except Exception as te:
                print(f"[bulkPush] Turso pre-check notice for {sku_key}: {te}")
            
        if gemstone_name:
            item['gemstone_name'] = gemstone_name
        if price:
            item['etsy_price'] = price
        if custom_description:
            item['custom_description'] = custom_description
            
        # Attempt listing creation with automatic token refresh and rate limit retries
        max_retries = 3
        attempt = 0

        while attempt < max_retries:
            attempt += 1
            try:
                current_access = db_instance.get_etsy_config('access_token')

                t0 = time.perf_counter()
                listing = client.create_draft_listing(
                    current_access, 
                    item, 
                    shipping_profile_id=shipping_profile_id, 
                    readiness_state_id=readiness_state_id,
                    shop_section_id=matched_section_id
                )
                t_draft = time.perf_counter() - t0

                listing_id = listing.get('listing_id')
                if not listing_id:
                    raise Exception(f"Etsy API did not return a valid listing_id: {listing}")

                # Update dedicated property attributes
                try:
                    COLOR_MAP = {
                        'black': (1, 'Black'), 'blue': (2, 'Blue'), 'brown': (3, 'Brown'), 'green': (4, 'Green'),
                        'gray': (5, 'Gray'), 'orange': (6, 'Orange'), 'pink': (7, 'Pink'), 'purple': (8, 'Purple'),
                        'red': (9, 'Red'), 'white': (10, 'White'), 'yellow': (11, 'Yellow'), 'gold': (1214, 'Gold'),
                        'silver': (1215, 'Silver'), 'bronze': (1216, 'Bronze'), 'copper': (1218, 'Copper'),
                        'clear': (1219, 'Clear'), 'rainbow': (1220, 'Rainbow'), 'turquoise': (2, 'Blue')
                    }
                    if primary_color and primary_color.strip().lower() in COLOR_MAP:
                        c_id, c_name = COLOR_MAP[primary_color.strip().lower()]
                        client.update_listing_property(current_access, listing_id, 200, [c_name], [c_id])
                    
                    client.update_listing_property(current_access, listing_id, 47626759760, ["Jewelry making"], [561])
                    
                    SHAPE_MAP = {
                        'oval': (353, 'Oval'), 'pear': (354, 'Pear'), 'cushion': (331, 'Cushion'),
                        'heart': (344, 'Heart'), 'marquise': (349, 'Marquise'), 'round': (364, 'Round'),
                        'teardrop': (375, 'Teardrop'), 'triangle': (376, 'Triangle'), 'trillion': (377, 'Trillion'),
                        'rectangle': (361, 'Rectangle'), 'square': (371, 'Square'), 'emerald': (339, 'Emerald')
                    }
                    shape_raw = (item.get("shape") or "").strip().lower()
                    if shape_raw in SHAPE_MAP:
                        s_id, s_name = SHAPE_MAP[shape_raw]
                        client.update_listing_property(current_access, listing_id, 47626759726, [s_name], [s_id])

                    client.update_listing_property(current_access, listing_id, 570246213610, ["Natural"], [5104])
                    client.update_listing_property(current_access, listing_id, 136027449574, ["Yes"], [2313])
                    client.update_listing_property(current_access, listing_id, 570246213541, ["Yes"], [4557])
                except Exception as pe:
                    print(f"[bulkPush] Property update notice for {listing_id}: {pe}")

                t1 = time.perf_counter()
                client.update_listing_inventory(
                    current_access, 
                    str(listing_id), 
                    sku_key, 
                    item.get('etsy_price', 12.99),
                    readiness_state_id=readiness_state_id
                )
                t_inv = time.perf_counter() - t1

                t2 = time.perf_counter()
                client.upload_s3_photos_for_listing(current_access, str(listing_id), sku_group, sku_id)
                t_photos = time.perf_counter() - t2

                from datetime import datetime, timezone
                now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

                # Update local database status
                conn_w = sql.connect(db_uri, uri=True)
                try:
                    curs_w = conn_w.cursor()
                    curs_w.execute("""
                        UPDATE inventory 
                        SET status = 'LISTED_ETSY', 
                            etsy_listing_id = ?, 
                            updated_at = ? 
                        WHERE sku_group = ? AND sku_id = ?;
                    """, (str(listing_id), now_str, sku_group, sku_id))
                    conn_w.commit()
                finally:
                    conn_w.close()

                # Update Turso directly with synchronized timestamp
                if turso_client is not None:
                    try:
                        turso_client.execute("""
                            UPDATE inventory 
                            SET status = 'LISTED_ETSY', 
                                etsy_listing_id = ?, 
                                updated_at = ? 
                            WHERE sku_group = ? AND sku_id = ?;
                        """, [str(listing_id), now_str, sku_group, sku_id])
                    except Exception as te:
                        print(f"[bulkPush] Turso direct update notice for {sku_key}: {te}")
                
                item_total_time = time.perf_counter() - item_start_time
                print(f"[bulkPush] {sku_key} listed in {item_total_time:.2f}s (Draft: {t_draft:.2f}s | SKU: {t_inv:.2f}s | Photos: {t_photos:.2f}s)")
                
                return {
                    "sku": sku_key, 
                    "listing_id": listing_id, 
                    "status": "success",
                    "duration_sec": round(item_total_time, 2),
                    "is_success": True,
                    "t_draft": t_draft,
                    "t_inv": t_inv,
                    "t_photos": t_photos
                }
                    
            except Exception as e:
                err_msg = str(e).lower()
                is_auth_error = ("401" in err_msg or "expired" in err_msg or "unauthorized" in err_msg or "invalid_token" in err_msg)
                is_rate_limit = ("429" in err_msg or "too many requests" in err_msg)
                if is_auth_error and attempt < max_retries:
                    refresh_etsy_token_if_needed(client, db_instance.get_etsy_config('refresh_token'))
                    continue
                elif is_rate_limit and attempt < max_retries:
                    time.sleep(3.0)
                    continue
                
                if attempt >= max_retries:
                    return {"sku": sku_key, "error": str(e), "status": "failed", "is_success": False}

        return {"sku": sku_key, "error": "Max retries reached", "status": "failed", "is_success": False}

    # Deduplicate input items by (sku_group, sku_id) key
    seen = set()
    unique_items = []
    for item in items:
        key = (item.get('sku_group'), item.get('sku_id'))
        if key not in seen and key[0] is not None and key[1] is not None:
            seen.add(key)
            unique_items.append(item)
    items = unique_items
    total = len(items)

    def process_chunk(item_list):
        chunk_results = []
        for req_item in item_list:
            res = process_single_item(req_item)
            if res:
                chunk_results.append(res)
        return chunk_results

    chunk_even = items[0::2]
    chunk_odd = items[1::2]
    chunks = [c for c in [chunk_even, chunk_odd] if len(c) > 0]

    import queue
    import json
    from flask import Response, stream_with_context

    q = queue.Queue()
    completed_counter = [0]

    def process_chunk(item_list):
        for req_item in item_list:
            res = process_single_item(req_item)
            if res:
                completed_counter[0] += 1
                q.put((completed_counter[0], res))
        q.put(None) # Signal thread chunk finished

    @stream_with_context
    def generate():
        nonlocal success, failed
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=max(1, len(chunks)))
        for c in chunks:
            executor.submit(process_chunk, c)

        finished_chunks = 0
        expected_chunks = len(chunks)

        while finished_chunks < expected_chunks:
            msg = q.get()
            if msg is None:
                finished_chunks += 1
                continue
            
            comp_count, res = msg
            if res.get("is_success"):
                success += 1
                if "t_draft" in res: draft_times.append(res["t_draft"])
                if "t_inv" in res: inv_times.append(res["t_inv"])
                if "t_photos" in res: photo_times.append(res["t_photos"])
                results.append({
                    "sku": res["sku"],
                    "listing_id": res["listing_id"],
                    "status": "success",
                    "duration_sec": res["duration_sec"]
                })
            else:
                if res.get("status") == "skipped":
                    results.append({"sku": res["sku"], "listing_id": res.get("listing_id"), "error": res.get("error"), "status": "skipped"})
                else:
                    failed += 1
                    results.append({"sku": res["sku"], "error": res.get("error"), "status": "failed"})

            # Yield live progress NDJSON event
            event_data = {
                "type": "progress",
                "completed": comp_count,
                "total": total,
                "sku": res.get("sku"),
                "listing_id": res.get("listing_id"),
                "status": res.get("status"),
                "duration_sec": res.get("duration_sec", 0),
                "t_draft": round(res.get("t_draft", 0), 2),
                "t_inv": round(res.get("t_inv", 0), 2),
                "t_photos": round(res.get("t_photos", 0), 2),
                "error": res.get("error", "")
            }
            yield json.dumps(event_data) + "\n"

        executor.shutdown(wait=True)

        total_batch_duration = time.perf_counter() - batch_start_time
        avg_per_item = (total_batch_duration / success) if success > 0 else 0
        avg_draft = (sum(draft_times) / len(draft_times)) if draft_times else 0
        avg_inv = (sum(inv_times) / len(inv_times)) if inv_times else 0
        avg_photos = (sum(photo_times) / len(photo_times)) if photo_times else 0

        print(f"[bulkPush] BATCH COMPLETE: Pushed {success}/{total} items in {total_batch_duration:.2f}s (avg {avg_per_item:.2f}s/item)")

        if success > 0:
            trigger_async_sync()

        complete_event = {
            "type": "complete",
            "total": total,
            "success": success,
            "failed": failed,
            "metrics": {
                "total_duration_sec": round(total_batch_duration, 2),
                "avg_sec_per_item": round(avg_per_item, 2),
                "step_averages_sec": {
                    "draft_creation": round(avg_draft, 2),
                    "sku_assignment": round(avg_inv, 2),
                    "photo_uploads": round(avg_photos, 2)
                }
            },
            "results": results
        }
        yield json.dumps(complete_event) + "\n"

    return Response(generate(), mimetype='application/x-ndjson')