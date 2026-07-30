"""
protocol.py — shared WebSocket messages and transport shim.

Client  -> Server:  LoginMsg, MenuChoiceMsg, ClickMsg, JumpMsg
Server  -> Client:  OkMsg, ErrorMsg, WaitingMsg, MatchedMsg, SnapshotMsg, LeaderboardMsg
"""

from shared.schema.messages import (
    LoginMsg, MenuChoiceMsg, ClickMsg, JumpMsg,
    OkMsg, ErrorMsg, WaitingMsg, MatchedMsg,
    SnapshotMsg, DisconnectedMsg, ReconnectedMsg,
    ForfeitMsg, LeaderboardMsg, GameOverMsg,
    NetworkMsgType,
)
from shared.schema.transport import encode, decode, decode_client_msg
