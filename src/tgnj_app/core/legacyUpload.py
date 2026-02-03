import csv
from tgnj_app.core.database import database


def ReadSpecificColumns(csv_location):
    selectedData = []
    desiredColumns = ['product_id','shape','item length','item width','item depth','weight']
    with open(csv_location,'r',newline='',encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            selectRow:dict = {col: row[col] for col in desiredColumns if col in row}
            a,b = selectRow['product_id'].split('-')
            selectRow['sku_group'],selectRow['sku_id'] = a, int(b)
            del selectRow['product_id']
            selectRow['length'] = int(str(selectRow['item length']).replace('mm',''))
            del selectRow['item length']
            selectRow['width'] = int(str(selectRow['item width']).replace('mm',''))
            del selectRow['item width']
            selectRow['depth'] = int(str(selectRow['item depth']).replace('mm',''))
            del selectRow['item depth']
            selectRow['weight'] = float(str(selectRow['weight']).replace("Cts.",""))
            selectedData.append(selectRow)
    return selectedData
