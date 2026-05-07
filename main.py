# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
# Launches the PyWebView window with the Gmail API backend.
#
# BACKEND NOTE:
#   pywebview on Windows normally uses WinForms (via pythonnet).
#   pythonnet has no pre-built wheel for Python 3.14, so we force the Qt backend
#   (PySide6) by setting PYWEBVIEW_GUI before importing webview.

import os
os.environ['PYWEBVIEW_GUI'] = 'qt'   # use PySide6 WebEngine instead of WinForms

import webview
from api import GmailAPI

if __name__ == "__main__":
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
