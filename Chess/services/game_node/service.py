"""Game node service runtime for Kung-Fu Chess."""

from shared.events import (
    EventBus,
    InMemoryEventBus,
    COMMAND_SUBJECT,
    PLAYER_FRAME_SUBJECT,
    TERMINAL_EVENT_SUBJECT,
)
from shared import logging as slog
from shared import metrics


def run_game_node(event_bus: EventBus | None = None) -> EventBus:
    """Start the game node service runtime."""
    if event_bus is None:
        event_bus = InMemoryEventBus()

    def _handle_command(command: dict) -> None:
        log = slog.RequestLogger(game_id=command.get("game_id"), service="game-node")
        log.info("command_received", command_type=command.get("type") or command.get("action"))
        metrics.inc_commands("game-node")
        event_bus.publish(PLAYER_FRAME_SUBJECT, {
            "game_id": command.get("game_id"),
            "type": "snapshot",
            "payload": command,
        })
        metrics.inc_frames("game-node")
        if command.get("terminal"):
            event_bus.publish(TERMINAL_EVENT_SUBJECT, {
                "game_id": command.get("game_id"),
                "result": command.get("result", {}),
            })
            log.info("terminal_event_emitted")

    event_bus.subscribe(COMMAND_SUBJECT, _handle_command)
    return event_bus
