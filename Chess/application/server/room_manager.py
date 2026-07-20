import uuid

class RoomManager:
    def __init__(self):
        self._rooms = {}

    def create_room(self):
        room_id = str(uuid.uuid4())[:8]
        self._rooms[room_id] = {"players": [], "viewers": []}
        return room_id

    def join_room(self, room_id, user_conn):
        if room_id in self._rooms:
            room = self._rooms[room_id]
            if len(room["players"]) < 2:
                room["players"].append(user_conn)
                return "player"
            room["viewers"].append(user_conn)
            return "viewer"
        return None