"""Result writer service — consumes terminal events, writes to durable store.

Durable store (SQLite/PostgreSQL): game_results, user Elo updates.
In-memory cache: fast get_result / get_last_result for tests and hot-path reads.
The game node never calls this service directly.
"""

from shared.events import InMemoryEventBus, TERMINAL_EVENT_SUBJECT
from shared import logging as slog
from shared import metrics

_results: dict[str, dict] = {}


def write_result(game_id: str, result: dict) -> None:
    """Write to in-memory cache (used directly in tests and by _handle_terminal_event)."""
    _results[game_id] = dict(result)


def get_result(game_id: str) -> dict | None:
    return _results.get(game_id)


def get_last_result() -> dict | None:
    return next(reversed(_results.values()), None)


def _handle_terminal_event(event: dict) -> None:
    game_id = event.get("game_id")
    result  = event.get("result")
    if not game_id or not isinstance(result, dict):
        return

    log = slog.RequestLogger(game_id=game_id, service="result-writer")
    write_result(game_id, result)
    metrics.inc_commands("result-writer")

    winner = result.get("winner")
    loser  = result.get("loser")
    if winner and loser:
        try:
            from services.auth import write_game_result
            written = write_game_result(game_id, winner, loser)
            log.info("game_result_written", winner=winner, loser=loser, persisted=written)
        except Exception as exc:
            log.error("durable_write_failed", reason=str(exc))


def run_result_writer(event_bus: InMemoryEventBus | None = None) -> InMemoryEventBus:
    if event_bus is None:
        event_bus = InMemoryEventBus()
    event_bus.subscribe(TERMINAL_EVENT_SUBJECT, _handle_terminal_event)
    return event_bus
