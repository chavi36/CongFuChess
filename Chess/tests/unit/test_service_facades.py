from services.allocator import allocate_game_node, get_allocated_node
from services.game_node import run_game_node
from services.result_writer import get_result, write_result
from services.spectator_relay import last_frame, relay_frame


def test_allocator_allocates_and_remembers_node():
    game_id = "room-42"

    node = allocate_game_node(game_id)
    assert node == "game-node-1"
    assert get_allocated_node(game_id) == node


def test_relay_frame_records_last_frame():
    frame = {"foo": "bar"}

    relay_frame(frame)
    assert last_frame() == frame


def test_write_result_persists_and_gets_result():
    game_id = "game-99"
    result = {"winner": "white", "moves": 10}

    write_result(game_id, result)
    assert get_result(game_id) == result


def test_game_node_run_entrypoint_is_callable():
    assert callable(run_game_node)
