import os
import webview
from flask import Flask, render_template, jsonify, request
from tgnj_app.core.database import database

#_________________________________ setup __________________________________
gui_dir  = os.path.dirname(__file__)
app = Flask(__name__,template_folder=os.path.join(gui_dir,"templates"), static_folder=os.path.join(gui_dir,'static'))
db_instance : database = None

#____________________________ utility functions______________________

def message(string:str)-> dict:
    return {"message":string}

# ________________________ ROUTES ______________________
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/getData/<sku_group>',methods=['GET'])
def getData(sku_group:str):
    data = db_instance.get_items_by_group(sku_group)
    cleanData = [dict(row) for row in data]
    return jsonify(cleanData)

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

