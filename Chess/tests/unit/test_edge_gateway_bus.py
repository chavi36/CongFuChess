from shared.events import InMemoryEventBus, COMMAND_SUBJECT, PLAYER_FRAME_SUBJECT
from services.edge_gateway import get_last_player_frame, publish_command, run_edge_gateway
from services.game_node import run_game_node


def test_edge_gateway_receives_player_frame_from_game_node():
    bus = InMemoryEventBus()
    run_edge_gateway(event_bus=bus)
    run_game_node(event_bus=bus)

    publish_command({"game_id": "g1", "action": "click", "row": 2, "col": 3})

    frame = get_last_player_frame()
    assert frame is not None
    assert frame["game_id"] == "g1"
    assert frame["type"] == "snapshot"
