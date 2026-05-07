# ─── MIXIN: MESSAGE LIST ──────────────────────────────────────────────────────
# API connection, label loading, message fetching and display.

import threading
from tkinter import messagebox

from auth  import get_service
from utils import get_header


class MailListMixin:
    """Handles Gmail connection, labels and the message list."""

    # ── CONNECTION & LABELS ───────────────────────────────────────────────────

    def _connect(self):
        """Starts the Gmail API connection in a background thread."""
        def task():
            try:
                self.service    = get_service()
                profile         = self.service.users().getProfile(userId="me").execute()
                self.user_email = profile.get("emailAddress", "")
                self._load_labels()
                self.status_var.set("✅ Connected")
                self._refresh()
            except Exception as e:
                self.status_var.set("❌ Connection error")
                messagebox.showerror("Connection", str(e))
        threading.Thread(target=task, daemon=True).start()

    def _load_labels(self):
        """Fetches all labels and updates the filter dropdown."""
        res = self.service.users().labels().list(userId="me").execute()
        self.labels_map = {l["id"]: l["name"] for l in res.get("labels", [])}
        system = ["INBOX", "SENT", "STARRED", "SPAM", "TRASH"]
        custom = sorted(n for n in self.labels_map.values()
                        if n not in system and not n.startswith("CATEGORY_"))
        self.after(0, lambda: self.filter_combo.configure(values=system + custom))

    # ── REFRESH & SEARCH ──────────────────────────────────────────────────────

    def _refresh(self):
        """Reloads the message list according to the active filter."""
        self.status_var.set("⏳ Loading...")
        threading.Thread(target=self._fetch_messages, daemon=True).start()

    def _search(self):
        """Runs a search with the entered query."""
        self.status_var.set("🔍 Searching...")
        threading.Thread(target=self._fetch_messages, args=(self.search_var.get(),), daemon=True).start()

    # ── FETCHING FROM THE API ─────────────────────────────────────────────────

    def _fetch_messages(self, query=""):
        """
        Fetches up to 50 messages from the API.
        Filters by label (normal mode) or by search query.
        """
        try:
            label  = self.filter_var.get()
            params = {"userId": "me", "maxResults": 50}
            if query:
                params["q"] = query
            else:
                params["labelIds"] = [label]

            res = self.service.users().messages().list(**params).execute()
            ids = [m["id"] for m in res.get("messages", [])]
            self.messages = []

            for mid in ids:
                msg = self.service.users().messages().get(
                    userId="me", id=mid, format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute()
                headers = msg["payload"]["headers"]
                self.messages.append({
                    "id":       mid,
                    "threadId": msg.get("threadId", ""),
                    "from":     get_header(headers, "From"),
                    "subject":  get_header(headers, "Subject"),
                    "date":     get_header(headers, "Date")[:25],
                    "labels":   msg.get("labelIds", []),
                })

            self.after(0, self._populate_tree)
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self.status_var.set(f"❌ {err}"))

    # ── TREEVIEW DISPLAY ──────────────────────────────────────────────────────

    def _populate_tree(self):
        """Populates the Treeview. Unread messages appear in bold blue."""
        self.tree.delete(*self.tree.get_children())
        for m in self.messages:
            tag = "unread" if "UNREAD" in m["labels"] else ""
            self.tree.insert("", "end", iid=m["id"],
                             values=(m["from"], m["subject"], m["date"]), tags=(tag,))
        self.tree.tag_configure("unread", foreground="#89b4fa", font=("Segoe UI", 10, "bold"))
        self.status_var.set(f"✅ {len(self.messages)} messages")
