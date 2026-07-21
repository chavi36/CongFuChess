# import cv2
# from application.bridge.game_session import GameSession


# class GUIController:
#     def __init__(self, renderer, session: GameSession):
#         self.renderer = renderer
#         self.session  = session
#         self.selected = None  # (row, col) of currently selected cell

#     def get_mouse_callback(self):
#         def on_mouse(event, x, y, flags, param):
#             if event != cv2.EVENT_LBUTTONDOWN:
#                 return
#             row, col = self.renderer.pixel_to_cell(x, y)
#             if not self.renderer.in_bounds(row, col):
#                 return
#             if self.selected == (row, col):
#                 self.session.jump(row, col)
#                 self.selected = None
#             else:
#                 self.session.click(row, col)
#                 if self.selected is None:
#                     self.selected = (row, col)
#                 else:
#                     self.selected = None
#         return on_mouse



# import socket
# import json
# import threading
# import cv2
# from application.server.protocol import encode, decode
# from application.gui.animated_renderer import AnimatedRenderer
# from application.gui.gui_controller import GUIController

# class GameClient:
#     def __init__(self, host='127.0.0.1', port=5555):
#         self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         self.host = host
#         self.port = port
#         self.renderer = None
#         self.controller = None

#     def connect(self):
#         self.sock.connect((self.host, self.port))

#     def login(self, username, password):
#         msg = {"type": "login", "name": username, "password": password}
#         self.sock.sendall(encode(msg))
#         return decode(self.sock.recv(1024))

#     def start_game(self, renderer, controller):
#         self.renderer = renderer
#         self.controller = controller
#         threading.Thread(target=self._receive_loop, daemon=True).start()

#     def _receive_loop(self):
#         while True:
#             try:
#                 data = self.sock.recv(4096)
#                 if not data: break
#                 msg = decode(data)
                
#                 if msg["type"] == "snapshot":
#                     # רינדור הלוח עם המידע שמגיע מהשרת
#                     canvas = self.renderer.render(msg["data"], selected=self.controller.selected)
#                     cv2.imshow("Kungfu Chess", canvas)
#                     cv2.waitKey(1)
#             except:
#                 break

#     def send_action(self, action_type, row=None, col=None):
#         msg = {"type": action_type, "row": row, "col": col}
#         self.sock.sendall(encode(msg))

# def main():
#     # 1. התחברות
#     client = GameClient()
#     client.connect()
    
#     name = input("Username: ")
#     pwd = input("Password: ")
#     res = client.login(name, pwd)
    
#     if res.get("type") == "ok":
#         print("Logged in. Seeking game...")
#         client.send_action("play")
        
#         # 2. אתחול GUI
#         renderer = AnimatedRenderer("board.png", "animations/pieces1", 1300, 900, 700)
#         controller = GUIController(renderer, client)
#         cv2.namedWindow("Kungfu Chess")
#         cv2.setMouseCallback("Kungfu Chess", controller.get_mouse_callback())
        
#         # 3. התחלת לולאת המשחק
#         client.start_game(renderer, controller)
        
#         while cv2.getWindowProperty("Kungfu Chess", cv2.WND_PROP_VISIBLE) >= 1:
#             if cv2.waitKey(30) & 0xFF == 27: break
#     else:
#         print("Login failed.")

# if __name__ == "__main__":
#     main()


import cv2
from application.bridge.game_session import GameSession


class GUIController:
    def __init__(self, renderer, session: GameSession):
        self.renderer = renderer
        self.session  = session
        self.selected = None  # (row, col) of currently selected cell

    def get_mouse_callback(self):
        def on_mouse(event, x, y, flags, param):
            if event != cv2.EVENT_LBUTTONDOWN:
                return
            row, col = self.renderer.pixel_to_cell(x, y)
            if not self.renderer.in_bounds(row, col):
                return
            if self.selected == (row, col):
                if hasattr(self.session, "send_action"):
                    self.session.send_action("jump", row=row, col=col)
                elif hasattr(self.session, "jump"):
                    self.session.jump(row, col)
                self.selected = None
            else:
                if hasattr(self.session, "send_action"):
                    self.session.send_action("click", row=row, col=col)
                elif hasattr(self.session, "click"):
                    self.session.click(row, col)
                if self.selected is None:
                    self.selected = (row, col)
                else:
                    self.selected = None
        return on_mouse