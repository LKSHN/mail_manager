# ─── GMAIL API BACKEND ────────────────────────────────────────────────────────
# Exposes all Gmail operations to the PyWebView frontend via js_api.
#
# Read path  → local SQLite DB (instant)
# Write path → Gmail API, then update DB so the cache stays consistent
# Sync       → handled by SyncManager (sync.py) in background threads

import os
import json
import base64
import webbrowser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import db
from sync import SyncManager
from auth import get_service
from utils import decode_body, get_header
from config import GMAIL_ACCOUNT_INDEX


class GmailAPI:
    """
    API class injected into the WebView as window.pywebview.api.
    Every public method returns a JSON-serialisable dict with at least {"ok": bool}.
    """

    def __init__(self):
        self.service      = None
        self.window       = None
        self.labels_map   = {}
        self.user_email   = ""
        self.sync_manager = SyncManager()

    def set_window(self, window):
        self.window = window

    # ── Connection ──────────────────────────────────────────────────────────────

    def connect(self):
        """Authenticates with Gmail, loads labels, kicks off background sync."""
        try:
            self.service    = get_service()
            profile         = self.service.users().getProfile(userId="me").execute()
            self.user_email = profile.get("emailAddress", "")
            self._load_labels()
            # Start background sync (incremental if DB has data, full if empty)
            self.sync_manager.start(self.service, self.window)
            return {"ok": True, "email": self.user_email}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _load_labels(self):
        res = self.service.users().labels().list(userId="me").execute()
        self.labels_map = {l["id"]: l["name"] for l in res.get("labels", [])}

    # ── Messages ────────────────────────────────────────────────────────────────

    def get_messages(self, query="in:inbox", max_results=100):
        """
        Reads from the local DB for standard folder queries (instant).
        Falls back to the Gmail API for free-text search or unsupported queries.
        """
        cached = db.query_messages(query, limit=max_results)
        if cached is not None:
            return {"ok": True, "messages": cached, "source": "cache"}

        # Complex / search query → hit the API
        try:
            res = self.service.users().messages().list(
                userId="me", q=query, maxResults=max_results
            ).execute()
            ids  = [m["id"] for m in res.get("messages", [])]
            msgs = []
            for mid in ids:
                msg       = self.service.users().messages().get(
                    userId="me", id=mid, format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()
                headers   = msg.get("payload", {}).get("headers", [])
                label_ids = msg.get("labelIds", [])
                entry = {
                    "id":           mid,
                    "threadId":     msg.get("threadId", ""),
                    "from":         get_header(headers, "From"),
                    "subject":      get_header(headers, "Subject") or "(no subject)",
                    "date":         get_header(headers, "Date")[:25],
                    "internalDate": int(msg.get("internalDate", 0)),
                    "labels":       label_ids,
                    "unread":       "UNREAD"  in label_ids,
                    "starred":      "STARRED" in label_ids,
                }
                msgs.append(entry)
                db.upsert_message(entry)   # cache search results too
            return {"ok": True, "messages": msgs, "source": "api"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_message_detail(self, mid):
        """
        Returns the full message detail.
        Body HTML is cached in the DB after the first fetch.
        """
        meta      = db.get_message_by_id(mid)
        body_html = db.get_body(mid)

        if meta and body_html:
            # Fully cached — no API call needed
            if meta.get("unread"):
                # Optimistically mark as read in DB; API call below will confirm
                db.update_labels(mid, [l for l in meta["labels"] if l != "UNREAD"])
                try:
                    self.service.users().messages().modify(
                        userId="me", id=mid, body={"removeLabelIds": ["UNREAD"]}
                    ).execute()
                except Exception:
                    pass
            return {
                "ok":       True,
                "id":       mid,
                "threadId": meta["threadId"],
                "from":     meta["from"],
                "to":       "",
                "subject":  meta["subject"],
                "date":     meta["date"],
                "body":     body_html,
                "labels":   meta["labels"],
                "starred":  meta["starred"],
                "source":   "cache",
            }

        # Body not cached yet → fetch full message from API
        try:
            msg       = self.service.users().messages().get(
                userId="me", id=mid, format="full"
            ).execute()
            headers   = msg.get("payload", {}).get("headers", [])
            html_body, _ = decode_body(msg.get("payload", {}))
            label_ids = msg.get("labelIds", [])

            # Cache body and update labels
            db.cache_body(mid, html_body)
            db.update_labels(mid, label_ids)

            # Mark as read
            if "UNREAD" in label_ids:
                self.service.users().messages().modify(
                    userId="me", id=mid, body={"removeLabelIds": ["UNREAD"]}
                ).execute()
                db.update_labels(mid, [l for l in label_ids if l != "UNREAD"])

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
                "source":   "api",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Sync ────────────────────────────────────────────────────────────────────

    def sync_now(self):
        """Manually trigger an incremental sync."""
        try:
            self.sync_manager.sync_now(self.service, self.window)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_sync_status(self):
        """Return last sync timestamp and total cached message count."""
        return {
            "ok":            True,
            "last_sync":     db.get_meta("last_sync", ""),
            "message_count": db.count(),
        }

    # ── Actions ─────────────────────────────────────────────────────────────────
    # Each action updates the DB immediately so the UI stays consistent,
    # then calls the Gmail API in the background.

    def archive(self, mid):
        try:
            db.update_labels(mid, [
                l for l in (db.get_message_by_id(mid) or {}).get("labels", [])
                if l != "INBOX"
            ])
            self.service.users().messages().modify(
                userId="me", id=mid, body={"removeLabelIds": ["INBOX"]}
            ).execute()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def trash(self, mid):
        try:
            db.delete_message(mid)
            self.service.users().messages().trash(userId="me", id=mid).execute()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def toggle_star(self, mid):
        try:
            meta    = db.get_message_by_id(mid) or {}
            starred = meta.get("starred", False)
            if starred:
                new_labels = [l for l in meta.get("labels", []) if l != "STARRED"]
                body = {"removeLabelIds": ["STARRED"]}
            else:
                new_labels = meta.get("labels", []) + ["STARRED"]
                body = {"addLabelIds": ["STARRED"]}
            db.update_labels(mid, new_labels)
            self.service.users().messages().modify(userId="me", id=mid, body=body).execute()
            return {"ok": True, "starred": not starred}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def mark_read(self, mid):
        try:
            meta = db.get_message_by_id(mid) or {}
            db.update_labels(mid, [l for l in meta.get("labels", []) if l != "UNREAD"])
            self.service.users().messages().modify(
                userId="me", id=mid, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def apply_label(self, mid, label_id):
        try:
            meta = db.get_message_by_id(mid) or {}
            db.update_labels(mid, list(set(meta.get("labels", []) + [label_id])))
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
                },
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
                },
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
            res = self.service.users().settings().filters().list(userId="me").execute()
            blocked = [
                {"address": f.get("criteria", {}).get("from", ""), "filter_id": f["id"]}
                for f in res.get("filter", [])
                if "SPAM" in f.get("action", {}).get("addLabelIds", [])
                and f.get("criteria", {}).get("from")
            ]
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
                },
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
        try:
            res = self.service.users().messages().list(
                userId="me", q=query, maxResults=500
            ).execute()
            return {"ok": True, "count": len(res.get("messages", []))}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def bulk_action(self, query, action):
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
                    meta = db.get_message_by_id(mid)
                    if meta:
                        db.update_labels(mid, [l for l in meta["labels"] if l != "INBOX"])
                elif action == "trash":
                    self.service.users().messages().trash(userId="me", id=mid).execute()
                    db.delete_message(mid)
            return {"ok": True, "count": len(ids)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
