from shared.events import InMemoryEventBus, COMMAND_SUBJECT, PLAYER_FRAME_SUBJECT
from services.edge_gateway import run_edge_gateway
from services.game_node import run_game_node


def test_edge_gateway_and_game_node_share_event_bus():
    bus = InMemoryEventBus()
    run_edge_gateway(event_bus=bus)
    run_game_node(event_bus=bus)

    published = []

    def on_frame(frame):
        published.append(frame)

    bus.subscribe(PLAYER_FRAME_SUBJECT, on_frame)
    bus.publish(COMMAND_SUBJECT, {"game_id": "g1", "action": "click", "row": 2, "col": 3})

    assert len(published) == 1
    assert published[0]["game_id"] == "g1"
    assert published[0]["type"] == "snapshot"
