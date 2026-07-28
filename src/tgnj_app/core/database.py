import sqlite3 as sql
from pathlib import Path

class database:
    def __init__(self, path: Path):
        try:
            self.path = Path(path).resolve()
            
            db_uri = f"{self.path.as_uri()}?mode=rw"
            
            self.conn = sql.connect(db_uri, uri=True, check_same_thread=False)
            
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.row_factory = sql.Row
            
            try:
                self.conn.execute("ALTER TABLE inventory ADD COLUMN created_at TEXT DEFAULT (datetime('now'))")
            except sql.OperationalError:
                pass
            try:
                self.conn.execute("ALTER TABLE inventory ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))")
            except sql.OperationalError:
                pass
            try:
                self.conn.execute("ALTER TABLE inventory ADD COLUMN is_deleted INTEGER DEFAULT 0")
            except sql.OperationalError:
                pass
            
            self.conn.execute("CREATE TABLE IF NOT EXISTS _sync_meta (key TEXT PRIMARY KEY, value TEXT);")
            

        except sql.OperationalError as e:
            raise FileNotFoundError(f"Database not found at {self.path}. Details: {e}")
        except sql.DatabaseError as e:
            raise e
    
    def add_item(self,sku_group,sku_id,shape,weight,length,width,depth):
        query = """
        INSERT INTO inventory (sku_group,sku_id,shape,weight,length,width,depth,created_at,updated_at) VALUES (?,?,?,?,?,?,?,datetime('now'),datetime('now'));
        """
        curs = None
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(query,(sku_group,sku_id,shape,weight,length,width,depth))
                return True
            except sql.Error:
                return False
            finally:
                if curs:
                    curs.close()

    def edit_item(self,sku_group:str,sku_id:int,shape:str=None,weight:float=None,length:int=None,width:int=None,depth:int=None):
        allparams = locals()
        updates = {k:v for k, v in allparams.items() if v is not None and k not in ('self','sku_group','sku_id')}
        
        set_clause = ", ".join([f"{k} = ? " for k in updates.keys()])
        query = f"""
        UPDATE inventory SET {set_clause}, updated_at = datetime('now') WHERE id = (SELECT id FROM inventory WHERE sku_group = ? AND sku_id = ?);
         """
        params = list(updates.values()) + [sku_group,sku_id]
        
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(query,params)
                curs.close()
                return True
            except sql.Error:
                return False

    def get_items_by_group(self,sku_group:str):
        query = """
            SELECT * FROM inventory where sku_group = ? AND COALESCE(is_deleted, 0) = 0;
        """
        curs = None
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(query,(sku_group,))
                return curs.fetchall()
            except sql.Error:
                return False
            finally:
                if curs:
                    curs.close()

    def get_item_by_sku(self,sku_group:str,sku_id:int):
        query = """
        SELECT * FROM inventory where id = (SELECT id FROM inventory WHERE sku_group = ? AND sku_id = ?) AND COALESCE(is_deleted, 0) = 0;
        """ 
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(query,(sku_group,sku_id))
                return curs.fetchone()
            except sql.Error:
                return False
            finally:
                if curs:
                    curs.close()

    def delete_item(self,sku_group: str, sku_id: int):
        query = """
        UPDATE inventory SET is_deleted = 1, updated_at = datetime('now') WHERE id = (SELECT id FROM inventory WHERE sku_group = ? AND sku_id = ?);
        """
        curs = None
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(query,(sku_group,sku_id))
                return True
            except sql.Error:
                return False
            finally:
                if curs:
                    curs.close()

    def extract_data(self,sku_group:str):
        query = """
            SELECT UPPER(SUBSTR(shape, 1, 1)) || LOWER(SUBSTR(shape, 2)), length || ' mm', width || ' mm', depth || ' mm', printf('%.2f',weight) || ' Ct.' FROM inventory where sku_group = ? AND COALESCE(is_deleted, 0) = 0;
        """
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(query,(sku_group,))
                return curs.fetchall()
            except sql.Error as e:
                return False
            finally:
                if curs:
                    curs.close()

    def get_changes_since(self, timestamp: str) -> list[dict]:
        """Return all rows (including soft-deleted) modified after timestamp."""
        query = """
            SELECT * FROM inventory WHERE updated_at > ? ORDER BY updated_at ASC;
        """
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(query, (timestamp,))
                rows = curs.fetchall()
                return [dict(row) for row in rows]
            except sql.Error:
                return []
            finally:
                if curs:
                    curs.close()

    def apply_remote_change(self, row: dict):
        """
        Upsert a remote row into local SQLite — last-write-wins.
        Only writes if remote updated_at >= local updated_at.
        """
        # Check local updated_at first
        check_query = "SELECT updated_at FROM inventory WHERE id = ?;"
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(check_query, (row['id'],))
                existing = curs.fetchone()
                if existing and existing['updated_at'] and existing['updated_at'] > row.get('updated_at', ''):
                    return  # local is newer — skip
                upsert_query = """
                    INSERT OR REPLACE INTO inventory
                        (id, sku_group, sku_id, shape, weight, length, width, depth,
                         created_at, updated_at, is_deleted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                curs.execute(upsert_query, (
                    row.get('id'), row.get('sku_group'), row.get('sku_id'),
                    row.get('shape'), row.get('weight'), row.get('length'),
                    row.get('width'), row.get('depth'), row.get('created_at'),
                    row.get('updated_at'), row.get('is_deleted', 0)
                ))
            except sql.Error as e:
                print(f"[database] apply_remote_change error: {e}")
            finally:
                if curs:
                    curs.close()

    def get_sync_meta(self, key: str) -> str | None:
        """Read a value from _sync_meta table."""
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute("SELECT value FROM _sync_meta WHERE key = ?;", (key,))
                row = curs.fetchone()
                return row['value'] if row else None
            except sql.Error:
                return None
            finally:
                if curs:
                    curs.close()

    def set_sync_meta(self, key: str, value: str):
        """Write a key-value pair to _sync_meta table."""
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute(
                    "INSERT OR REPLACE INTO _sync_meta (key, value) VALUES (?, ?);",
                    (key, value)
                )
            except sql.Error as e:
                print(f"[database] set_sync_meta error: {e}")
            finally:
                if curs:
                    curs.close()

    def get_all_items(self) -> list[dict]:
        """Return all non-deleted rows (for initial migration / full-sync)."""
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute("SELECT * FROM inventory WHERE COALESCE(is_deleted, 0) = 0;")
                return [dict(row) for row in curs.fetchall()]
            except sql.Error:
                return []
            finally:
                if curs:
                    curs.close()

    def get_count(self) -> int:
        """Return total non-deleted row count."""
        with self.conn as conn:
            try:
                curs = conn.cursor()
                curs.execute("SELECT COUNT(*) as c FROM inventory WHERE COALESCE(is_deleted, 0) = 0;")
                row = curs.fetchone()
                return row['c'] if row else 0
            except sql.Error:
                return 0
            finally:
                if curs:
                    curs.close()

if __name__ == "__main__":
    pass