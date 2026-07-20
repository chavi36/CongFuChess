# """
# matchmaker.py — pairs waiting clients by closest ELO (mark).
# """

# import threading


# class Matchmaker:
#     def __init__(self):
#         self._lock    = threading.Lock()
#         self._waiting = []   # list of (user_dict, conn, addr)

#     def add(self, user: dict, conn, addr) -> tuple | None:
#         """
#         Add a client to the queue.
#         If a suitable opponent is already waiting, remove them both and
#         return (user_a, conn_a, user_b, conn_b).
#         Otherwise return None.
#         """
#         with self._lock:
#             if self._waiting:
#                 # pick the opponent with the closest mark
#                 best_idx = min(
#                     range(len(self._waiting)),
#                     key=lambda i: abs(self._waiting[i][0]["range"] - user["range"]),
#                 )
#                 opp_user, opp_conn, opp_addr = self._waiting.pop(best_idx)
#                 return opp_user, opp_conn, user, conn
#             else:
#                 self._waiting.append((user, conn, addr))
#                 return None

#     def remove(self, conn) -> None:
#         """Remove a client that disconnected while waiting."""
#         with self._lock:
#             self._waiting = [e for e in self._waiting if e[1] is not conn]



import threading
import time

class Matchmaker:
    def __init__(self):
        self._lock = threading.Lock()
        self._waiting = []

    def add(self, user: dict, conn) -> tuple | None:
        with self._lock:
            now = time.time()
            self._waiting = [e for e in self._waiting if now - e[2] < 60]
            
            best_idx = -1
            for i, (opp, _, _) in enumerate(self._waiting):
                if abs(opp["range"] - user["range"]) <= 100:
                    best_idx = i
                    break
            
            if best_idx != -1:
                opp_user, opp_conn, _ = self._waiting.pop(best_idx)
                return opp_user, opp_conn, user, conn
            
            self._waiting.append((user, conn, now))
            return None