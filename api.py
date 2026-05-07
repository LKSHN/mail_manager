# ─── GMAIL API BACKEND ────────────────────────────────────────────────────────
# Exposes all Gmail operations to the PyWebView frontend via js_api.
# Every public method returns a JSON-serialisable dict with at least {"ok": bool}.

import os
import json
import base64
import webbrowser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from auth import get_service
from utils import decode_body, get_header
from config import GMAIL_ACCOUNT_INDEX


class GmailAPI:
    """
    API class injected into the WebView as window.pywebview.api.
    JS calls these methods as async functions that return Promises.
    """

    def __init__(self):
        self.service    = None
        self.window     = None   # set by main.py after window creation
        self.messages   = []
        self.labels_map = {}
        self.user_email = ""

    def set_window(self, window):
        self.window = window

    # ── Connection ──────────────────────────────────────────────────────────────

    def connect(self):
        """Authenticates with Gmail and loads initial metadata."""
        try:
            self.service    = get_service()
            profile         = self.service.users().getProfile(userId="me").execute()
            self.user_email = profile.get("emailAddress", "")
            self._load_labels()
            return {"ok": True, "email": self.user_email}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _load_labels(self):
        res = self.service.users().labels().list(userId="me").execute()
        self.labels_map = {l["id"]: l["name"] for l in res.get("labels", [])}

    # ── Messages ────────────────────────────────────────────────────────────────

    def get_messages(self, query="in:inbox", max_results=50):
        """Returns a list of message summaries for the given query."""
        try:
            res = self.service.users().messages().list(
                userId="me", q=query, maxResults=max_results
            ).execute()
            ids = [m["id"] for m in res.get("messages", [])]

            self.messages = []
            for mid in ids:
                msg = self.service.users().messages().get(
                    userId="me", id=mid, format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute()
                headers   = msg.get("payload", {}).get("headers", [])
                label_ids = msg.get("labelIds", [])
                self.messages.append({
                    "id":       mid,
                    "threadId": msg.get("threadId", ""),
                    "from":     get_header(headers, "From"),
                    "subject":  get_header(headers, "Subject") or "(no subject)",
                    "date":     get_header(headers, "Date")[:25],
                    "labels":   label_ids,
                    "unread":   "UNREAD"   in label_ids,
                    "starred":  "STARRED"  in label_ids,
                })
            return {"ok": True, "messages": self.messages}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_message_detail(self, mid):
        """Returns the full content of a single message and marks it as read."""
        try:
            msg       = self.service.users().messages().get(
                userId="me", id=mid, format="full"
            ).execute()
            headers   = msg.get("payload", {}).get("headers", [])
            html_body, _ = decode_body(msg.get("payload", {}))
            label_ids = msg.get("labelIds", [])

            if "UNREAD" in label_ids:
                self.service.users().messages().modify(
                    userId="me", id=mid,
                    body={"removeLabelIds": ["UNREAD"]}
                ).execute()

            return {
                "ok":       True,
                "id":       mid,
                "threadId": msg.get("threadId", ""),
                "from":     get_header(headers, "From"),
                "to":       get_header(headers, "To"),
                "subject":  get_header(headers, "Subject") or "(no subject)",
                "date":     get_header(headers, "Date"),
                "body":     html_body,
                "labels":   label_ids,
                "starred":  "STARRED" in label_ids,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Actions ─────────────────────────────────────────────────────────────────

    def archive(self, mid):
        try:
            self.service.users().messages().modify(
                userId="me", id=mid, body={"removeLabelIds": ["INBOX"]}
            ).execute()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def trash(self, mid):
        try:
            self.service.users().messages().trash(userId="me", id=mid).execute()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def toggle_star(self, mid):
        try:
            msg     = self.service.users().messages().get(
                userId="me", id=mid, format="minimal"
            ).execute()
            starred = "STARRED" in msg.get("labelIds", [])
            body    = {"removeLabelIds": ["STARRED"]} if starred else {"addLabelIds": ["STARRED"]}
            self.service.users().messages().modify(userId="me", id=mid, body=body).execute()
            return {"ok": True, "starred": not starred}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def mark_read(self, mid):
        try:
            self.service.users().messages().modify(
                userId="me", id=mid, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def apply_label(self, mid, label_id):
        try:
            self.service.users().messages().modify(
                userId="me", id=mid, body={"addLabelIds": [label_id]}
            ).execute()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_in_browser(self, thread_id):
        try:
            url = f"https://mail.google.com/mail/u/{GMAIL_ACCOUNT_INDEX}/#all/{thread_id}"
            webbrowser.open(url)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Compose / Send ──────────────────────────────────────────────────────────

    def send_message(self, to, subject, body, thread_id=None):
        try:
            msg            = MIMEMultipart()
            msg["to"]      = to
            msg["subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            raw     = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            payload = {"raw": raw}
            if thread_id:
                payload["threadId"] = thread_id
            self.service.users().messages().send(userId="me", body=payload).execute()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Labels ──────────────────────────────────────────────────────────────────

    def get_labels(self):
        try:
            self._load_labels()
            labels = [
                {"id": k, "name": v}
                for k, v in sorted(self.labels_map.items(), key=lambda x: x[1].lower())
                if not v.startswith("CATEGORY_")
            ]
            return {"ok": True, "labels": labels}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def create_label(self, name):
        try:
            label = self.service.users().labels().create(
                userId="me",
                body={
                    "name": name,
                    "labelListVisibility":   "labelShow",
                    "messageListVisibility": "show",
                }
            ).execute()
            self.labels_map[label["id"]] = label["name"]
            return {"ok": True, "label": {"id": label["id"], "name": label["name"]}}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_label(self, lid):
        try:
            self.service.users().labels().delete(userId="me", id=lid).execute()
            self.labels_map.pop(lid, None)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Filters ─────────────────────────────────────────────────────────────────

    def get_filters(self):
        try:
            res = self.service.users().settings().filters().list(userId="me").execute()
            return {"ok": True, "filters": res.get("filter", [])}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def create_filter(self, data):
        try:
            criteria = {}
            if data.get("from"):    criteria["from"]    = data["from"]
            if data.get("to"):      criteria["to"]      = data["to"]
            if data.get("subject"): criteria["subject"] = data["subject"]
            if data.get("query"):   criteria["query"]   = data["query"]

            add_labels, remove_labels = [], []
            if data.get("skipInbox"): remove_labels.append("INBOX")
            if data.get("markRead"):  remove_labels.append("UNREAD")
            if data.get("markSpam"):  add_labels.append("SPAM")
            if data.get("star"):      add_labels.append("STARRED")
            if data.get("trash"):     add_labels.append("TRASH")
            if data.get("labelId"):   add_labels.append(data["labelId"])

            f = self.service.users().settings().filters().create(
                userId="me",
                body={
                    "criteria": criteria,
                    "action":   {"addLabelIds": add_labels, "removeLabelIds": remove_labels},
                }
            ).execute()
            return {"ok": True, "filter": f}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_filter(self, fid):
        try:
            self.service.users().settings().filters().delete(userId="me", id=fid).execute()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def export_filters(self):
        try:
            res     = self.service.users().settings().filters().list(userId="me").execute()
            filters = res.get("filter", [])
            os.makedirs("exports", exist_ok=True)
            path = os.path.abspath(os.path.join("exports", "filters.json"))
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(filters, fh, indent=2, ensure_ascii=False)
            return {"ok": True, "path": path, "count": len(filters)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Blocked addresses (filter-based) ────────────────────────────────────────

    def get_blocked(self):
        try:
            res     = self.service.users().settings().filters().list(userId="me").execute()
            blocked = []
            for f in res.get("filter", []):
                if "SPAM" in f.get("action", {}).get("addLabelIds", []):
                    addr = f.get("criteria", {}).get("from", "")
                    if addr:
                        blocked.append({"address": addr, "filter_id": f["id"]})
            return {"ok": True, "blocked": blocked}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def block_address(self, address):
        try:
            f = self.service.users().settings().filters().create(
                userId="me",
                body={
                    "criteria": {"from": address},
                    "action":   {"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]},
                }
            ).execute()
            return {"ok": True, "filter_id": f["id"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def unblock_address(self, filter_id):
        try:
            self.service.users().settings().filters().delete(userId="me", id=filter_id).execute()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Bulk cleanup ────────────────────────────────────────────────────────────

    def bulk_preview(self, query):
        """Returns the count of messages matching a query (dry-run)."""
        try:
            res = self.service.users().messages().list(
                userId="me", q=query, maxResults=500
            ).execute()
            return {"ok": True, "count": len(res.get("messages", []))}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def bulk_action(self, query, action):
        """Applies 'archive' or 'trash' to all messages matching the query."""
        try:
            res = self.service.users().messages().list(
                userId="me", q=query, maxResults=500
            ).execute()
            ids = [m["id"] for m in res.get("messages", [])]
            for mid in ids:
                if action == "archive":
                    self.service.users().messages().modify(
                        userId="me", id=mid, body={"removeLabelIds": ["INBOX"]}
                    ).execute()
                elif action == "trash":
                    self.service.users().messages().trash(userId="me", id=mid).execute()
            return {"ok": True, "count": len(ids)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
