from typing import Dict, List, Optional

from database.db import get_connection


# ── Submissions ──────────────────────────────────────────────────────────────

def add_submission(guild_id: int, user_id: int, question_text: Optional[str], image_url: Optional[str]) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO submissions (guild_id, user_id, question_text, image_url) VALUES (?, ?, ?, ?)",
        (guild_id, user_id, question_text, image_url),
    )
    submission_id = cur.lastrowid
    conn.commit()
    conn.close()
    return submission_id


def get_oldest_unposted(guild_id: int, user_id: int) -> Optional[Dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM submissions WHERE guild_id = ? AND user_id = ? AND posted = 0 ORDER BY created_at ASC LIMIT 1",
        (guild_id, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_posted(submission_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE submissions SET posted = 1, posted_at = CURRENT_TIMESTAMP WHERE id = ?",
        (submission_id,),
    )
    conn.commit()
    conn.close()


def get_unposted_count(guild_id: int, user_id: int) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM submissions WHERE guild_id = ? AND user_id = ? AND posted = 0",
        (guild_id, user_id),
    ).fetchone()
    conn.close()
    return row["cnt"]


def should_insert_at_back(guild_id: int, user_id: int) -> bool:
    """Check if a returning user should go to the back instead of the front.

    A user goes to the BACK if they were recently removed and a full rotation
    has NOT yet completed since their removal. We track this by recording who
    was at the back of the queue when the user was removed (the "gate user").
    Once that gate user has had a question posted, a full rotation has passed
    and the returning user is eligible for the front again.

    Users with no removal record (brand-new) always go to the front.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT gate_user_id, removed_at FROM removed_users WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    conn.close()

    if not row:
        # Never been in rotation before — brand new user, goes to front
        return False

    gate_user_id = row["gate_user_id"]
    removed_at = row["removed_at"]

    if gate_user_id is None:
        # Rotation was empty when they were removed — full cycle trivially passed
        return False

    # Check if the gate user has had a question posted since removal
    conn = get_connection()
    posted = conn.execute(
        "SELECT 1 FROM submissions WHERE guild_id = ? AND user_id = ? AND posted = 1 AND posted_at >= ? LIMIT 1",
        (guild_id, gate_user_id, removed_at),
    ).fetchone()
    conn.close()

    # If gate user has posted since removal, full rotation passed → front is OK
    # If not, rotation hasn't completed → must go to back
    return posted is None


def record_removal(guild_id: int, user_id: int):
    """Record that a user was removed from rotation, and who was at the back."""
    conn = get_connection()
    # Find who is currently at the back of the rotation (highest position),
    # excluding the user being removed
    back_row = conn.execute(
        "SELECT user_id FROM rotation_order WHERE guild_id = ? AND user_id != ? ORDER BY position DESC LIMIT 1",
        (guild_id, user_id),
    ).fetchone()
    gate_user_id = back_row["user_id"] if back_row else None

    conn.execute(
        "INSERT INTO removed_users (guild_id, user_id, gate_user_id) VALUES (?, ?, ?) "
        "ON CONFLICT(guild_id, user_id) DO UPDATE SET gate_user_id = excluded.gate_user_id, removed_at = CURRENT_TIMESTAMP",
        (guild_id, user_id, gate_user_id),
    )
    conn.commit()
    conn.close()


def clear_removal_record(guild_id: int, user_id: int):
    """Clear the removal record when a user re-enters rotation."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM removed_users WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    conn.commit()
    conn.close()


def get_user_submissions(guild_id: int, user_id: int) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM submissions WHERE guild_id = ? AND user_id = ? ORDER BY posted ASC, created_at ASC",
        (guild_id, user_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_queue_preview(guild_id: int, limit: int = 10) -> List[Dict]:
    """Get the next submissions in rotation order for queue preview."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT s.id, s.user_id, s.question_text, s.image_url, s.created_at, r.position
        FROM rotation_order r
        JOIN submissions s ON s.guild_id = r.guild_id AND s.user_id = r.user_id AND s.posted = 0
        WHERE r.guild_id = ?
        ORDER BY r.position ASC, s.created_at ASC
        """,
        (guild_id,),
    ).fetchall()
    conn.close()

    # Pick the oldest unposted submission per user, in rotation order
    seen_users = set()
    result = []
    for row in rows:
        uid = row["user_id"]
        if uid not in seen_users:
            seen_users.add(uid)
            result.append(dict(row))
            if len(result) >= limit:
                break
    return result


def get_submission_by_id(submission_id: int) -> Optional[Dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_submission(submission_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def prioritize_submission(guild_id: int, submission_id: int) -> bool:
    """Move a submission's owner to the front of the rotation so it posts next."""
    sub = get_submission_by_id(submission_id)
    if not sub or sub["posted"]:
        return False
    user_id = sub["user_id"]

    conn = get_connection()
    # Remove user from current position if they're in rotation
    conn.execute(
        "DELETE FROM rotation_order WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    # Re-normalize remaining positions
    rows = conn.execute(
        "SELECT user_id FROM rotation_order WHERE guild_id = ? ORDER BY position ASC",
        (guild_id,),
    ).fetchall()
    for i, row in enumerate(rows):
        conn.execute(
            "UPDATE rotation_order SET position = ? WHERE guild_id = ? AND user_id = ?",
            (i + 1, guild_id, row["user_id"]),
        )
    # Insert at front (position 0)
    conn.execute(
        "INSERT INTO rotation_order (guild_id, user_id, position) VALUES (?, ?, 0)",
        (guild_id, user_id),
    )
    conn.commit()
    conn.close()
    return True


def get_top_contributors(guild_id: int, limit: int = 10) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT user_id, COUNT(*) as total,
               SUM(CASE WHEN posted = 1 THEN 1 ELSE 0 END) as posted_count
        FROM submissions
        WHERE guild_id = ?
        GROUP BY user_id
        ORDER BY total DESC
        LIMIT ?
        """,
        (guild_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Rotation ─────────────────────────────────────────────────────────────────

def get_rotation(guild_id: int) -> List[Dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM rotation_order WHERE guild_id = ? ORDER BY position ASC",
        (guild_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def user_in_rotation(guild_id: int, user_id: int) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM rotation_order WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()
    conn.close()
    return row is not None


def insert_at_back(guild_id: int, user_id: int):
    """Insert a returning user at the end of the rotation."""
    conn = get_connection()
    max_pos = conn.execute(
        "SELECT COALESCE(MAX(position), -1) as max_pos FROM rotation_order WHERE guild_id = ?",
        (guild_id,),
    ).fetchone()["max_pos"]
    conn.execute(
        "INSERT INTO rotation_order (guild_id, user_id, position) VALUES (?, ?, ?)",
        (guild_id, user_id, max_pos + 1),
    )
    conn.commit()
    conn.close()


def insert_at_front(guild_id: int, user_id: int):
    """Insert a new user at position 0 and shift everyone else down."""
    conn = get_connection()
    conn.execute(
        "UPDATE rotation_order SET position = position + 1 WHERE guild_id = ?",
        (guild_id,),
    )
    conn.execute(
        "INSERT INTO rotation_order (guild_id, user_id, position) VALUES (?, ?, 0)",
        (guild_id, user_id),
    )
    conn.commit()
    conn.close()


def move_to_back(guild_id: int, user_id: int):
    """Move a user from position 0 to the end of the rotation."""
    conn = get_connection()
    max_row = conn.execute(
        "SELECT MAX(position) as max_pos FROM rotation_order WHERE guild_id = ?",
        (guild_id,),
    ).fetchone()
    max_pos = max_row["max_pos"] if max_row["max_pos"] is not None else -1

    conn.execute(
        "DELETE FROM rotation_order WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    # Shift remaining positions so front is always 0
    conn.execute(
        "UPDATE rotation_order SET position = position - 1 WHERE guild_id = ?",
        (guild_id,),
    )
    # Re-count to get actual new max
    new_max = conn.execute(
        "SELECT COALESCE(MAX(position), -1) as max_pos FROM rotation_order WHERE guild_id = ?",
        (guild_id,),
    ).fetchone()["max_pos"]

    conn.execute(
        "INSERT INTO rotation_order (guild_id, user_id, position) VALUES (?, ?, ?)",
        (guild_id, user_id, new_max + 1),
    )
    conn.commit()
    conn.close()


def remove_from_rotation(guild_id: int, user_id: int):
    record_removal(guild_id, user_id)
    conn = get_connection()
    conn.execute(
        "DELETE FROM rotation_order WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    # Re-normalize positions
    rows = conn.execute(
        "SELECT user_id FROM rotation_order WHERE guild_id = ? ORDER BY position ASC",
        (guild_id,),
    ).fetchall()
    for i, row in enumerate(rows):
        conn.execute(
            "UPDATE rotation_order SET position = ? WHERE guild_id = ? AND user_id = ?",
            (i, guild_id, row["user_id"]),
        )
    conn.commit()
    conn.close()


# ── Guild Settings ───────────────────────────────────────────────────────────

def get_channel_id(guild_id: int) -> Optional[int]:
    conn = get_connection()
    row = conn.execute(
        "SELECT qotd_channel_id FROM guild_settings WHERE guild_id = ?",
        (guild_id,),
    ).fetchone()
    conn.close()
    return row["qotd_channel_id"] if row else None


def cleanup_old_posted(days: int = 7) -> int:
    """Delete posted submissions older than the given number of days.
    Returns the number of rows deleted.
    """
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM submissions WHERE posted = 1 AND posted_at <= datetime('now', ? || ' days')",
        (str(-days),),
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def set_channel_id(guild_id: int, channel_id: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO guild_settings (guild_id, qotd_channel_id) VALUES (?, ?) "
        "ON CONFLICT(guild_id) DO UPDATE SET qotd_channel_id = excluded.qotd_channel_id",
        (guild_id, channel_id),
    )
    conn.commit()
    conn.close()
