from tgnj_app.gui.app import app
import tgnj_app.gui.app as gui_module
from tgnj_app.core.database import database
from pathlib import Path

def start_dev_server():
    db_path = Path(__file__).parent.parent.parent / "inventory.db"
    db = database(db_path)
    gui_module.db_instance = db
    app.run(port=5000, debug=True)

if __name__ == "__main__":
    start_dev_server()