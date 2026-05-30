import os
import sqlite3
from typing import Optional, Dict
import json
import os
import utils.dynamo as dynamo

ROOT = os.path.dirname(os.path.dirname(__file__))
DB_DIR = os.path.join(ROOT, 'database')
DB_PATH = os.path.join(DB_DIR, 'warera_users.db')


def _connect():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the users table and indexes if they don't exist."""
    # If AWS credentials are provided, create DynamoDB tables and skip sqlite init.
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        try:
            # created = dynamo.ensure_tables()
            created = False
            if created:
                print("Initialized DynamoDB tables for WarEraBot.")
            else:
                print("AWS credentials present but DynamoDB tables not created.")
            return
        except Exception as e:
            # if Dynamo fails, fall back to sqlite initialization and warn
            print(f"DynamoDB init failed, falling back to sqlite: {e}")
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
        # diplomacy table: one row per country, store status, description and a JSON array for diplomacy entries
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
    """Insert or update a user mapping.

    Keeps the latest discord/display names for a given `api_id`.
    """
    if api_id is None:
        return
    discord_id_str = str(discord_id) if discord_id is not None else None
    with _connect() as conn:
        cur = conn.cursor()
        # Use UPSERT semantics on api_id (unique)
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
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT api_id FROM users WHERE discord_id = ? LIMIT 1", (str(discord_id),))
        row = cur.fetchone()
        return row['api_id'] if row else None


def find_api_id_by_display_name(display_name: str) -> Optional[str]:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT api_id FROM users WHERE display_name = ? LIMIT 1", (display_name,))
        row = cur.fetchone()
        return row['api_id'] if row else None


def find_api_id_by_discord_username(discord_username: str) -> Optional[str]:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT api_id FROM users WHERE discord_username = ? LIMIT 1", (discord_username,))
        row = cur.fetchone()
        return row['api_id'] if row else None


def get_record_by_api_id(api_id: str) -> Optional[Dict]:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT discord_username, display_name, api_id, discord_id FROM users WHERE api_id = ? LIMIT 1", (api_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_all_diplomacies() -> Dict[str, Dict]:
    """Return a mapping of country_name -> record dict for all diplomacies."""
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
    with _connect() as conn:
        cur = conn.cursor()
        # Ensure row exists
        cur.execute("INSERT OR IGNORE INTO diplomacies (country_name, status, description, diplomacy) VALUES (?, ?, ?, ?)", (country_name, None, None, json.dumps([])))
        # Update provided fields
        if status is not None and description is not None:
            cur.execute("UPDATE diplomacies SET status = ?, description = ? WHERE country_name = ?", (status, description, country_name))
        elif status is not None:
            cur.execute("UPDATE diplomacies SET status = ? WHERE country_name = ?", (status, country_name))
        elif description is not None:
            cur.execute("UPDATE diplomacies SET description = ? WHERE country_name = ?", (description, country_name))
        conn.commit()


def add_diplomacy_entry(country_name: str, info: str) -> None:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, description, diplomacy FROM diplomacies WHERE country_name = ? LIMIT 1", (country_name,))
        row = cur.fetchone()
        status_val = None
        desc_val = None
        diplomacy_json = None
        if row:
            # handle sqlite3.Row or tuple
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

        entries.append(info)
        cur.execute("INSERT OR REPLACE INTO diplomacies (country_name, status, description, diplomacy) VALUES (?, ?, ?, ?)", (country_name, status_val, desc_val, json.dumps(entries)))
        conn.commit()


def remove_diplomacy_entry(country_name: str, position: int) -> bool:
    """Remove entry at 1-based position from diplomacy list. Returns True if removed."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, description, diplomacy FROM diplomacies WHERE country_name = ? LIMIT 1", (country_name,))
        row = cur.fetchone()
        if not row:
            return False

        # extract diplomacy JSON robustly
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

        # preserve status/description
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
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM diplomacies WHERE country_name = ?", (country_name,))
        deleted = cur.rowcount
        conn.commit()
        return deleted > 0
