from shared.events import InMemoryEventBus
from services.edge_gateway import get_last_player_frame, publish_command, run_edge_gateway
from services.game_node import run_game_node
from services.result_writer import get_last_result, run_result_writer
from services.spectator_relay import get_last_spectator_frame, run_spectator_relay


def test_full_bus_pipeline_delivers_frame_and_result():
    bus = InMemoryEventBus()

    run_edge_gateway(event_bus=bus)
    run_game_node(event_bus=bus)
    run_spectator_relay(event_bus=bus)
    run_result_writer(event_bus=bus)

    publish_command({
        "game_id": "g1",
        "action": "click",
        "row": 2,
        "col": 3,
        "terminal": True,
        "result": {"winner": "white"},
    })

    frame = get_last_player_frame()
    assert frame is not None
    assert frame["game_id"] == "g1"
    assert frame["type"] == "snapshot"

    spectator_frame = get_last_spectator_frame()
    assert spectator_frame is not None
    assert spectator_frame["game_id"] == "g1"

    result = get_last_result()
    assert result is not None
    assert result["winner"] == "white"
