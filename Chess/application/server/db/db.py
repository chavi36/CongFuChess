# import sqlite3

# import os
# DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kungfu_chess.db")


# def get_connection(path: str = DB_PATH) -> sqlite3.Connection:
#     return sqlite3.connect(path)


# def init_db(path: str = DB_PATH) -> None:
#     conn = get_connection(path)
#     conn.execute("""
#         CREATE TABLE IF NOT EXISTS users (
#             id       INTEGER PRIMARY KEY AUTOINCREMENT,
#             name     TEXT    NOT NULL UNIQUE,
#             password TEXT    NOT NULL,
#             range    INTEGER NOT NULL DEFAULT 0
#         )
#     """)
#     conn.commit()
#     conn.close()


# def add_user(name: str, password: str, range: int = 0, path: str = DB_PATH) -> None:
#     conn = get_connection(path)
#     conn.execute(
#         "INSERT INTO users (name, password, range) VALUES (?, ?, ?)",
#         (name, password, range),
#     )
#     conn.commit()
#     conn.close()


# def get_user(name: str, path: str = DB_PATH) -> dict | None:
#     conn = get_connection(path)
#     cur = conn.execute(
#         "SELECT id, name, password, range FROM users WHERE name = ?", (name,)
#     )
#     row = cur.fetchone()
#     conn.close()
#     if row is None:
#         return None
#     return {"id": row[0], "name": row[1], "password": row[2], "range": row[3]}


# def update_range(name: str, new_range: int, path: str = DB_PATH) -> None:
#     conn = get_connection(path)
#     conn.execute("UPDATE users SET range = ? WHERE name = ?", (new_range, name))
#     conn.commit()
#     conn.close()


import sqlite3
from dataclasses import dataclass

DB_PATH = "kungfu_chess.db"


@dataclass
class UserRecord:
    id: int
    name: str
    password: str
    range: int


def get_connection(path: str = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(path)


def init_db(path: str = DB_PATH) -> None:
    conn = get_connection(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL UNIQUE,
            password TEXT    NOT NULL,
            range    INTEGER NOT NULL DEFAULT 1200
        )
    """)
    conn.commit()
    conn.close()


def add_user(name: str, password: str, range: int = 1200, path: str = DB_PATH) -> None:
    conn = get_connection(path)
    conn.execute("INSERT INTO users (name, password, range) VALUES (?, ?, ?)", (name, password, range))
    conn.commit()
    conn.close()


def get_user(name: str, path: str = DB_PATH) -> UserRecord | None:
    conn = get_connection(path)
    cur  = conn.execute("SELECT id, name, password, range FROM users WHERE name = ?", (name,))
    row  = cur.fetchone()
    conn.close()
    return UserRecord(id=row[0], name=row[1], password=row[2], range=row[3]) if row else None


def update_range(name: str, new_range: int, path: str = DB_PATH) -> None:
    conn = get_connection(path)
    conn.execute("UPDATE users SET range = ? WHERE name = ?", (new_range, name))
    conn.commit()
    conn.close()


def authenticate(name: str, password: str) -> UserRecord | None:
    """
    Authenticate user:
    - If user does not exist, register them automatically.
    - If user exists, verify that the password matches. Return None if it doesn't.
    """
    user = get_user(name)
    
    if user is None:
        add_user(name, password, range=1200)
        return get_user(name)
        
    if user.password != password:
        return None 
        
    return user


def compute_elo(winner_range: int, loser_range: int, k: int = 32):
    """Return (new_winner_range, new_loser_range)."""
    expected = 1 / (1 + 10 ** ((loser_range - winner_range) / 400))
    delta = int(k * (1 - expected))
    return winner_range + delta, loser_range - delta


def update_after_game(winner_name: str, winner_range: int,
                      loser_name: str,  loser_range: int) -> None:
    new_winner, new_loser = compute_elo(winner_range, loser_range)
    update_range(winner_name, new_winner)
    update_range(loser_name,  new_loser)