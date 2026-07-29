# Repo-specific migration checklist for Kung-Fu Chess

This checklist maps the architecture in the reference spec to the files already present in this repository so the migration can be executed concretely.

## 1. Target repository shape

The current repository should be reorganized into the following high-level structure:

- services/api-gateway/
- services/auth/
- services/edge-gateway/
- services/spectator-relay/
- services/matchmaker/
- services/allocator/
- services/game-node/
- services/result-writer/
- shared/schema/
- shared/protocol/
- shared/events/
- infra/
- tests/

The existing Python engine under [Chess/Core](Chess/Core) should become the reference domain model for the first migration pass, then be reimplemented or wrapped by the authoritative game node.

## 2. File-by-file migration map

### A. Authoritative game domain core

Current files:
- [Chess/Core/engine/game_engine.py](Chess/Core/engine/game_engine.py)
- [Chess/Core/realtime/real_time_arbiter.py](Chess/Core/realtime/real_time_arbiter.py)
- [Chess/Core/rules/rule_engine.py](Chess/Core/rules/rule_engine.py)
- [Chess/Core/rules/piece_rules.py](Chess/Core/rules/piece_rules.py)
- [Chess/Core/model/board.py](Chess/Core/model/board.py)
- [Chess/Core/model/game_state.py](Chess/Core/model/game_state.py)
- [Chess/Core/model/config.py](Chess/Core/model/config.py)

Action:
- Keep these as the canonical domain logic for the initial migration.
- Refactor them so they become pure authoritative logic with no GUI dependencies.
- Introduce a deterministic clock and event emitter around them.
- Later, port the same semantics into the Go game node.

### B. Current server entrypoint

Current file:
- [Chess/application/server/server.py](Chess/application/server/server.py)

Action:
- Split this file into at least two responsibilities:
  - WebSocket edge gateway logic
  - room/match flow orchestration
- The current socket server should no longer be the place where game rules are evaluated.
- It should only parse envelopes, route commands, and forward them to the bus.

### C. Matchmaking and rooms

Current files:
- [Chess/application/server/matchmaker.py](Chess/application/server/matchmaker.py)
- [Chess/application/server/room_manager.py](Chess/application/server/room_manager.py)
- [Chess/application/server/game_server.py](Chess/application/server/game_server.py)

Action:
- Keep them as the starting point for control-plane logic.
- Refactor them into the allocator/matchmaker/room lifecycle flow described in the spec.
- Replace any direct game execution coupling with a message-driven flow.

### D. Persistence and auth

Current files:
- [Chess/application/server/db/db.py](Chess/application/server/db/db.py)
- [Chess/application/server/db_2.py](Chess/application/server/db_2.py)

Action:
- Split auth and durable user data away from game-runtime state.
- Keep PostgreSQL responsibilities limited to users and game results.
- Keep Redis responsibilities limited to sessions, room state, placement records, and game logs.

## 3. Concrete implementation order

### Phase 0 — Stabilize the current engine

Objective:
- Make the current Python engine deterministic and safe to migrate.

Tasks:
- Create a thin event abstraction around the engine so all state transitions can be observed.
- Add a clock interface and a fake clock implementation.
- Replace any direct sleeps or wall-clock assumptions with deterministic time progression.
- Add tests that lock in current move/jump/capture/game-over behavior before refactoring.

First files to touch:
- [Chess/Core/engine/game_engine.py](Chess/Core/engine/game_engine.py)
- [Chess/Core/realtime/real_time_arbiter.py](Chess/Core/realtime/real_time_arbiter.py)

### Phase 1 — Introduce the shared wire schema

Objective:
- Define the protocol that the engine, edge, and client will all speak.

Tasks:
- Create a shared schema package under shared/schema/.
- Define:
  - envelope fields
  - keyframe and delta frame formats
  - terminal event format
  - rejection format
- Keep the schema language-neutral and usable from Python, Go, and TypeScript.

First files to add:
- shared/schema/
- shared/protocol/

### Phase 2 — Replace the current time progression model

