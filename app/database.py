import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from app.config import DB_PATH

DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS site_state (
                site_name TEXT PRIMARY KEY,
                url TEXT,
                last_items_json TEXT,
                last_text_hash TEXT,
                last_checked TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_name TEXT,
                item_title TEXT,
                item_url TEXT,
                summary TEXT,
                detected_at TEXT,
                emailed INTEGER DEFAULT 0
            )
        """)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def get_known_titles(site_name: str):
    """Returns a set() of previously seen item titles for this site, or None if never checked."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT last_items_json FROM site_state WHERE site_name = ?", (site_name,)
        )
        row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        return set(json.loads(row[0]))


def get_last_text_hash(site_name: str):
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT last_text_hash FROM site_state WHERE site_name = ?", (site_name,)
        )
        row = cur.fetchone()
        return row[0] if row else None


def update_site_state(site_name: str, url: str, items: list, text_hash: str):
    titles = [i["title"] for i in items]
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO site_state (site_name, url, last_items_json, last_text_hash, last_checked)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(site_name) DO UPDATE SET
                last_items_json = excluded.last_items_json,
                last_text_hash = excluded.last_text_hash,
                last_checked = excluded.last_checked
        """, (site_name, url, json.dumps(titles), text_hash, datetime.now().isoformat()))
        conn.commit()


def log_alert(site_name: str, item_title: str, item_url: str, summary: str, emailed: bool):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO alerts_log (site_name, item_title, item_url, summary, detected_at, emailed)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (site_name, item_title, item_url, summary, datetime.now().isoformat(), int(emailed)))
        conn.commit()


def get_recent_alerts(limit: int = 50):
    with get_conn() as conn:
        cur = conn.execute("""
            SELECT site_name, item_title, item_url, summary, detected_at, emailed
            FROM alerts_log ORDER BY id DESC LIMIT ?
        """, (limit,))
        cols = ["site_name", "item_title", "item_url", "summary", "detected_at", "emailed"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
