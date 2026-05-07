# ─── MAIN APPLICATION ─────────────────────────────────────────────────────────
# Assembles the mixins from the core/ folder into a single GmailApp class.
# Each mixin provides a cohesive group of methods:
#
#   UiBuilderMixin      → tkinter widget construction
#   MailListMixin       → connection, labels, message list
#   MailDetailMixin     → message detail, browser, local file
#   MailActionsMixin    → archive, star, delete, label
#   WindowsOpenerMixin  → secondary windows (compose, filters…)

import tkinter as tk

from core.ui_builder     import UiBuilderMixin
from core.mail_list      import MailListMixin
from core.mail_detail    import MailDetailMixin
from core.mail_actions   import MailActionsMixin
from core.windows_opener import WindowsOpenerMixin


class GmailApp(UiBuilderMixin, MailListMixin, MailDetailMixin,
               MailActionsMixin, WindowsOpenerMixin, tk.Tk):
    """Main window of the Gmail Desktop application."""

    def __init__(self):
        super().__init__()
        self.title("Gmail Desktop")
        self.geometry("1200x700")
        self.configure(bg="#1e1e2e")

        # ── Shared state across all mixins ────────────────────────────────────
        self.service           = None  # Gmail API service
        self.messages          = []    # Cache of displayed messages
        self.labels_map        = {}    # {label_id: label_name}
        self.current_mid       = None  # ID of the currently displayed message
        self.current_thread_id = None  # Thread ID of the currently displayed message
        self.user_email        = ""    # Email address of the connected account

        self._build_ui()
        self._connect()
