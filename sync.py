# ─── SYNC MANAGER ─────────────────────────────────────────────────────────────
import json
import threading
import time
from datetime import datetime, timezone

import db
from utils import get_header

SYNC_INTERVAL  = 30     # seconds between automatic background syncs
INITIAL_LABELS = ["INBOX", "SENT", "STARRED"]
FIRST_PAGE     = 100    # messages shown to user immediately (phase 1)
PAGE_SIZE      = 500    # page size for background pagination (phase 2)
PROGRESS_EVERY = 20     # send a progress notification every N messages


class SyncManager:

    def __init__(self):
        self._lock    = threading.RLock()
        self._running = False
        self._thread  = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self, service, window):
        if db.count() == 0:
            threading.Thread(
                target=self._initial_sync, args=(service, window), daemon=True
            ).start()
        else:
            threading.Thread(
                target=self._incremental_sync, args=(service, window), daemon=True
            ).start()
        self._start_auto_loop(service, window)

    def sync_now(self, service, window):
        threading.Thread(
            target=self._incremental_sync, args=(service, window), daemon=True
        ).start()

    def stop(self):
        self._running = False

    # ── Auto-sync loop ─────────────────────────────────────────────────────────

    def _start_auto_loop(self, service, window):
        if self._running:
            return
        self._running = True
        threading.Thread(
            target=self._auto_loop, args=(service, window), daemon=True
        ).start()

    def _auto_loop(self, service, window):
        while self._running:
            time.sleep(SYNC_INTERVAL)
            if self._running:
                self._incremental_sync(service, window)

    # ── Initial sync ───────────────────────────────────────────────────────────

    def _initial_sync(self, service, window):
        """
        Phase 1 — fast: first FIRST_PAGE messages per label → UI populates.
        Phase 2 — deep: paginates everything else in background with progress bar.
        """
        with self._lock:
            try:
                _notify(window, "syncing", {"mode": "full"})

                # Snapshot historyId before fetching so we never miss new mail
                profile    = _api(service.users().getProfile(userId="me"))
                history_id = profile.get("historyId", "")

                seen       = set()
                done       = 0
                next_tokens   = {}   # label → nextPageToken for phase 2
                size_estimates = {}  # label → resultSizeEstimate

                # ── Phase 1: first page ───────────────────────────────────────
                for label in INITIAL_LABELS:
                    res = _api(service.users().messages().list(
                        userId="me", labelIds=[label], maxResults=FIRST_PAGE
                    ))
                    size_estimates[label] = res.get("resultSizeEstimate", 0)
                    for item in res.get("messages", []):
                        mid = item["id"]
                        if mid in seen:
                            continue
                        seen.add(mid)
                        try:
                            _fetch_and_store(service, mid)
                        except Exception:
                            pass
                        done += 1
                    token = res.get("nextPageToken")
                    if token:
                        next_tokens[label] = token

                # Save checkpoint — UI can now show messages
                db.set_meta("history_id", history_id)
                db.set_meta("last_sync",  _now_iso())
                _notify(window, "synced", {"mode": "full", "count": done})

                if not next_tokens:
                    _notify(window, "progress_hide", {})
                    return

                # ── Phase 2: paginate the rest ───────────────────────────────
                total = sum(size_estimates.values())
                _notify(window, "syncing", {"mode": "deep"})
                _notify(window, "progress", {"done": done, "total": total})

                for label, page_token in next_tokens.items():
                    while page_token:
                        res = _api(service.users().messages().list(
                            userId="me", labelIds=[label],
                            maxResults=PAGE_SIZE, pageToken=page_token
                        ))
                        for item in res.get("messages", []):
                            mid = item["id"]
                            if mid in seen:
                                continue
                            seen.add(mid)
                            try:
                                _fetch_and_store(service, mid)
                            except Exception:
                                pass
                            done += 1
                            if done % PROGRESS_EVERY == 0:
                                _notify(window, "progress", {"done": done, "total": total})
                        page_token = res.get("nextPageToken")

                db.set_meta("last_sync", _now_iso())
                _notify(window, "progress", {"done": done, "total": done})  # 100 %
                _notify(window, "synced",   {"mode": "deep", "count": done})

            except Exception as e:
                _notify(window, "sync_error", {"error": str(e)})

    # ── Incremental sync ───────────────────────────────────────────────────────

    def _incremental_sync(self, service, window):
        with self._lock:
            try:
                history_id = db.get_meta("history_id")
                if not history_id:
                    self._initial_sync(service, window)
                    return

                _notify(window, "syncing", {"mode": "incremental"})

                changes        = 0
                page_token     = None
                new_history_id = history_id
                needs_full     = False

                while True:
                    kwargs = {
                        "userId":         "me",
                        "startHistoryId": history_id,
                        "maxResults":     500,
                    }
                    if page_token:
                        kwargs["pageToken"] = page_token

                    try:
                        res = _api(service.users().history().list(**kwargs))
                    except Exception:
                        needs_full = True
                        break

                    new_history_id = res.get("historyId", new_history_id)

                    for record in res.get("history", []):
                        for item in record.get("messagesAdded", []):
                            try:
                                _fetch_and_store(service, item["message"]["id"])
                                changes += 1
                            except Exception:
                                pass

                        for item in record.get("messagesDeleted", []):
                            db.delete_message(item["message"]["id"])
                            changes += 1

                        for item in (record.get("labelsAdded", []) +
                                     record.get("labelsRemoved", [])):
                            db.update_labels(
                                item["message"]["id"],
                                item["message"].get("labelIds", []),
                            )
                            changes += 1

                    page_token = res.get("nextPageToken")
                    if not page_token:
                        break

                if needs_full:
                    self._initial_sync(service, window)
                    return

                db.set_meta("history_id", new_history_id)
                db.set_meta("last_sync",  _now_iso())
                _notify(window, "synced", {"mode": "incremental", "changes": changes})

            except Exception as e:
                _notify(window, "sync_error", {"error": str(e)})


# ── Helpers ────────────────────────────────────────────────────────────────────

def _api(request, num_retries=3):
    return request.execute(num_retries=num_retries)


def _fetch_and_store(service, mid: str):
    msg       = _api(service.users().messages().get(
        userId="me", id=mid, format="metadata",
        metadataHeaders=["From", "Subject", "Date"],
    ))
    headers   = msg.get("payload", {}).get("headers", [])
    label_ids = msg.get("labelIds", [])
    db.upsert_message({
        "id":           mid,
        "threadId":     msg.get("threadId", ""),
        "from":         get_header(headers, "From"),
        "subject":      get_header(headers, "Subject") or "(no subject)",
        "date":         get_header(headers, "Date")[:25],
        "internalDate": int(msg.get("internalDate", 0)),
        "labels":       label_ids,
        "unread":       "UNREAD"  in label_ids,
        "starred":      "STARRED" in label_ids,
    })


def _notify(window, event: str, data: dict = None):
    if not window:
        return
    try:
        window.evaluate_js(f"App.onSyncEvent('{event}', {json.dumps(data or {})})")
    except Exception:
        pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
