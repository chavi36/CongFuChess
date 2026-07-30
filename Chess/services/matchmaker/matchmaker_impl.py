import threading
import time
from Core.model.config import MATCHMAKING_STALE_TIMEOUT_S

_BAND_BASE    = 100
_BAND_STEP    = 50
_BAND_STEP_S  = 5.0
_BAND_CAP     = 400


def _band(wait_s: float) -> int:
    """Widening band: starts at ±100, grows by 50 every 5 s, capped at ±400."""
    steps = int(wait_s / _BAND_STEP_S)
    return min(_BAND_BASE + steps * _BAND_STEP, _BAND_CAP)


class Matchmaker:
    def __init__(self):
        self._lock    = threading.Lock()
        self._waiting = []  # (user, ws, enqueued_at)

    def register(self, user, ws) -> None:
        with self._lock:
            if not any(e[1] is ws for e in self._waiting):
                self._waiting.append((user, ws, time.time()))

    def unregister(self, ws) -> None:
        with self._lock:
            self._waiting = [e for e in self._waiting if e[1] is not ws]

    def all_waiting_ws(self) -> list:
        with self._lock:
            return [e[1] for e in self._waiting]

    def poll(self, ws) -> tuple | None:
        """
        Try to match the player identified by ws.
        Uses widening rating bands. Evicts stale entries.
        Returns (user_a, ws_a, user_b, ws_b) if matched, else None.
        """
        with self._lock:
            now = time.time()
            self._waiting = [e for e in self._waiting
                             if now - e[2] < MATCHMAKING_STALE_TIMEOUT_S]

            my_idx = next((i for i, e in enumerate(self._waiting) if e[1] is ws), None)
            if my_idx is None:
                return None

            my_user, _, my_ts = self._waiting[my_idx]
            my_band = _band(now - my_ts)
            my_range = my_user["range"] if isinstance(my_user, dict) else my_user.range

            for i, (opp_user, opp_ws, opp_ts) in enumerate(self._waiting):
                if i == my_idx:
                    continue
                opp_range = opp_user["range"] if isinstance(opp_user, dict) else opp_user.range
                opp_band  = _band(now - opp_ts)
                tolerance = min(my_band, opp_band)
                if abs(opp_range - my_range) <= tolerance:
                    for idx in sorted([my_idx, i], reverse=True):
                        self._waiting.pop(idx)
                    return my_user, ws, opp_user, opp_ws

            return None
