# ─── LOCAL CACHE DATABASE ─────────────────────────────────────────────────────
# SQLite database that stores message metadata and body HTML locally.
# Reads are instant; Gmail API is only hit for writes and background sync.

import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "mailbox.db")


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")   # allow concurrent reads during writes
    return c


def init_db():
    """Create tables and indexes. Safe to call on every startup."""
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id            TEXT PRIMARY KEY,
                thread_id     TEXT    NOT NULL DEFAULT '',
                from_addr     TEXT    NOT NULL DEFAULT '',
                subject       TEXT    NOT NULL DEFAULT '',
                date          TEXT    NOT NULL DEFAULT '',
                internal_date INTEGER NOT NULL DEFAULT 0,
                labels        TEXT    NOT NULL DEFAULT '[]',
                unread        INTEGER NOT NULL DEFAULT 0,
                starred       INTEGER NOT NULL DEFAULT 0,
                body_html     TEXT,
                synced_at     TEXT
            )
        """)
        # Migration: add internal_date to existing DBs that don't have it
        try:
            c.execute("ALTER TABLE messages ADD COLUMN internal_date INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass  # column already exists — ignore
        c.execute("""
            CREATE TABLE IF NOT EXISTS sync_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_idate  ON messages(internal_date DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_unread ON messages(unread)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_star   ON messages(starred)")


# ── Metadata (history_id, last_sync, …) ────────────────────────────────────────

def get_meta(key, default=None):
    with _conn() as c:
        row = c.execute("SELECT value FROM sync_meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_meta(key, value):
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO sync_meta(key, value) VALUES(?, ?)",
            (key, str(value)),
        )


# ── Message upsert / delete ────────────────────────────────────────────────────

def upsert_message(m: dict):
    """Insert or update a message row (metadata only, body untouched)."""
    labels = json.dumps(m.get("labels", []))
    with _conn() as c:
        c.execute(
            """
            INSERT INTO messages
                (id, thread_id, from_addr, subject, date, internal_date,
                 labels, unread, starred, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                thread_id     = excluded.thread_id,
                from_addr     = excluded.from_addr,
                subject       = excluded.subject,
                date          = excluded.date,
                internal_date = excluded.internal_date,
                labels        = excluded.labels,
                unread        = excluded.unread,
                starred       = excluded.starred,
                synced_at     = excluded.synced_at
            """,
            (
                m["id"],
                m.get("threadId", ""),
                m.get("from", ""),
                m.get("subject", "(no subject)"),
                m.get("date", ""),
                int(m.get("internalDate", 0)),   # Unix ms — sorts correctly
                labels,
                1 if m.get("unread")   else 0,
                1 if m.get("starred")  else 0,
            ),
        )


def update_labels(mid: str, label_ids: list):
    """Update only the labels / unread / starred columns for one message."""
    with _conn() as c:
        c.execute(
            "UPDATE messages SET labels=?, unread=?, starred=? WHERE id=?",
            (
                json.dumps(label_ids),
                1 if "UNREAD"   in label_ids else 0,
                1 if "STARRED"  in label_ids else 0,
                mid,
            ),
        )


def delete_message(mid: str):
    with _conn() as c:
        c.execute("DELETE FROM messages WHERE id=?", (mid,))


# ── Body cache ─────────────────────────────────────────────────────────────────

def cache_body(mid: str, html: str):
    with _conn() as c:
        c.execute("UPDATE messages SET body_html=? WHERE id=?", (html, mid))


def get_body(mid: str):
    with _conn() as c:
        row = c.execute("SELECT body_html FROM messages WHERE id=?", (mid,)).fetchone()
        return row["body_html"] if row else None


# ── Queries ────────────────────────────────────────────────────────────────────

# Maps Gmail-style folder queries to SQL WHERE clauses.
# Returns None for queries we can't translate (falls back to Gmail API).
_QUERY_MAP = {
    "":                  "1=1",
    "in:inbox":          'labels LIKE \'%"INBOX"%\'',
    "in:sent":           'labels LIKE \'%"SENT"%\'',
    "in:drafts":         'labels LIKE \'%"DRAFT"%\'',
    "in:spam":           'labels LIKE \'%"SPAM"%\'',
    "in:trash":          'labels LIKE \'%"TRASH"%\'',
    "is:starred":        "starred=1",
    "is:unread":         "unread=1",
    "is:unread in:inbox":'unread=1 AND labels LIKE \'%"INBOX"%\'',
    "is:read in:inbox":  'unread=0 AND labels LIKE \'%"INBOX"%\'',
}


def query_messages(gmail_query: str, limit: int = 100):
    """
    Return cached messages matching a Gmail folder query.
    Returns None if the query is too complex for local SQL (caller should hit the API).
    """
    key   = (gmail_query or "").strip().lower()
    where = _QUERY_MAP.get(key)
    if where is None:
        return None   # unsupported → fall back to Gmail API

    with _conn() as c:
        rows = c.execute(
            f"SELECT * FROM messages WHERE {where} ORDER BY internal_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_message_by_id(mid: str):
    with _conn() as c:
        row = c.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        return _row_to_dict(row) if row else None


def count():
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]


# ── Internal ───────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    if row is None:
        return None
    d           = dict(row)
    d["labels"]   = json.loads(d.get("labels", "[]"))
    d["unread"]   = bool(d.get("unread"))
    d["starred"]  = bool(d.get("starred"))
    d["from"]     = d.pop("from_addr",  "")
    d["threadId"] = d.pop("thread_id",  "")
    return d
