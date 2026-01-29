from tgnj_app.gui.app import app, config_location
import tgnj_app.gui.app as gui_module
from tgnj_app.core.database import database
from pathlib import Path
from threading import Thread
import webview

Base_DIR = Path(__file__).resolve().parent
icon_path = (Base_DIR/"gui"/"static"/"logo.ico")
def start_dev_server():
    app.run(port=5000)

if __name__ == "__main__":
    t = Thread(target=start_dev_server)
    t.daemon = True
    t.start()
    webview.create_window("TGNJ MANAGEMENT APP","http://127.0.0.1:5000")
    if icon_path.exists():
        webview.start(icon=str(icon_path))
    else:
        webview.start()