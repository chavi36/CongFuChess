"""
db.py — thin wrapper around kungfu_chess.db.db for the server.
All storage logic lives in kungfu_chess/db/db.py.
"""

# from kungfu_chess.db.db import init_db, get_user, update_range, UserRecord


# def authenticate(name: str, password: str) -> UserRecord | None:
#     """Return UserRecord if credentials match, else None."""
#     user = get_user(name)
#     if user is None or user.password != password:
#         return None
#     return user

from application.server.db.db import init_db, get_user, add_user, update_range, UserRecord

def authenticate(name: str, password: str) -> UserRecord | None:
    """
    Authenticate user:
    - If user does not exist, register them automatically.
    - If user exists, verify that the password matches. Return None if it doesn't.
    """
    user = get_user(name)
    
    if user is None:
        # המשתמש לא קיים כלל במערכת – נרשום אותו אוטומטית
        add_user(name, password, range=1200)
        return get_user(name)
        
    # המשתמש קיים – נבדוק האם הסיסמה תואמת
    if user.password != password:
        return None  # סיסמה שגויה עבור משתמש קיים
        
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
