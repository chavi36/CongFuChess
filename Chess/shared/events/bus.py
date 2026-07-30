"""Shared event bus abstraction for Kung-Fu Chess."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple


class EventBus(ABC):
    @abstractmethod
    def publish(self, subject: str, message: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, subject: str, handler: Callable[[Any], None]) -> int:
        raise NotImplementedError

    @abstractmethod
    def unsubscribe(self, subject: str, token: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class InMemoryEventBus(EventBus):
    """Simple in-process event bus implementation."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Tuple[int, Callable[[Any], None]]]] = {}
        self._next_token = 0

    def publish(self, subject: str, message: Any) -> None:
        for _, handler in list(self._subscribers.get(subject, [])):
            handler(message)

    def subscribe(self, subject: str, handler: Callable[[Any], None]) -> int:
        self._subscribers.setdefault(subject, [])
        token = self._next_token
        self._next_token += 1
        self._subscribers[subject].append((token, handler))
        return token

    def unsubscribe(self, token: int) -> None:
        for subject, subscribers in list(self._subscribers.items()):
            filtered = [
                (existing_token, handler)
                for existing_token, handler in subscribers
                if existing_token != token
            ]
            if filtered:
                self._subscribers[subject] = filtered
            else:
                del self._subscribers[subject]

    def close(self) -> None:
        self._subscribers.clear()
