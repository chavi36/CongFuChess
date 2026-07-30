"""Edge gateway service runtime for Kung-Fu Chess."""

from shared.events import InMemoryEventBus, COMMAND_SUBJECT, PLAYER_FRAME_SUBJECT
from .server import set_event_bus
from services.matchmaker import run_matchmaker
from services.room_manager import run_room_manager

_event_bus: InMemoryEventBus | None = None
_frames: list[dict] = []


def _handle_player_frame(frame: dict) -> None:
    _frames.append(frame)


def run_edge_gateway(event_bus: InMemoryEventBus | None = None) -> InMemoryEventBus:
    """Start the edge gateway service runtime with an event bus."""
    global _event_bus
    if event_bus is None:
        event_bus = InMemoryEventBus()
    _event_bus = event_bus
    set_event_bus(event_bus)
    run_matchmaker(event_bus)
    run_room_manager(event_bus)
    event_bus.subscribe(PLAYER_FRAME_SUBJECT, _handle_player_frame)
    return event_bus


def publish_command(command: dict) -> None:
    if _event_bus is None:
        raise RuntimeError("Edge gateway event bus is not initialized")
    _event_bus.publish(COMMAND_SUBJECT, command)


def get_last_player_frame() -> dict | None:
    return _frames[-1] if _frames else None
