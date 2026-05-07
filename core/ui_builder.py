# ─── MIXIN: UI CONSTRUCTION ───────────────────────────────────────────────────
# Contains all methods that build the tkinter widgets for GmailApp.

import tkinter as tk
from tkinter import ttk

from tkinterweb import HtmlFrame


class UiBuilderMixin:
    """Builds all widgets of the main window."""

    # ── ENTRY POINT ───────────────────────────────────────────────────────────

    def _build_ui(self):
        """Assembles all UI blocks."""
        self._apply_styles()
        self._build_header()
        self._build_toolbar()
        self._build_main_pane()
        self._build_context_menu()

    # ── THEME ─────────────────────────────────────────────────────────────────

    def _apply_styles(self):
        """Applies the dark theme (Catppuccin Mocha palette) to all ttk widgets."""
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame",       background="#1e1e2e")
        style.configure("TLabel",       background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
        style.configure("TButton",      background="#313244", foreground="#cdd6f4", font=("Segoe UI", 10), padding=6)
        style.map("TButton",            background=[("active", "#45475a")])
        style.configure("Accent.TButton", background="#89b4fa", foreground="#1e1e2e", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Accent.TButton",     background=[("active", "#74c7ec")])
        style.configure("Treeview",     background="#313244", foreground="#cdd6f4",
                        fieldbackground="#313244", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#45475a", foreground="#89b4fa", font=("Segoe UI", 10, "bold"))
        style.map("Treeview",           background=[("selected", "#45475a")])

    # ── HEADER BAR ────────────────────────────────────────────────────────────

    def _build_header(self):
        """Top bar: app title + connection status indicator."""
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="📧 Gmail Desktop",
                  font=("Segoe UI", 14, "bold"), foreground="#89b4fa").pack(side="left")
        self.status_var = tk.StringVar(value="Connecting...")
        ttk.Label(top, textvariable=self.status_var, foreground="#a6e3a1").pack(side="right")

    # ── TOOLBAR ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        """Toolbar: action buttons, search field and label filter."""
        toolbar = ttk.Frame(self, padding=(10, 0, 10, 8))
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="🔄 Refresh",            command=self._refresh).pack(side="left", padx=2)
        ttk.Button(toolbar, text="✏️ New email",           command=self._open_compose, style="Accent.TButton").pack(side="left", padx=2)
        ttk.Button(toolbar, text="🗂️ Labels",              command=self._open_labels).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🧹 Cleanup",             command=self._open_cleanup).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🚫 Filters & Blocked",  command=self._open_filters).pack(side="left", padx=2)
        ttk.Button(toolbar, text="📂 Open file",           command=self._open_local_file).pack(side="left", padx=2)

        # Search bar
        ttk.Label(toolbar, text="🔍").pack(side="left", padx=(20, 2))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=2)
        search_entry.bind("<Return>", lambda e: self._search())
        ttk.Button(toolbar, text="Search", command=self._search).pack(side="left", padx=2)

        # Label/folder filter
        ttk.Label(toolbar, text="Filter:").pack(side="left", padx=(20, 2))
        self.filter_var = tk.StringVar(value="INBOX")
        self.filter_combo = ttk.Combobox(toolbar, textvariable=self.filter_var, width=18, state="readonly")
        self.filter_combo["values"] = ["INBOX", "SENT", "STARRED", "SPAM", "TRASH"]
        self.filter_combo.pack(side="left", padx=2)
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh())

    # ── MAIN PANE ─────────────────────────────────────────────────────────────

    def _build_main_pane(self):
        """Main area: list on the left, detail on the right, resizable divider."""
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._build_mail_list(paned)
        self._build_detail_pane(paned)

    def _build_mail_list(self, paned):
        """Left panel: Treeview with From / Subject / Date columns."""
        left = ttk.Frame(paned)
        paned.add(left, weight=1)

        cols = ("from", "subject", "date")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("from",    text="From")
        self.tree.heading("subject", text="Subject")
        self.tree.heading("date",    text="Date")
        self.tree.column("from",    width=200, minwidth=120)
        self.tree.column("subject", width=320, minwidth=150)
        self.tree.column("date",    width=140, minwidth=100)

        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Button-3>",         self._context_menu)

    def _build_detail_pane(self, paned):
        """Right panel: metadata, HTML body, quick action buttons."""
        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        self.detail_meta = ttk.Label(right, text="", wraplength=500,
                                     justify="left", foreground="#a6adc8")
        self.detail_meta.pack(fill="x", padx=8, pady=(8, 4))

        self.detail_text = HtmlFrame(right, messages_enabled=False)
        self.detail_text.pack(fill="both", expand=True, padx=4, pady=4)

        actions = ttk.Frame(right)
        actions.pack(fill="x", padx=8, pady=4)
        ttk.Button(actions, text="↩ Reply",            command=self._reply).pack(side="left", padx=2)
        ttk.Button(actions, text="📦 Archive",         command=self._archive_selected).pack(side="left", padx=2)
        ttk.Button(actions, text="⭐ Star",            command=self._star_selected).pack(side="left", padx=2)
        ttk.Button(actions, text="🗑️ Delete",          command=self._trash_selected).pack(side="left", padx=2)
        ttk.Button(actions, text="🌐 Open in browser",
                   command=self._open_in_browser).pack(side="right", padx=2)

    # ── CONTEXT MENU ──────────────────────────────────────────────────────────

    def _build_context_menu(self):
        """Right-click context menu on a message in the list."""
        self.ctx_menu = tk.Menu(self, tearoff=0, bg="#313244", fg="#cdd6f4",
                                activebackground="#45475a", activeforeground="#cdd6f4")
        self.ctx_menu.add_command(label="📦 Archive",         command=self._archive_selected)
        self.ctx_menu.add_command(label="⭐ Star",            command=self._star_selected)
        self.ctx_menu.add_command(label="✅ Mark as read",    command=self._mark_read)
        self.ctx_menu.add_command(label="🗑️ Move to trash",   command=self._trash_selected)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="🏷️ Apply a label",   command=self._apply_label_dialog)
