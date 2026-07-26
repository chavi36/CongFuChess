# import uuid

# class RoomManager:
#     def __init__(self):
#         self._rooms = {}

#     def create_room(self):
#         room_id = str(uuid.uuid4())[:8]
#         self._rooms[room_id] = {"players": [], "viewers": []}
#         return room_id

#     def join_room(self, room_id, user_conn):
#         if room_id in self._rooms:
#             room = self._rooms[room_id]
#             if len(room["players"]) < 2:
#                 room["players"].append(user_conn)
#                 return "player"
#             room["viewers"].append(user_conn)
#             return "viewer"
#         return None

import asyncio
import uuid
from typing import Optional, Dict, List, Tuple

class Room:
    def __init__(self, room_id: str, password: str, creator_conn):
        self.room_id = room_id
        self.password = password
        self.players: List = [creator_conn]
        self.viewers: List = []
        self.users: dict = {}
        self.ready = asyncio.Event()  # fired when 2 players have joined

    def is_empty(self) -> bool:
        return len(self.players) == 0 and len(self.viewers) == 0


class RoomManager:
    def __init__(self):
        self._rooms: Dict[str, Room] = {}

    def create_room(self, password: str, creator_conn) -> str:
        """יוצר חדר חדש עם סיסמה ומחזיר את ה-room_id הייחודי."""
        room_id = str(uuid.uuid4())[:8]
        self._rooms[room_id] = Room(room_id, password, creator_conn)
        return room_id

    def join_room(self, room_id: str, password: str, user_conn) -> Tuple[Optional[str], str]:
        """
        מנסה להצטרף לחדר קיים בהינתן סיסמה נכונה.
        מחזיר טאפל: (תפקיד - 'player' או 'viewer', הודעת טקסט)
        """
        if room_id not in self._rooms:
            return None, "החדר אינו קיים"
        
        room = self._rooms[room_id]
        if room.password != password:
            return None, "סיסמה שגויה"
        
        # אם יש פחות מ-2 שחקנים, מצטרף כשחקן פעיל
        if len(room.players) < 2:
            room.players.append(user_conn)
            return "player", "התחברת לשחקן בהצלחה"
        
        # אם החדר מלא בשחקנים, מצטרף כצופה
        room.viewers.append(user_conn)
        return "viewer", "החדר מלא, התחברת כצופה (ללא יכולת להזיז כלים)"

    def remove_player(self, user_conn) -> Optional[str]:
        """
        מסיר שחקן או צופה מהחדר שבו הוא נמצא.
        אם החדר נותר ריק לחלוטין משחקנים וצופים - הוא נמחק אוטומטית מהשרת.
        מחזיר את ה-room_id אם החדר נמחק, או None אחרת.
        """
        for room_id, room in list(self._rooms.items()):
            if user_conn in room.players:
                room.players.remove(user_conn)
                if room.is_empty():
                    del self._rooms[room_id]
                    return room_id
                break
            elif user_conn in room.viewers:
                room.viewers.remove(user_conn)
                if room.is_empty():
                    del self._rooms[room_id]
                    return room_id
                break
        return None