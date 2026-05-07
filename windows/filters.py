# ─── FILTERS & BLOCKED ADDRESSES WINDOW ──────────────────────────────────────
# Two tabs:
#   - Gmail Filters: list, create and delete filter rules.
#   - Blocked addresses: manage senders automatically sent to spam.

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog


class FiltersWindow(tk.Toplevel):
    """
    Two-tab window for managing Gmail filters and blocked addresses.

    Parameters
    ----------
    parent      : parent window (GmailApp)
    service     : authenticated Gmail API service
    labels_map  : dict {label_id: label_name} shared with GmailApp
    """

    def __init__(self, parent, service, labels_map):
        super().__init__(parent)
        self.service    = service
        self.labels_map = labels_map

        self.title("Filters & Blocked addresses")
        self.geometry("720x500")
        self.configure(bg="#1e1e2e")

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_filters_tab(notebook)
        self._build_blocked_tab(notebook)

        ttk.Button(self, text="Close", command=self.destroy).pack(anchor="e", padx=10, pady=(0, 10))

        # Initial load of both tabs
        self._reload_filters()
        self._reload_blocked()

    def _build_filters_tab(self, notebook):
        """Tab 1: list of active filters with create and delete actions."""
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text="  Gmail Filters  ")

        ttk.Label(tab, text="Active filter rules",
                  font=("Segoe UI", 11, "bold"), foreground="#89b4fa").pack(anchor="w", pady=(0, 6))

        # Treeview with two columns: criteria and actions
        cols = ("criteria", "actions")
        self.filter_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        self.filter_tree.heading("criteria", text="Criteria")
        self.filter_tree.heading("actions",  text="Actions")
        self.filter_tree.column("criteria", width=310, minwidth=150)
        self.filter_tree.column("actions",  width=310, minwidth=150)
        fsb = ttk.Scrollbar(tab, orient="vertical", command=self.filter_tree.yview)
        self.filter_tree.configure(yscrollcommand=fsb.set)
        self.filter_tree.pack(side="left", fill="both", expand=True)
        fsb.pack(side="left", fill="y")

        self.filter_ids = {}  # {tree_iid: gmail_filter_id}

        btn_row = ttk.Frame(tab)
        btn_row.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(btn_row, text="➕ New filter", style="Accent.TButton",
                   command=self._open_create_dialog).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🗑️ Delete",   command=self._delete_filter).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🔄 Refresh",  command=self._reload_filters).pack(side="left", padx=2)
        ttk.Button(btn_row, text="💾 Export",   command=self._export_filters).pack(side="left", padx=2)

    def _build_blocked_tab(self, notebook):
        """Tab 2: list of blocked senders (filter → spam)."""
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text="  Blocked addresses  ")

        ttk.Label(tab, text="Blocked senders (via this application)",
                  font=("Segoe UI", 11, "bold"), foreground="#89b4fa").pack(anchor="w", pady=(0, 4))
        ttk.Label(tab,
                  text="⚠ Gmail's native block list is not accessible via the API.\n"
                       "Only addresses blocked through this application appear here.",
                  foreground="#f38ba8", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))

        self.blocked_list = tk.Listbox(
            tab, bg="#313244", fg="#cdd6f4", selectbackground="#45475a",
            font=("Segoe UI", 10), relief="flat", height=14
        )
        bsb = ttk.Scrollbar(tab, orient="vertical", command=self.blocked_list.yview)
        self.blocked_list.configure(yscrollcommand=bsb.set)
        self.blocked_list.pack(side="left", fill="both", expand=True)
        bsb.pack(side="left", fill="y")

        self.blocked_filter_ids = {}  # {email_address: gmail_filter_id}

        btn_row = ttk.Frame(tab)
        btn_row.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(btn_row, text="🚫 Block an address", style="Accent.TButton",
                   command=self._block_address).pack(side="left", padx=2)
        ttk.Button(btn_row, text="✅ Unblock",   command=self._unblock_address).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🔄 Refresh",   command=self._reload_blocked).pack(side="left", padx=2)
        ttk.Button(btn_row, text="💾 Export",    command=self._export_blocked).pack(side="left", padx=2)

    # ── DISPLAY HELPERS ───────────────────────────────────────────────────────

    def _fmt_criteria(self, c):
        """Formats a Gmail filter's criteria into a readable string."""
        parts = []
        if c.get("from"):    parts.append(f"From: {c['from']}")
        if c.get("to"):      parts.append(f"To: {c['to']}")
        if c.get("subject"): parts.append(f"Subject: {c['subject']}")
        if c.get("query"):   parts.append(f"Words: {c['query']}")
        return " | ".join(parts) or "(all)"

    def _fmt_actions(self, a):
        """Formats a Gmail filter's actions into a readable string."""
        parts   = []
        adds    = a.get("addLabelIds", [])
        removes = a.get("removeLabelIds", [])
        if "INBOX"   in removes: parts.append("Skip inbox")
        if "UNREAD"  in removes: parts.append("Mark as read")
        if "SPAM"    in adds:    parts.append("Mark as spam")
        if "TRASH"   in adds:    parts.append("Delete")
        if "STARRED" in adds:    parts.append("Star")
        custom = [self.labels_map.get(l, l) for l in adds
                  if l not in ("INBOX", "SPAM", "TRASH", "STARRED", "UNREAD")]
        if custom:               parts.append(f"Label: {', '.join(custom)}")
        if a.get("forward"):     parts.append(f"Forward to {a['forward']}")
        return " | ".join(parts) or "(none)"

    # ── FILTERS TAB — ACTIONS ─────────────────────────────────────────────────

    def _reload_filters(self):
        """Reloads the filter list from the Gmail API."""
        self.filter_tree.delete(*self.filter_tree.get_children())
        self.filter_ids.clear()
        try:
            res = self.service.users().settings().filters().list(userId="me").execute()
            for f in res.get("filter", []):
                crit = self._fmt_criteria(f.get("criteria", {}))
                acts = self._fmt_actions(f.get("action", {}))
                iid  = self.filter_tree.insert("", "end", values=(crit, acts))
                self.filter_ids[iid] = f["id"]
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _delete_filter(self):
        """Deletes the selected filter(s) after confirmation."""
        sel = self.filter_tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Confirm", f"Delete {len(sel)} filter(s)?", parent=self):
            return
        for iid in sel:
            fid = self.filter_ids.get(iid)
            if fid:
                self.service.users().settings().filters().delete(userId="me", id=fid).execute()
        self._reload_filters()

    def _open_create_dialog(self):
        """Opens the dialog to create a new filter."""
        CreateFilterDialog(self, self.service, self.labels_map, on_done=self._reload_filters)

    def _export_filters(self):
        """Exports all raw Gmail filters to exports/filters.json."""
        try:
            res     = self.service.users().settings().filters().list(userId="me").execute()
            filters = res.get("filter", [])
            out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, "filters.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(filters, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Export successful", f"{len(filters)} filter(s) exported to:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    # ── BLOCKED TAB — ACTIONS ─────────────────────────────────────────────────

    def _export_blocked(self):
        """Exports blocked addresses (SPAM filters created via this app) to exports/blocked_addresses.txt."""
        try:
            res   = self.service.users().settings().filters().list(userId="me").execute()
            addrs = [
                f["criteria"]["from"]
                for f in res.get("filter", [])
                if f.get("criteria", {}).get("from")
                and "SPAM" in f.get("action", {}).get("addLabelIds", [])
            ]
            out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, "blocked_addresses.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(addrs))
            messagebox.showinfo("Export successful",
                                f"{len(addrs)} address(es) exported to:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _reload_blocked(self):
        """
        Reloads the blocked address list.
        Shows Gmail filters that send a sender to SPAM (created via this application).
        """
        self.blocked_list.delete(0, "end")
        self.blocked_filter_ids.clear()
        try:
            res = self.service.users().settings().filters().list(userId="me").execute()
            for f in res.get("filter", []):
                crit   = f.get("criteria", {})
                acts   = f.get("action", {})
                sender = crit.get("from", "")
                if sender and "SPAM" in acts.get("addLabelIds", []):
                    self.blocked_list.insert("end", sender)
                    self.blocked_filter_ids[sender] = f["id"]
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _block_address(self):
        """Creates a Gmail filter that sends the entered address directly to spam."""
        addr = simpledialog.askstring("Block", "Email address to block:", parent=self)
        if not addr or not addr.strip():
            return
        addr = addr.strip()
        try:
            self.service.users().settings().filters().create(
                userId="me",
                body={
                    "criteria": {"from": addr},
                    "action":   {"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]},
                }
            ).execute()
            self._reload_blocked()
            self._reload_filters()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _unblock_address(self):
        """Deletes the block filter for the selected address."""
        sel = self.blocked_list.curselection()
        if not sel:
            return
        addr = self.blocked_list.get(sel[0])
        fid  = self.blocked_filter_ids.get(addr)
        if not fid:
            return
        if not messagebox.askyesno("Confirm", f"Unblock '{addr}'?", parent=self):
            return
        try:
            self.service.users().settings().filters().delete(userId="me", id=fid).execute()
            self._reload_blocked()
            self._reload_filters()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)


class CreateFilterDialog(tk.Toplevel):
    """
    Modal dialog for creating a new Gmail filter.

    Parameters
    ----------
    parent      : parent window (FiltersWindow)
    service     : authenticated Gmail API service
    labels_map  : dict {label_id: label_name}
    on_done     : callback called after successful creation (to refresh the list)
    """

    def __init__(self, parent, service, labels_map, on_done):
        super().__init__(parent)
        self.service    = service
        self.labels_map = labels_map
        self.on_done    = on_done

        self.title("New filter")
        self.geometry("480x400")
        self.configure(bg="#1e1e2e")
        self.grab_set()  # Blocks the parent window during input

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        # ── Criteria section ──────────────────────────────────────────────────
        ttk.Label(f, text="Criteria", font=("Segoe UI", 10, "bold"),
                  foreground="#89b4fa").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.fields = {}
        criteria_fields = [
            ("From (sender):",    "from"),
            ("To (recipient):",   "to"),
            ("Subject:",          "subject"),
            ("Contains words:",   "query"),
        ]
        for i, (label_text, key) in enumerate(criteria_fields, start=1):
            ttk.Label(f, text=label_text).grid(row=i, column=0, sticky="w", pady=3)
            var = tk.StringVar()
            ttk.Entry(f, textvariable=var, width=30).grid(row=i, column=1, sticky="ew", padx=(8, 0))
            self.fields[key] = var

        ttk.Separator(f, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)

        # ── Actions section ───────────────────────────────────────────────────
        ttk.Label(f, text="Actions", font=("Segoe UI", 10, "bold"),
                  foreground="#89b4fa").grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.action_vars = {}
        action_list = [
            ("skip_inbox", "Skip inbox"),
            ("mark_read",  "Mark as read"),
            ("mark_spam",  "Mark as spam"),
            ("delete",     "Delete (trash)"),
            ("star",       "Star"),
        ]
        for i, (key, label_text) in enumerate(action_list, start=7):
            var = tk.BooleanVar()
            ttk.Checkbutton(f, text=label_text, variable=var).grid(
                row=i, column=0, columnspan=2, sticky="w")
            self.action_vars[key] = var

        # Custom label selector
        ttk.Label(f, text="Apply label:").grid(row=12, column=0, sticky="w", pady=(6, 0))
        self.label_var   = tk.StringVar()
        label_names = sorted(
            n for n in self.labels_map.values()
            if not n.startswith("CATEGORY_")
            and n not in ("INBOX", "SENT", "TRASH", "SPAM", "STARRED", "UNREAD")
        )
        ttk.Combobox(f, textvariable=self.label_var, values=[""] + label_names,
                     state="readonly", width=28).grid(row=12, column=1, sticky="ew", padx=(8, 0))

        # Create / Cancel buttons
        btn_row = ttk.Frame(f)
        btn_row.grid(row=13, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(btn_row, text="Create",  command=self._create,
                   style="Accent.TButton").pack(side="right", padx=2)
        ttk.Button(btn_row, text="Cancel",  command=self.destroy).pack(side="right", padx=2)

    # ── LOGIC ─────────────────────────────────────────────────────────────────

    def _create(self):
        """Validates fields, builds the filter body and sends it to the Gmail API."""
        criteria = {k: v.get().strip() for k, v in self.fields.items() if v.get().strip()}
        if not criteria:
            messagebox.showwarning("Empty criteria", "Please fill in at least one criterion.", parent=self)
            return

        add_labels, remove_labels = [], []
        if self.action_vars["skip_inbox"].get(): remove_labels.append("INBOX")
        if self.action_vars["mark_read"].get():  remove_labels.append("UNREAD")
        if self.action_vars["mark_spam"].get():  add_labels.append("SPAM")
        if self.action_vars["delete"].get():     add_labels.append("TRASH")
        if self.action_vars["star"].get():       add_labels.append("STARRED")
        if self.label_var.get():
            lid = next((k for k, v in self.labels_map.items() if v == self.label_var.get()), None)
            if lid:
                add_labels.append(lid)

        body = {"criteria": criteria, "action": {}}
        if add_labels:    body["action"]["addLabelIds"]    = add_labels
        if remove_labels: body["action"]["removeLabelIds"] = remove_labels

        try:
            self.service.users().settings().filters().create(userId="me", body=body).execute()
            self.destroy()
            self.on_done()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
