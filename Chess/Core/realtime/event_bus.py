from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple


class EventBus:
    """Simple pub/sub bus for in-process events."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Tuple[object, Callable[[object], None]]]] = {}
        self._next_token = 0

    def subscribe(self, event_name: str, handler: Callable[[object], None]) -> int:
        self._subscribers.setdefault(event_name, [])
        token = self._next_token
        self._next_token += 1
        self._subscribers[event_name].append((token, handler))
        return token

    def unsubscribe(self, token: int) -> None:
        for event_name, subscribers in list(self._subscribers.items()):
            self._subscribers[event_name] = [
                (existing_token, handler)
                for existing_token, handler in subscribers
                if existing_token != token
            ]
            if not self._subscribers[event_name]:
                del self._subscribers[event_name]

    def publish(self, event_name: str, payload: Optional[object] = None) -> None:
        for _, handler in list(self._subscribers.get(event_name, [])):
            handler(payload)
