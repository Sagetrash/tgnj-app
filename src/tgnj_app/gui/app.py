import json
import os, sys, io
from pathlib import Path
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

def start_sync_loop(interval: int = 30):
    """Start the background sync daemon thread. Safe to call once only."""
    global sync_thread_started
    sync_thread_started = True

    def _loop():
        while True:
            time.sleep(interval)
            if turso_client is not None:
                try:
                    result = sync_engine.sync(db_instance, turso_client)
                    print(f"[sync] Auto-sync: pushed={result['pushed']} pulled={result['pulled']}")
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
        return jsonify({'message':"stone added successfully"}),201
    else:
        return jsonify({"message":"error"}), 500

@app.route('/api/deleteItem/<sku_group>/<int:sku_id>',methods=["DELETE"])
def deleteItem(sku_group:str,sku_id:int):
    success = db_instance.delete_item(sku_group=sku_group,sku_id=sku_id)
    if success:
        return jsonify(message("deleted item successfully")), 201
    else:
        return jsonify(message("Error deleting item")), 500

@app.route('/api/editItem/<group>/<int:id>',methods=["PATCH"])
def editItems(group,id):
    data = request.json
    success = db_instance.edit_item(sku_group=group,sku_id=id, **data)
    if success:
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
    turso_url, _, _ = load_turso_config()
    return jsonify({
        'configured': bool(turso_url),
        'turso_url': turso_url or ''
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
        result = sync_engine.sync(db_instance, turso_client)
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