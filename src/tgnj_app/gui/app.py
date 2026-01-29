import os
import webview
from flask import Flask, render_template, jsonify, request
from tgnj_app.core.database import database
from pathlib import Path
import json

#____________________________ utility functions______________________

def setConfig(db_path:Path):
    if os.path.exists:
        Path = str(db_path)
        config = {
            "db_Path":Path
        }
        with open(config_location, "w") as f:
            json.dump(config,f)
        return Path
    else:
        raise FileNotFoundError

def message(string:str)-> dict:
    return {"message":string}

def getConfig():
    with open(config_location,'r') as f:
        config = json.load(f)
        if not Path(config.get('db_Path')).exists():
            raise FileNotFoundError()
        else:
            return config


#_________________________________ setup __________________________________
config_location = Path(__file__).resolve().parent.parent.parent.parent / "config.json"
gui_dir  = os.path.dirname(__file__)
app = Flask(__name__,template_folder=os.path.join(gui_dir,"templates"), static_folder=os.path.join(gui_dir,'static'))
config = getConfig()
try:
    db_path = Path()
    db_instance : database = database(db_path)
except FileNotFoundError as e:
    print(e)
    setConfig(Path(''))
    

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