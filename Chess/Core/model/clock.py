from __future__ import annotations

from abc import ABC, abstractmethod


class Clock(ABC):
    @abstractmethod
    def now(self) -> int:
        pass

    @abstractmethod
    def advance(self, delta_ms: int) -> None:
        pass


class FakeClock(Clock):
    def __init__(self, initial_time_ms: int = 0) -> None:
        self._time_ms = initial_time_ms

    def now(self) -> int:
        return self._time_ms

    def advance(self, delta_ms: int) -> None:
        if delta_ms < 0:
            raise ValueError("Cannot advance clock by a negative interval")
        self._time_ms += delta_ms


class SystemClock(Clock):
    def __init__(self, initial_time_ms: int = 0) -> None:
        self._time_ms = initial_time_ms

    def now(self) -> int:
        return self._time_ms

    def advance(self, delta_ms: int) -> None:
        if delta_ms < 0:
            raise ValueError("Cannot advance clock by a negative interval")
        self._time_ms += delta_ms
