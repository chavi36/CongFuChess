from shared.events import InMemoryEventBus, PLAYER_FRAME_SUBJECT
from services.spectator_relay import get_last_spectator_frame, run_spectator_relay


def test_spectator_relay_subscribes_to_player_frames():
    bus = InMemoryEventBus()
    run_spectator_relay(event_bus=bus)

    bus.publish(PLAYER_FRAME_SUBJECT, {"game_id": "g1", "type": "snapshot", "board": []})

    frame = get_last_spectator_frame()
    assert frame is not None
    assert frame["game_id"] == "g1"
    assert frame["type"] == "snapshot"
