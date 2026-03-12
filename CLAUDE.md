# Claude Development Guide

This repository contains a Discord bot that manages a **Question of the Day (QOTD)** system.

Claude should follow the architectural rules below when modifying or generating code.

---

# Core Technology

Language: Python

Discord library: discord.py

Database: SQLite

The bot connects to Discord using the **gateway websocket model**, not an HTTP interaction endpoint.

No public API endpoints should be introduced unless explicitly requested.

---

# Key Concept

The QOTD system rotates **users**, not questions.

Each user can submit multiple questions.

The bot posts one question per day from the next user in the rotation.

---

# Rotation Rules

The rotation is a circular queue.

Example:

Bob → Joe → Amy

When Bob's question posts:

Joe → Amy → Bob

---

## New User Priority Rule

If a user submits a question and is **not already in the rotation**, they should be inserted at the **front of the queue**.

Example:

Current rotation:

Bob → Joe → Amy

Pip submits a question.

New rotation:

Pip → Bob → Joe → Amy

After Pip's question posts:

Bob → Joe → Amy → Pip

---

# Database Design

SQLite database file:

qotd.db

Tables:

## submissions

Stores user-submitted questions.

Fields:

id
guild_id
user_id
question_text
image_url
created_at

---

## rotation_order

Maintains the current user rotation.

Fields:

guild_id
user_id
position

Rotation is scoped per guild.

---

## guild_settings

Stores configuration per server.

Fields:

guild_id
qotd_channel_id

---

# Posting Logic

Daily scheduled task:

1. determine next user in rotation
2. fetch their oldest unposted submission
3. post it to the configured QOTD channel
4. remove or mark the submission as posted
5. move the user to the end of the rotation
6. if the user has no remaining questions, remove them from rotation

---

# Submission Types

Two types of submissions:

1. Text question
2. Image question

Image submissions should be stored using the Discord CDN URL.

---

# Message Formatting

Text submission format:

**Month Day, Year**

<Question text>

*Submitted by <@user_id>*

---

Image submission format:

Message 1:

**Month Day, Year**

(image attachment)

Message 2:

*Submitted by <@user_id>*

---

# Command Requirements

User commands:

/qotd_submit
/qotd_queue

Admin commands:

/qotd_add
/qotd_next

Responses to user submissions should be **ephemeral**.

---

# Security Requirements

Claude must ensure:

- Bot token is loaded from environment variables
- No secrets are hardcoded
- Commands only function within the configured guild if the bot is private

---

# Development Goals

Code should prioritize:

- simplicity
- readability
- reliability
- minimal dependencies

The bot should remain lightweight enough to run on a Raspberry Pi.

Avoid unnecessary frameworks or microservices.

---

# Important Constraints

Do NOT introduce:

- external APIs
- HTTP interaction endpoints
- complex ORMs
- large frameworks

Use simple Python modules and SQLite queries.

This project should remain small and maintainable.