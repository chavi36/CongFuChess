"""
protocol.py — newline-delimited JSON messages shared by server and client.

Client  -> Server:  login, click, jump
Server  -> Client:  ok, error, waiting, matched, snapshot, game_over
"""

import json


def encode(msg: dict) -> bytes:
    return (json.dumps(msg) + "\n").encode()


def decode(line: bytes) -> dict:
    return json.loads(line.decode().strip())
