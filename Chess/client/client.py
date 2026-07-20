import asyncio
import threading
import cv2
import websockets
from application.server.protocol import encode, decode
from application.gui.gui_controller import GUIController
from application.gui.animated_renderer import AnimatedRenderer

HOST = "127.0.0.1"
PORT = 5555


class GameClient:
    def __init__(self, host=HOST, port=PORT):
        self.uri        = f"ws://{host}:{port}"
        self.ws         = None
        self.renderer   = None
        self.controller = None
        self._loop      = asyncio.new_event_loop()
        self._snapshot  = None
        self._lock      = threading.Lock()

    # ── connection ────────────────────────────────────────────────────

    def connect(self):
        """Open the WebSocket connection (blocking)."""
        self.ws = self._loop.run_until_complete(
            websockets.connect(self.uri)
        )

    def login(self, username: str, password: str) -> dict:
        return self._loop.run_until_complete(self._login(username, password))

    async def _login(self, username: str, password: str) -> dict:
        await self.ws.send(encode({"type": "login", "name": username, "password": password}))
        return decode(await self.ws.recv())

    # ── actions ───────────────────────────────────────────────────────

    def send_action(self, action_type: str, row=None, col=None):
        msg = {"type": action_type}
        if row is not None:
            msg["row"] = row
        if col is not None:
            msg["col"] = col
        asyncio.run_coroutine_threadsafe(self.ws.send(encode(msg)), self._loop)

    # ── receive loop ──────────────────────────────────────────────────

    def start_receive_loop(self):
        threading.Thread(target=self._run_loop, daemon=True).start()

    def _run_loop(self):
        self._loop.run_until_complete(self._receive_loop())

    async def _receive_loop(self):
        try:
            async for raw in self.ws:
                msg = decode(raw)
                if msg.get("type") == "snapshot":
                    with self._lock:
                        self._snapshot = msg
        except Exception:
            pass

    def get_snapshot(self) -> dict | None:
        with self._lock:
            return self._snapshot


def main():
    client = GameClient()
    client.connect()

    name = input("Username: ")
    pwd  = input("Password: ")
    resp = client.login(name, pwd)

    if resp.get("type") != "ok":
        print(f"Login failed: {resp.get('reason')}")
        return

    print("Waiting for opponent...")
    client.start_receive_loop()

    renderer   = AnimatedRenderer("board.png", "anotations/pieces3", 1300, 900, 700)
    controller = GUIController(renderer, client)

    cv2.namedWindow("Kungfu Chess")
    cv2.setMouseCallback("Kungfu Chess", controller.get_mouse_callback())

    while True:
        snap = client.get_snapshot()
        if snap:
            canvas = renderer.render_snapshot(snap, selected=controller.selected)
            cv2.imshow("Kungfu Chess", canvas)
        if cv2.waitKey(30) & 0xFF == 27:
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
