"""Durable storage for the Rihla Trip Store (services/travel_api.py): saved trips survive a restart.

Off unless TRAVEL_DB_PATH names a SQLite file (created on first use, with its folder). Off, the Trip Store keeps
everything in memory exactly as before, which the eval runner and the tests rely on (a fresh store per run).

What is kept: every saved trip record as the store holds it (itinerary with its own status fields such as
rihla_save, dates, costs, owner traveller_id, created_at), the idempotency keys (a retried approval after a
restart still saves nothing twice), the next trip number (ids are never reused), and traveller preferences
that were saved through the API. The seed data (services/data) is not copied: it is loaded from its files.

SQLite (Python's standard library, no server, no extra dependency) in WAL mode. Each write is one transaction,
made under the Trip Store's own lock. See docs/trip_store_persistence.md.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1
_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trips (
    trip_id TEXT PRIMARY KEY,
    traveller_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    record TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS trips_by_traveller ON trips (traveller_id COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, digest TEXT NOT NULL, response TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS travellers (traveller_id TEXT PRIMARY KEY, record TEXT NOT NULL);
"""


def db_path() -> Path | None:
    """The configured database file, or None (persistence off)."""
    value = os.getenv("TRAVEL_DB_PATH", "").strip()
    return Path(value).expanduser().resolve() if value else None


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(_SCHEMA)
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    if row is None:
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        conn.commit()
    elif int(row[0]) > SCHEMA_VERSION:
        conn.close()
        raise RuntimeError(f"{path} was written by a newer Trip Store (schema {row[0]}); refusing to use it.")
    return conn


def load() -> dict | None:
    """Everything stored, or None when persistence is off:
    {trips: [record, ...] oldest first, idempotency: {key: {digest, response}}, travellers: {id: record},
     next_trip: int | None}."""
    path = db_path()
    if path is None:
        return None
    with _connect(path) as conn:
        trips = [json.loads(r) for (r,) in conn.execute("SELECT record FROM trips ORDER BY created_at, trip_id")]
        idempotency = {k: {"digest": d, "response": json.loads(r)}
                       for k, d, r in conn.execute("SELECT key, digest, response FROM idempotency")}
        travellers = {t: json.loads(r) for t, r in conn.execute("SELECT traveller_id, record FROM travellers")}
        row = conn.execute("SELECT value FROM meta WHERE key = 'next_trip'").fetchone()
    conn.close()
    return {"trips": trips, "idempotency": idempotency, "travellers": travellers,
            "next_trip": int(row[0]) if row else None}


def save_trip(record: dict, next_trip: int, idempotency_key: str | None, idempotency: dict | None) -> None:
    """Store one new trip, the next trip number and its idempotency entry, in one transaction."""
    path = db_path()
    if path is None:
        return
    with _connect(path) as conn:
        conn.execute("INSERT INTO trips (trip_id, traveller_id, created_at, record) VALUES (?, ?, ?, ?)",
                     (record["trip_id"], record["traveller_id"], record["created_at"],
                      json.dumps(record, ensure_ascii=False)))
        conn.execute("INSERT INTO meta (key, value) VALUES ('next_trip', ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (str(next_trip),))
        if idempotency_key and idempotency is not None:
            conn.execute("INSERT OR REPLACE INTO idempotency (key, digest, response) VALUES (?, ?, ?)",
                         (idempotency_key, idempotency["digest"],
                          json.dumps(idempotency["response"], ensure_ascii=False)))
    conn.close()


def save_traveller(record: dict) -> None:
    """Store a traveller's record (their saved preferences)."""
    path = db_path()
    if path is None:
        return
    with _connect(path) as conn:
        conn.execute("INSERT OR REPLACE INTO travellers (traveller_id, record) VALUES (?, ?)",
                     (record["traveller_id"], json.dumps(record, ensure_ascii=False)))
    conn.close()


def clear() -> None:
    """Erase everything stored (the TEST-ONLY POST /admin/reset)."""
    path = db_path()
    if path is None:
        return
    with _connect(path) as conn:
        conn.execute("DELETE FROM trips")
        conn.execute("DELETE FROM idempotency")
        conn.execute("DELETE FROM travellers")
        conn.execute("DELETE FROM meta WHERE key = 'next_trip'")
    conn.close()
