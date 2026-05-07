# ─── LABELS WINDOW ────────────────────────────────────────────────────────────
# Allows listing, creating and deleting Gmail labels.

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog


class LabelsWindow(tk.Toplevel):
    """
    Gmail label management window.

    Parameters
    ----------
    parent             : parent window (GmailApp)
    service            : authenticated Gmail API service
    labels_map         : mutable dict {label_id: label_name} shared with GmailApp
    on_labels_changed  : callback called after create/delete to update
                         the filter dropdown in GmailApp
    """

    def __init__(self, parent, service, labels_map, on_labels_changed):
        super().__init__(parent)
        self.service           = service
        self.labels_map        = labels_map
        self.on_labels_changed = on_labels_changed

        self.title("Label management")
        self.geometry("440x420")
        self.configure(bg="#1e1e2e")

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        f = ttk.Frame(self, padding=12)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="Existing labels",
                  font=("Segoe UI", 11, "bold"), foreground="#89b4fa").pack(anchor="w")

        # Label list
        self.lb = tk.Listbox(f, bg="#313244", fg="#cdd6f4", selectbackground="#45475a",
                             font=("Segoe UI", 10), relief="flat", height=14)
        self.lb.pack(fill="both", expand=True, pady=6)

        # Action buttons
        btn_frame = ttk.Frame(f)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="➕ Create",  command=self._create,
                   style="Accent.TButton").pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🗑️ Delete",  command=self._delete).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Close",       command=self.destroy).pack(side="right")

        self._refresh_list()

    # ── LOGIC ─────────────────────────────────────────────────────────────────

    def _refresh_list(self):
        """Reloads the listbox from labels_map (excludes system categories)."""
        self.lb.delete(0, "end")
        for lid, name in sorted(self.labels_map.items(), key=lambda x: x[1]):
            if not name.startswith("CATEGORY_"):
                self.lb.insert("end", f"{name}  [{lid}]")

    def _create(self):
        """Prompts for a name and creates a new label via the API."""
        name = simpledialog.askstring("New label", "Label name:", parent=self)
        if not name:
            return
        label = self.service.users().labels().create(
            userId="me",
            body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
        ).execute()
        self.labels_map[label["id"]] = label["name"]
        self._refresh_list()
        self.on_labels_changed()

    def _delete(self):
        """Deletes the selected label after confirmation."""
        sel = self.lb.curselection()
        if not sel:
            return
        text = self.lb.get(sel[0])
        lid  = text.split("[")[-1].rstrip("]")
        name = self.labels_map.get(lid, lid)
        if not messagebox.askyesno("Confirm", f"Delete label '{name}'?", parent=self):
            return
        self.service.users().labels().delete(userId="me", id=lid).execute()
        del self.labels_map[lid]
        self._refresh_list()
        self.on_labels_changed()
