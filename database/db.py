import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "qotd.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            question_text TEXT,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            posted INTEGER DEFAULT 0,
            posted_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS rotation_order (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            qotd_channel_id INTEGER
        );

        -- Tracks users removed from rotation so we know whether a full
        -- cycle has passed before they resubmit.
        -- gate_user_id = who was at the back of the rotation when removed.
        -- Once that gate user has a question posted, a full rotation has
        -- passed and the removed user is eligible for front-of-queue again.
        CREATE TABLE IF NOT EXISTS removed_users (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            gate_user_id INTEGER,
            removed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, user_id)
        );
    """)
    # Migrate: add posted_at column if missing (for existing databases)
    cursor = conn.execute("PRAGMA table_info(submissions)")
    columns = [row[1] for row in cursor.fetchall()]
    if "posted_at" not in columns:
        conn.execute("ALTER TABLE submissions ADD COLUMN posted_at TIMESTAMP")

    conn.commit()
    conn.close()
