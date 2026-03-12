"""
Rotation Algorithm
==================

The QOTD system rotates USERS, not questions. Each user can have multiple
queued questions. The bot posts one question per day from the next user
in the rotation.

Rotation is a circular queue (round-robin):

    Bob -> Joe -> Amy

When Bob's question is posted, he moves to the back:

    Joe -> Amy -> Bob

New User Priority Rule:
    If a user is not in the rotation and submits a question, they go to
    the FRONT — unless they were recently removed and a full rotation
    hasn't completed yet.

    Example (brand-new user):
        Before: Bob -> Joe -> Amy
        Pip (never been in rotation) submits.
        After:  Pip -> Bob -> Joe -> Amy

    Example (returning user, full rotation passed):
        Gia was removed. Since then, every user who was in the queue at
        that time has had a turn. Gia submits again.
        Before: Toad -> Lia
        After:  Gia -> Toad -> Lia   (front — full cycle passed)

    Example (returning user, full rotation NOT passed):
        Gia's question was posted, she ran out, was removed.
        Toad is next but hasn't posted yet.
        Gia submits again.
        Before: Toad -> Lia
        After:  Toad -> Lia -> Gia   (back — cycle not complete)

Cleanup:
    After posting, if a user has no remaining unposted submissions,
    they are removed from the rotation entirely.
"""

from database import models


def ensure_in_rotation(guild_id: int, user_id: int):
    """Add user to rotation if they aren't already in it.

    Brand-new users go to the front.
    Returning users go to the front only if a full rotation has passed
    since they were last removed. Otherwise they go to the back.
    """
    if models.user_in_rotation(guild_id, user_id):
        return

    if models.should_insert_at_back(guild_id, user_id):
        models.insert_at_back(guild_id, user_id)
    else:
        models.insert_at_front(guild_id, user_id)

    models.clear_removal_record(guild_id, user_id)


def advance_rotation(guild_id: int, user_id: int):
    """After posting a user's question, move them to back or remove them."""
    remaining = models.get_unposted_count(guild_id, user_id)
    if remaining == 0:
        models.remove_from_rotation(guild_id, user_id)
    else:
        models.move_to_back(guild_id, user_id)
