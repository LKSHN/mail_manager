# ─── BULK CLEANUP WINDOW ──────────────────────────────────────────────────────
# Allows archiving or deleting groups of messages in a single action.

import threading
import tkinter as tk
from tkinter import ttk, messagebox


class CleanupWindow(tk.Toplevel):
    """
    Bulk cleanup window.

    Features:
      - Archive/delete all emails from a given sender.
      - Archive/delete by keyword in the subject.
      - Quick actions: empty promotions, empty spam, archive all read.

    Parameters
    ----------
    parent      : parent window (GmailApp)
    service     : authenticated Gmail API service
    on_done     : callback called after each action to refresh the main list
    """

    def __init__(self, parent, service, on_done):
        super().__init__(parent)
        self.service = service
        self.on_done = on_done

        self.title("Bulk cleanup")
        self.geometry("480x380")
        self.configure(bg="#1e1e2e")

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="🧹 Bulk cleanup",
                  font=("Segoe UI", 12, "bold"), foreground="#89b4fa").pack(anchor="w", pady=(0, 12))

        # ── By sender ─────────────────────────────────────────────────────────
        ttk.Label(f, text="Delete/archive all emails from a sender:").pack(anchor="w")
        sender_frame = ttk.Frame(f)
        sender_frame.pack(fill="x", pady=4)
        self.sender_var = tk.StringVar()
        ttk.Entry(sender_frame, textvariable=self.sender_var, width=32).pack(side="left", padx=(0, 6))
        ttk.Button(sender_frame, text="Archive",
                   command=lambda: self._by_sender("archive")).pack(side="left", padx=2)
        ttk.Button(sender_frame, text="Delete",
                   command=lambda: self._by_sender("trash")).pack(side="left", padx=2)

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=12)

        # ── By keyword in subject ─────────────────────────────────────────────
        ttk.Label(f, text="Delete/archive by keyword in subject:").pack(anchor="w")
        kw_frame = ttk.Frame(f)
        kw_frame.pack(fill="x", pady=4)
        self.kw_var = tk.StringVar()
        ttk.Entry(kw_frame, textvariable=self.kw_var, width=32).pack(side="left", padx=(0, 6))
        ttk.Button(kw_frame, text="Archive",
                   command=lambda: self._by_keyword("archive")).pack(side="left", padx=2)
        ttk.Button(kw_frame, text="Delete",
                   command=lambda: self._by_keyword("trash")).pack(side="left", padx=2)

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=12)

        # ── Quick actions ─────────────────────────────────────────────────────
        ttk.Label(f, text="Quick actions:").pack(anchor="w")
        quick = ttk.Frame(f)
        quick.pack(fill="x", pady=4)
        ttk.Button(quick, text="🗑️ Empty Promotions",
                   command=lambda: self._bulk_action("category:promotions", "trash")).pack(side="left", padx=2)
        ttk.Button(quick, text="🗑️ Empty Spam",
                   command=lambda: self._bulk_action("in:spam", "trash")).pack(side="left", padx=2)
        ttk.Button(quick, text="📦 Archive all read",
                   command=lambda: self._bulk_action("is:read in:inbox", "archive")).pack(side="left", padx=2)

        ttk.Button(f, text="Close", command=self.destroy).pack(anchor="e", pady=(16, 0))

    # ── LOGIC ─────────────────────────────────────────────────────────────────

    def _by_sender(self, action):
        """Runs an action on all messages from the entered sender."""
        addr = self.sender_var.get().strip()
        if not addr:
            messagebox.showwarning("Empty field", "Please enter an email address.", parent=self)
            return
        self._bulk_action(f"from:{addr}", action)

    def _by_keyword(self, action):
        """Runs an action on all messages whose subject contains the entered keyword."""
        kw = self.kw_var.get().strip()
        if not kw:
            return
        self._bulk_action(f"subject:{kw}", action)

    def _bulk_action(self, query, action):
        """
        Fetches up to 500 messages matching `query`,
        asks for confirmation, then applies `action` in a background thread.
        `action` is either "archive" (removes INBOX) or "trash" (moves to trash).
        """
        try:
            res = self.service.users().messages().list(userId="me", q=query, maxResults=500).execute()
            ids = [m["id"] for m in res.get("messages", [])]
            if not ids:
                messagebox.showinfo("Cleanup", "No messages found.", parent=self)
                return
            if not messagebox.askyesno("Confirm",
                                       f"{len(ids)} messages found.\nAction: {action}. Continue?",
                                       parent=self):
                return

            def do():
                for mid in ids:
                    if action == "archive":
                        self.service.users().messages().modify(
                            userId="me", id=mid,
                            body={"removeLabelIds": ["INBOX"]}
                        ).execute()
                    elif action == "trash":
                        self.service.users().messages().trash(userId="me", id=mid).execute()
                self.on_done()
                self.after(0, lambda: messagebox.showinfo(
                    "Done", f"{len(ids)} messages processed.", parent=self))

            threading.Thread(target=do, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
