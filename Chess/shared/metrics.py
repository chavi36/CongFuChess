"""Prometheus metrics for Kung-Fu Chess services.

Exports only bounded-cardinality metrics:
  - bus_shard_queue_depth   (gauge, label: shard)
  - canary_game_latency_ms  (gauge)
  - commands_total          (counter, label: service)
  - frames_emitted_total    (counter, label: service)

No per-game or per-user labels — cardinality stays bounded.
"""

from __future__ import annotations

_shard_queue_depth: dict[str, int] = {}
_canary_latency_ms: float = 0.0
_counters: dict[str, int] = {}


# ── writers (called by services) ─────────────────────────────────────────────

def set_shard_queue_depth(shard: str, depth: int) -> None:
    _shard_queue_depth[shard] = depth


def set_canary_latency_ms(latency_ms: float) -> None:
    global _canary_latency_ms
    _canary_latency_ms = latency_ms


def inc_commands(service: str) -> None:
    key = f"commands_total{{service=\"{service}\"}}"
    _counters[key] = _counters.get(key, 0) + 1


def inc_frames(service: str) -> None:
    key = f"frames_emitted_total{{service=\"{service}\"}}"
    _counters[key] = _counters.get(key, 0) + 1


# ── exposition (Prometheus text format) ──────────────────────────────────────

def exposition() -> str:
    lines: list[str] = []

    lines.append("# HELP bus_shard_queue_depth Number of pending events per bus shard")
    lines.append("# TYPE bus_shard_queue_depth gauge")
    for shard, depth in _shard_queue_depth.items():
        lines.append(f'bus_shard_queue_depth{{shard="{shard}"}} {depth}')

    lines.append("# HELP canary_game_latency_ms Round-trip latency of the canary game SLI in ms")
    lines.append("# TYPE canary_game_latency_ms gauge")
    lines.append(f"canary_game_latency_ms {_canary_latency_ms}")

    lines.append("# HELP commands_total Total commands received per service")
    lines.append("# TYPE commands_total counter")
    lines.append("# HELP frames_emitted_total Total frames emitted per service")
    lines.append("# TYPE frames_emitted_total counter")
    for key, val in _counters.items():
        lines.append(f"{key} {val}")

    return "\n".join(lines) + "\n"
