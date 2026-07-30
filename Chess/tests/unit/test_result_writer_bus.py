from shared.events import InMemoryEventBus, COMMAND_SUBJECT
from services.edge_gateway import publish_command, run_edge_gateway
from services.game_node import run_game_node
from services.result_writer import get_last_result, run_result_writer


def test_result_writer_subscribes_to_terminal_events():
    bus = InMemoryEventBus()
    run_edge_gateway(event_bus=bus)
    run_game_node(event_bus=bus)
    run_result_writer(event_bus=bus)

    publish_command({"game_id": "g1", "action": "end", "terminal": True, "result": {"winner": "white"}})

    result = get_last_result()
    assert result is not None
    assert result["winner"] == "white"