Objective:
- Move from a simple progression model to a discrete-event scheduler.

Tasks:
- Introduce a per-game event queue.
- Make move arrival, jump completion, pause handling, and end events explicit scheduler events.
- Ensure ordering is deterministic by `(game_time, monotonic_seq)`.
- Make the scheduler independent from GUI or socket code.

First files to touch:
- [Chess/Core/realtime/real_time_arbiter.py](Chess/Core/realtime/real_time_arbiter.py)
- [Chess/Core/engine/game_engine.py](Chess/Core/engine/game_engine.py)

### Phase 3 — Separate authoritative logic from transport/UI logic

Objective:
- Remove GUI and socket concerns from the core engine.

Tasks:
- Refactor [Chess/Core/engine/game_engine.py](Chess/Core/engine/game_engine.py) so it exposes a command interface rather than UI-coupled methods.
- Make the engine emit events instead of directly nudging GUI code.
- Ensure the rules layer remains read-only and does not depend on rendering or sockets.

### Phase 4 — Split the current server into gateway and control-plane services

Objective:
- Turn [Chess/application/server/server.py](Chess/application/server/server.py) into a gateway-like service rather than a monolithic game server.

Tasks:
- Move protocol parsing and socket handling into an edge gateway service.
- Keep matchmaking and room lifecycle in a separate service.
- Make the game node the only authority for rule evaluation.

### Phase 5 — Create the first Go game-node skeleton

Objective:
- Introduce the authoritative game node service.

Tasks:
- Create services/game-node/ with a minimal Go program.
- Implement a basic command subscription path.
- Hook it up to a local in-memory or test bus first.
- Port the existing engine rules into the node in stages.

### Phase 6 — Add NATS-based command and frame transport

Objective:
- Replace any direct in-process flow with bus-based command and frame routing.

Tasks:
- Add NATS subjects for:
  - inbound commands
  - player frames
  - spectator frames
  - terminal events
- Make the edge gateway publish commands to NATS.
- Make the game node publish frames to NATS.
- Keep the edge gateway as a pure transport tier.

### Phase 7 — Introduce allocator, rooms, and matchmaking flow

Objective:
- Build the control-plane flow described in the spec.

Tasks:
- Refactor [Chess/application/server/matchmaker.py](Chess/application/server/matchmaker.py) into a sharded matcher.
- Refactor [Chess/application/server/room_manager.py](Chess/application/server/room_manager.py) into a room lifecycle manager.
- Add Redis-backed placement and room state records.
- Make room join return the role from the server rather than leaving it to the client.

### Phase 8 — Add spectator relay and rebuild path

Objective:
- Support watched games and recovery.

Tasks:
- Add a spectator relay service.
- Subscribe to spectator frame subjects.
- Add keyframe-based recovery and rebuild support.
- Make the first keyframe from a rebuilt game repoint edge caches.

### Phase 9 — Separate durable and ephemeral storage

Objective:
- Align storage use with the spec.

Tasks:
- Keep PostgreSQL for users and game results only.
- Keep Redis for sessions, rooms, and placement state.
- Add a result-writer service for terminal events.

## 4. First implementation milestones

The safest first milestones are:

1. Add deterministic clock and event abstraction around [Chess/Core/engine/game_engine.py](Chess/Core/engine/game_engine.py).
2. Introduce the shared schema package.
3. Refactor [Chess/Core/realtime/real_time_arbiter.py](Chess/Core/realtime/real_time_arbiter.py) into an event-driven arbiter.
4. Split [Chess/application/server/server.py](Chess/application/server/server.py) so it no longer owns game execution.
5. Add the first Go game-node skeleton and a minimal command loop.

## 5. Definition of done for the first migration slice

The first slice is complete when:

- the Python engine can run deterministically with a fake clock,
- the shared schema exists and is used by the engine and transport layer,
- the current server is no longer the authoritative runtime,
- an initial Go game-node process can receive and process a command,
- and the system can emit a frame or terminal event through a defined event contract.
