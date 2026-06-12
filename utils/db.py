import os
import sqlite3
from typing import Optional, Dict
import json
import utils.dynamo as dynamo
from config import config

# When AWS credentials are present every function delegates to dynamo.py
_USE_DYNAMO: bool = bool(
    config.get("AWS_ACCESS_KEY_ID") and config.get("AWS_SECRET_ACCESS_KEY")
)

ROOT = os.path.dirname(os.path.dirname(__file__))
DB_DIR = os.path.join(ROOT, 'database')
DB_PATH = os.path.join(DB_DIR, 'warera_users.db')


def _connect():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables / confirm they exist.  Uses DynamoDB when credentials are present."""
    if _USE_DYNAMO:
        try:
            created = dynamo.ensure_tables()
            if created:
                print("DynamoDB tables confirmed/created for WarEraBot.")
        except Exception as e:
            print(f"DynamoDB ensure_tables failed: {e}")
        return
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_username TEXT,
                display_name TEXT,
                api_id TEXT UNIQUE,
                discord_id TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_discord_username ON users(discord_username)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_display_name ON users(display_name)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_discord_id ON users(discord_id)")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS diplomacies (
                country_name TEXT PRIMARY KEY,
                status TEXT,
                description TEXT,
                diplomacy TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_diplomacies_status ON diplomacies(status)")
        conn.commit()


def save_user(discord_username: str | None, display_name: str | None, api_id: str, discord_id: int | str | None = None) -> None:
    """Insert or update a user mapping."""
    if _USE_DYNAMO:
        return dynamo.save_user(discord_username, display_name, api_id, discord_id)
    if api_id is None:
        return
    discord_id_str = str(discord_id) if discord_id is not None else None
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (discord_username, display_name, api_id, discord_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(api_id) DO UPDATE SET
                discord_username=excluded.discord_username,
                display_name=excluded.display_name,
                discord_id=excluded.discord_id
            """,
            (discord_username, display_name, api_id, discord_id_str),
        )
        conn.commit()


def find_api_id_by_discord_id(discord_id: int | str) -> Optional[str]:
    if _USE_DYNAMO:
        return dynamo.find_api_id_by_discord_id(discord_id)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT api_id FROM users WHERE discord_id = ? LIMIT 1", (str(discord_id),))
        row = cur.fetchone()
        return row['api_id'] if row else None


def find_api_id_by_display_name(display_name: str) -> Optional[str]:
    if _USE_DYNAMO:
        return dynamo.find_api_id_by_display_name(display_name)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT api_id FROM users WHERE display_name = ? LIMIT 1", (display_name,))
        row = cur.fetchone()
        return row['api_id'] if row else None


def find_api_id_by_discord_username(discord_username: str) -> Optional[str]:
    if _USE_DYNAMO:
        return dynamo.find_api_id_by_discord_username(discord_username)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT api_id FROM users WHERE discord_username = ? LIMIT 1", (discord_username,))
        row = cur.fetchone()
        return row['api_id'] if row else None


def get_record_by_api_id(api_id: str) -> Optional[Dict]:
    if _USE_DYNAMO:
        return dynamo.get_record_by_api_id(api_id)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT discord_username, display_name, api_id, discord_id FROM users WHERE api_id = ? LIMIT 1", (api_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_all_diplomacies() -> Dict[str, Dict]:
    """Return a mapping of country_name -> record dict for all diplomacies."""
    if _USE_DYNAMO:
        return dynamo.get_all_diplomacies()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT country_name, status, description, diplomacy FROM diplomacies")
        rows = cur.fetchall()
        out: Dict[str, Dict] = {}
        for r in rows:
            diplomacy = r['diplomacy']
            try:
                entries = json.loads(diplomacy) if diplomacy else []
            except Exception:
                entries = []
            out[r['country_name']] = {
                'status': r['status'],
                'description': r['description'],
                'diplomacy': entries,
            }
        return out


