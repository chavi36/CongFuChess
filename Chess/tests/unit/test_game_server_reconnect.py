from services.game_node.game_server import _collect_ws_targets


class DummySocket:
    pass


def test_collect_ws_targets_uses_live_sockets_only():
    white = DummySocket()
    black = DummySocket()
    viewer = DummySocket()

    ws_slots = {"white": white, "black": None}
    targets = _collect_ws_targets(ws_slots, [black, None, viewer])

    assert targets == [white, black, viewer]
