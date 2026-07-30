"""
auth/db.py — durable user store and game results.

Uses PostgreSQL when DATABASE_URL env var is set, otherwise falls back to SQLite
for local development.

PostgreSQL:  DATABASE_URL=postgresql://user:pass@host:5432/kungfu_chess
SQLite:      DB_FILENAME from config (default: kungfu_chess.db)
"""

import os
import sqlite3
from dataclasses import dataclass
from Core.model.config import ELO_DEFAULT, ELO_K_FACTOR, ELO_DIVISOR, DB_FILENAME

DATABASE_URL = os.environ.get("DATABASE_URL", "")
_USE_PG = bool(DATABASE_URL)

if _USE_PG:
    import psycopg2
    import psycopg2.extras

DB_PATH = DB_FILENAME


# ── Connection helpers ────────────────────────────────────────────────────────

def _pg_conn():
    return psycopg2.connect(DATABASE_URL)


def _sqlite_conn(path: str):
    return sqlite3.connect(path)


# ── Schema ────────────────────────────────────────────────────────────────────

_PG_INIT = f"""
CREATE TABLE IF NOT EXISTS users (
    id       SERIAL PRIMARY KEY,
    name     TEXT   NOT NULL UNIQUE,
    password TEXT   NOT NULL,
    range    INTEGER NOT NULL DEFAULT {ELO_DEFAULT}
);
CREATE TABLE IF NOT EXISTS game_results (
    game_id     TEXT PRIMARY KEY,
    winner      TEXT,
    loser        TEXT,
    winner_elo  INTEGER,
    loser_elo   INTEGER,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_SQLITE_INIT = f"""
CREATE TABLE IF NOT EXISTS users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    NOT NULL UNIQUE,
    password TEXT    NOT NULL,
    range    INTEGER NOT NULL DEFAULT {ELO_DEFAULT}
);
CREATE TABLE IF NOT EXISTS game_results (
    game_id     TEXT PRIMARY KEY,
    winner      TEXT,
    loser        TEXT,
    winner_elo  INTEGER,
    loser_elo   INTEGER,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@dataclass
class UserRecord:
    id: int
    name: str
    password: str
    range: int


# ── Public API ────────────────────────────────────────────────────────────────

def init_db(path: str = DB_PATH) -> None:
    if _USE_PG:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                for stmt in _PG_INIT.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        cur.execute(stmt)
            conn.commit()
    else:
        with _sqlite_conn(path) as conn:
            for stmt in _SQLITE_INIT.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)
            conn.commit()


def add_user(name: str, password: str, elo: int = ELO_DEFAULT, path: str = DB_PATH) -> None:
    if _USE_PG:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (name, password, range) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (name, password, elo),
                )
            conn.commit()
    else:
        with _sqlite_conn(path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (name, password, range) VALUES (?, ?, ?)",
                (name, password, elo),
            )
            conn.commit()


def get_user(name: str, path: str = DB_PATH) -> UserRecord | None:
    if _USE_PG:
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT id, name, password, range FROM users WHERE name = %s", (name,))
                row = cur.fetchone()
        if row is None:
            return None
        return UserRecord(id=row["id"], name=row["name"], password=row["password"], range=row["range"])
    else:
        with _sqlite_conn(path) as conn:
            cur = conn.execute("SELECT id, name, password, range FROM users WHERE name = ?", (name,))
            row = cur.fetchone()
        return UserRecord(id=row[0], name=row[1], password=row[2], range=row[3]) if row else None


def update_range(name: str, new_range: int, path: str = DB_PATH) -> None:
    if _USE_PG:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET range = %s WHERE name = %s", (new_range, name))
            conn.commit()
    else:
        with _sqlite_conn(path) as conn:
            conn.execute("UPDATE users SET range = ? WHERE name = ?", (new_range, name))
            conn.commit()


def authenticate(name: str, password: str, path: str = DB_PATH) -> UserRecord | None:
    user = get_user(name, path)
    if user is None:
        add_user(name, password, elo=ELO_DEFAULT, path=path)
        return get_user(name, path)
    if user.password != password:
        raise ValueError("invalid credentials")
    return user


def compute_elo(winner_range: int, loser_range: int, k: int = ELO_K_FACTOR):
    expected = 1 / (1 + 10 ** ((loser_range - winner_range) / ELO_DIVISOR))
    delta = int(k * (1 - expected))
    return winner_range + delta, loser_range - delta


def update_after_game(winner_name: str, winner_range: int,
                      loser_name: str, loser_range: int, path: str = DB_PATH) -> None:
    new_winner, new_loser = compute_elo(winner_range, loser_range)
    update_range(winner_name, new_winner, path)
    update_range(loser_name, new_loser, path)


def get_leaderboard(n: int = 10, path: str = DB_PATH) -> list:
    if _USE_PG:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name, range FROM users ORDER BY range DESC LIMIT %s", (n,))
                rows = cur.fetchall()
    else:
        with _sqlite_conn(path) as conn:
            cur = conn.execute("SELECT name, range FROM users ORDER BY range DESC LIMIT ?", (n,))
            rows = cur.fetchall()
    return [(row[0], row[1]) for row in rows]


def write_game_result(game_id: str, winner: str, loser: str, path: str = DB_PATH) -> bool:
    winner_rec = get_user(winner, path)
    loser_rec  = get_user(loser, path)
    if winner_rec is None or loser_rec is None:
        return False
    new_winner_elo, new_loser_elo = compute_elo(winner_rec.range, loser_rec.range)
    if _USE_PG:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO game_results (game_id, winner, loser, winner_elo, loser_elo) "
                    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (game_id, winner, loser, new_winner_elo, new_loser_elo),
                )
                written = cur.rowcount == 1
            conn.commit()
    else:
        with _sqlite_conn(path) as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO game_results (game_id, winner, loser, winner_elo, loser_elo) "
                "VALUES (?, ?, ?, ?, ?)",
                (game_id, winner, loser, new_winner_elo, new_loser_elo),
            )
            written = cur.rowcount == 1
            conn.commit()
    if written:
        update_range(winner, new_winner_elo, path)
        update_range(loser, new_loser_elo, path)
    return written


def get_game_result(game_id: str, path: str = DB_PATH) -> dict | None:
    if _USE_PG:
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT game_id, winner, loser, winner_elo, loser_elo, recorded_at "
                    "FROM game_results WHERE game_id = %s", (game_id,)
                )
                row = cur.fetchone()
        if row is None:
            return None
        return dict(row)
    else:
        with _sqlite_conn(path) as conn:
            cur = conn.execute(
                "SELECT game_id, winner, loser, winner_elo, loser_elo, recorded_at "
                "FROM game_results WHERE game_id = ?", (game_id,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {"game_id": row[0], "winner": row[1], "loser": row[2],
                "winner_elo": row[3], "loser_elo": row[4], "recorded_at": row[5]}


def purge_old_results(days: int = 90, path: str = DB_PATH) -> int:
    if _USE_PG:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM game_results WHERE recorded_at < NOW() - INTERVAL '%s days'",
                    (days,)
                )
                deleted = cur.rowcount
            conn.commit()
        return deleted
    else:
        with _sqlite_conn(path) as conn:
            cur = conn.execute(
                "DELETE FROM game_results WHERE recorded_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            conn.commit()
        return cur.rowcount
