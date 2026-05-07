# ─── MIXIN: MESSAGE DETAIL ────────────────────────────────────────────────────
# Selection, full content fetching, display, browser and local file opening.

import html
import os
import threading
import webbrowser
from tkinter import messagebox, filedialog

from config import GMAIL_ACCOUNT_INDEX
from utils  import decode_body, get_header


class MailDetailMixin:
    """Handles displaying message content and related actions."""

    # ── SELECTION ─────────────────────────────────────────────────────────────

    def _on_select(self, event):
        """Triggered on selection: loads the message detail in a background thread."""
        sel = self.tree.selection()
        if not sel:
            return
        threading.Thread(target=self._fetch_detail, args=(sel[0],), daemon=True).start()

    # ── FETCHING FROM THE API ─────────────────────────────────────────────────

    def _fetch_detail(self, mid):
        """
        Fetches the full message content and passes it to _show_detail.
        Marks the message as read if it was unread.
        """
        try:
            msg     = self.service.users().messages().get(userId="me", id=mid, format="full").execute()
            headers = msg["payload"]["headers"]
            frm     = get_header(headers, "From")
            subj    = get_header(headers, "Subject")
            date    = get_header(headers, "Date")
            body, _ = decode_body(msg["payload"])
            meta    = f"From: {frm}\nDate: {date}\nSubject: {subj}"

            self.after(0, lambda: self._show_detail(mid, meta, body))

            if "UNREAD" in msg.get("labelIds", []):
                self.service.users().messages().modify(
                    userId="me", id=mid, body={"removeLabelIds": ["UNREAD"]}
                ).execute()
                self.after(0, self._refresh)
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._show_detail(None, "Error", err))

    # ── DISPLAY ───────────────────────────────────────────────────────────────

    def _show_detail(self, mid, meta, html_body):
        """Displays metadata and the HTML body in the right panel."""
        self.current_mid = mid
        msg_data = next((m for m in self.messages if m["id"] == mid), None)
        self.current_thread_id = msg_data["threadId"] if msg_data else None
        self.detail_meta.config(text=meta)
        self.detail_text.load_html(html_body)

    # ── OPEN IN BROWSER ───────────────────────────────────────────────────────

    def _open_in_browser(self):
        """Opens the currently displayed message in Gmail via the default browser."""
        if not self.current_thread_id:
            return
        url = f"https://mail.google.com/mail/u/{GMAIL_ACCOUNT_INDEX}/#all/{self.current_thread_id}"
        webbrowser.open(url)

    # ── LOCAL FILE ────────────────────────────────────────────────────────────

    def _open_local_file(self):
        """
        Opens a local email file (.eml, .html, .txt) and displays it in the detail panel.
        Automatically detects whether the content is HTML or plain text.
        """
        path = filedialog.askopenfilename(
            title="Open an email file",
            filetypes=[("Email files", "*.txt *.html *.htm *.eml"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if content.lstrip().startswith("<") or "<html" in content[:200].lower():
                html_body = content
            else:
                html_body = f"<pre style='font-family:sans-serif;white-space:pre-wrap'>{html.escape(content)}</pre>"
            self._show_detail(None, f"Local file: {os.path.basename(path)}", html_body)
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
