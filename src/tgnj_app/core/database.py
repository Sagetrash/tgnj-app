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

    def edit_item(self):
        pass
    
    def sold_item(self):
        pass

    def get_items_by_group(self):
        pass

    def get_item_by_sku(self):
        pass

    def delete_item(self):
        pass


if __name__ == "__main__":
    pass