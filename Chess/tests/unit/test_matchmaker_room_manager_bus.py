from shared.events import InMemoryEventBus
from services.edge_gateway import run_edge_gateway, publish_command
from services.matchmaker import run_matchmaker
from services.room_manager import run_room_manager


def test_matchmaker_and_room_manager_command_flow():
    bus = InMemoryEventBus()

    run_edge_gateway(event_bus=bus)
    run_matchmaker(event_bus=bus)
    run_room_manager(event_bus=bus)

    events = []

    def collect_event(event: dict) -> None:
        events.append(event)

    bus.subscribe("kungfuchess.match_events", collect_event)
    bus.subscribe("kungfuchess.room_events", collect_event)

    publish_command({
        "type": "create_room",
        "password": "pass123",
        "ws_ref": "ws1",
        "user": {"name": "alice", "range": 1500},
    })

    publish_command({
        "type": "join_room",
        "room_id": events[0]["room_id"],
        "password": "pass123",
        "ws_ref": "ws2",
        "user": {"name": "bob", "range": 1480},
    })

    assert any(event["action"] == "room_created" for event in events)
    assert any(event["action"] == "room_joined" for event in events)