def get_diplomacy(country_name: str) -> Optional[Dict]:
    if _USE_DYNAMO:
        return dynamo.get_diplomacy(country_name)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT country_name, status, description, diplomacy FROM diplomacies WHERE country_name = ? LIMIT 1", (country_name,))
        row = cur.fetchone()
        if not row:
            return None
        try:
            entries = json.loads(row['diplomacy']) if row['diplomacy'] else []
        except Exception:
            entries = []
        return {'country_name': row['country_name'], 'status': row['status'], 'description': row['description'], 'diplomacy': entries}


def update_diplomacy(country_name: str, status: str | None = None, description: str | None = None) -> None:
    """Insert or update a diplomacy record for a country."""
    if _USE_DYNAMO:
        return dynamo.update_diplomacy(country_name, status, description)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO diplomacies (country_name, status, description, diplomacy) VALUES (?, ?, ?, ?)", (country_name, None, None, json.dumps([])))
        if status is not None and description is not None:
            cur.execute("UPDATE diplomacies SET status = ?, description = ? WHERE country_name = ?", (status, description, country_name))
        elif status is not None:
            cur.execute("UPDATE diplomacies SET status = ? WHERE country_name = ?", (status, country_name))
        elif description is not None:
            cur.execute("UPDATE diplomacies SET description = ? WHERE country_name = ?", (description, country_name))
        conn.commit()


def add_diplomacy_entry(country_name: str, info: str, entry_date: str) -> None:
    entry = {"text": info, "date": entry_date}
    if _USE_DYNAMO:
        return dynamo.add_diplomacy_entry(country_name, info, entry_date)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, description, diplomacy FROM diplomacies WHERE country_name = ? LIMIT 1", (country_name,))
        row = cur.fetchone()
        status_val = None
        desc_val = None
        diplomacy_json = None
        if row:
            try:
                diplomacy_json = row['diplomacy']
            except Exception:
                try:
                    diplomacy_json = row[2]
                except Exception:
                    diplomacy_json = None
            try:
                status_val = row['status']
            except Exception:
                try:
                    status_val = row[0]
                except Exception:
                    status_val = None
            try:
                desc_val = row['description']
            except Exception:
                try:
                    desc_val = row[1]
                except Exception:
                    desc_val = None

        if diplomacy_json:
            try:
                entries = json.loads(diplomacy_json)
            except Exception:
                entries = []
        else:
            entries = []

        entries.append(entry)
        cur.execute("INSERT OR REPLACE INTO diplomacies (country_name, status, description, diplomacy) VALUES (?, ?, ?, ?)", (country_name, status_val, desc_val, json.dumps(entries)))
        conn.commit()


def remove_diplomacy_entry(country_name: str, position: int) -> bool:
    """Remove entry at 1-based position from diplomacy list. Returns True if removed."""
    if _USE_DYNAMO:
        return dynamo.remove_diplomacy_entry(country_name, position)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, description, diplomacy FROM diplomacies WHERE country_name = ? LIMIT 1", (country_name,))
        row = cur.fetchone()
        if not row:
            return False

        diplomacy_json = None
        try:
            diplomacy_json = row['diplomacy']
        except Exception:
            try:
                diplomacy_json = row[2]
            except Exception:
                diplomacy_json = None

        if not diplomacy_json:
            return False

        try:
            entries = json.loads(diplomacy_json)
        except Exception:
            entries = []

        idx = position - 1
        if idx < 0 or idx >= len(entries):
            return False
        entries.pop(idx)

        try:
            status_val = row['status']
        except Exception:
            try:
                status_val = row[0]
            except Exception:
                status_val = None
        try:
            desc_val = row['description']
        except Exception:
            try:
                desc_val = row[1]
            except Exception:
                desc_val = None

        cur.execute("INSERT OR REPLACE INTO diplomacies (country_name, status, description, diplomacy) VALUES (?, ?, ?, ?)", (country_name, status_val, desc_val, json.dumps(entries)))
        conn.commit()
        return True


def delete_diplomacy(country_name: str) -> bool:
    """Delete the diplomacy record for a country. Returns True if a row was deleted."""
    if _USE_DYNAMO:
        return dynamo.delete_diplomacy(country_name)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM diplomacies WHERE country_name = ?", (country_name,))
        deleted = cur.rowcount
        conn.commit()
        return deleted > 0
