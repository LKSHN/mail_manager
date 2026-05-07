# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
import os
os.environ['PYWEBVIEW_GUI'] = 'qt'   # use PySide6; pythonnet has no Python 3.14 wheel

import db
import webview
from api import GmailAPI

if __name__ == "__main__":
    db.init_db()   # create tables on first run, no-op if already exist

    api     = GmailAPI()
    ui_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "ui", "index.html"))

    window = webview.create_window(
        title            = "Mail Manager",
        url              = ui_path,
        js_api           = api,
        width            = 1280,
        height           = 820,
        min_size         = (960, 600),
        background_color = "#0d1117",
    )
    api.set_window(window)
    webview.start(debug=False)
