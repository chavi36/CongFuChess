import sqlite3

DB_PATH = "kungfu_chess.db"

def init_db(path: str = DB_PATH) -> None:
    conn = sqlite3.connect(path)
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
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO users (name, password, range) VALUES (?, ?, ?)", (name, password, range))
    conn.commit()
    conn.close()

# get_user ו-update_range נשארים כפי שהיו בקוד המקורי שלך