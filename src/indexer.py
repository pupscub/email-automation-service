import sqlite3
from typing import List, Dict, Any
from datetime import datetime
import threading

from src.config import config


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  sender TEXT,
  subject TEXT,
  body_preview TEXT,
  received_utc TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender);
CREATE INDEX IF NOT EXISTS idx_messages_received ON messages(received_utc);
"""


class MailIndexer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)

    def upsert_messages(self, items: List[Dict[str, Any]]):
        rows = []
        for m in items:
            rows.append((
                m.get("id"),
                (m.get("from", {}).get("emailAddress", {}) or {}).get("address", ""),
                m.get("subject", ""),
                m.get("bodyPreview", "") or (m.get("body", {}) or {}).get("content", ""),
                m.get("receivedDateTime", "")
            ))
        if not rows:
            return
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO messages(id, sender, subject, body_preview, received_utc) VALUES (?,?,?,?,?)",
                rows
            )

    def search_lexical(self, query: str, sender: str | None = None, top_k: int = 10) -> List[Dict[str, Any]]:
        q = f"%{query.lower()}%"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if sender:
                cur = conn.execute(
                    "SELECT * FROM messages WHERE (lower(subject) LIKE ? OR lower(body_preview) LIKE ?) AND lower(sender)=? ORDER BY received_utc DESC LIMIT ?",
                    (q, q, sender.lower(), top_k)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM messages WHERE lower(subject) LIKE ? OR lower(body_preview) LIKE ? ORDER BY received_utc DESC LIMIT ?",
                    (q, q, top_k)
                )
            return [dict(r) for r in cur.fetchall()]


mail_indexer = MailIndexer(config.index_path)


