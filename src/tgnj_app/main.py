from tgnj_app.gui.app import app
import webbrowser
from threading import Timer
import os
def open_browser():
    webbrowser.open_new_tab("http://127.0.0.1:5000")
def main():
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        Timer(1.5, open_browser).start()
    
    app.run(host="127.0.0.1",port=5000,debug=True)


if __name__ == "__main__":
    main()