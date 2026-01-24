import sqlite3 as sql
from pathlib import Path

class database:
    def __init__(self,path: Path):
        try:
            self.path = path
            self.conn = sql.connect(self.path)
        except sql.DatabaseError as e:
            raise sql.DatabaseError
    
    def add_item(self,sku_group,sku_id,shape,weight,length,width,depth):
        query = f"""
        INSERT INTO inventory (sku_group,sku_id,shape,weight,length,width,depth) VALUES (?,?,?,?,?,?,?);
        """
        with self.conn as conn:
            try:
                cur = conn.cursor()
                cur.execute(query,(sku_group,sku_id,shape,weight,length,width,depth))
                return True
            except sql.Error:
                return False

    def edit_item(self,sku_group:str,sku_id:int,shape:str=None,weight:float=None,length:int=None,width:int=None,depth:int=None):
        allparams = locals()
        updates = {k:v for k, v in allparams.items() if v is not None and k not in ('self','sku_group','sku_id')}
        
        set_clause = ", ".join([f"{k} = ? " for k in updates.keys()])
        query = f"""
        UPDATE inventory SET {set_clause} WHERE id = (SELECT id FROM INVENTORY WHERE sku_group = ? AND sku_id = ?);
         """
        params = list(updates.values()) + [sku_group,sku_id]
        
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(query,params)
                return True
            except sql.Error:
                return False

    def sold_item(self):
        pass

    def get_items_by_group(self,sku_group:str):
        query = """
            SELECT * FROM inventory where sku_group = ?;
        """
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(query,(sku_group,))
                return curs.fetchall()
            except sql.Error:
                return False

    def get_item_by_sku(self,sku_group:str,sku_id:int):
        query = """
        SELECT * FROM inventory where id = (SELECT id FROM INVENTORY WHERE sku_group = ? AND sku_id = ?);
        """
        with self.conn as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(query,(sku_group,sku_id))
                return cursor.fetchone()
            except sql.Error:
                return False

    def delete_item(self,sku_group: str, sku_id: int):
        query = """
        DELETE FROM INVENTORY WHERE id = (SELECT id FROM INVENTORY WHERE sku_group = ? AND sku_id = ?);
        """
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(query,(sku_group,sku_id))
                return True
            except sql.Error:
                return False

if __name__ == "__main__":
    pass