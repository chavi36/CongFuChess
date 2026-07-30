"""Auth service package for Kung-Fu Chess."""

from .db import (
    UserRecord,
    authenticate,
    init_db,
    get_leaderboard,
    add_user,
    get_user,
    update_range,
    compute_elo,
    update_after_game,
    write_game_result,
    get_game_result,
)

__all__ = [
    "UserRecord",
    "authenticate",
    "init_db",
    "get_leaderboard",
    "add_user",
    "get_user",
    "update_range",
    "compute_elo",
    "update_after_game",
    "write_game_result",
    "get_game_result",
]
