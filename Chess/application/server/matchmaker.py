import threading
import time
from Core.model.config import MATCHMAKING_RANGE_TOLERANCE, MATCHMAKING_STALE_TIMEOUT_S


class Matchmaker:
    def __init__(self):
        self._lock    = threading.Lock()
        self._waiting = []  # (user, ws, timestamp)

    def register(self, user, ws) -> None:
        """Add a player to the waiting queue."""
        with self._lock:
            self._waiting.append((user, ws, time.time()))

    def poll(self, ws) -> tuple | None:
        """
        Check if the player identified by ws has been matched.
        Returns (user_a, ws_a, user_b, ws_b) if matched, else None.
        Also evicts stale entries older than MATCHMAKING_STALE_TIMEOUT_S.
        """
        with self._lock:
            now = time.time()
            self._waiting = [e for e in self._waiting if now - e[2] < MATCHMAKING_STALE_TIMEOUT_S]

            my_idx = next((i for i, e in enumerate(self._waiting) if e[1] is ws), None)
            if my_idx is None:
                return None

            my_user = self._waiting[my_idx][0]

            for i, (opp_user, opp_ws, _) in enumerate(self._waiting):
                if i == my_idx:
                    continue
                if abs(opp_user.range - my_user.range) <= MATCHMAKING_RANGE_TOLERANCE:
                    for idx in sorted([my_idx, i], reverse=True):
                        self._waiting.pop(idx)
                    return my_user, ws, opp_user, opp_ws

            return None
