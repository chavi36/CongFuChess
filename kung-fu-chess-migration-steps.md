# Kung-Fu Chess Migration Plan

This document defines the concrete, sequential migration steps required to refactor the current Python project so it conforms to the architecture, rules, and tiering requirements in the reference specification.

## Migration principles

The implementation must preserve these non-negotiable rules:

- Existing files may be renamed, moved, or reorganized if their current names or locations do not match the target architecture.
- The migration should preserve behavior and test coverage while adapting the repository layout to the required tiered structure.
- The current repository layout is treated as a starting point, not a constraint; package, module, and directory names may be changed where necessary to align with the spec.

- The game node is the only authoritative rule engine.
- Layering is strictly one-directional: model ← rules/events ← real_time ← game_engine.
- The arbiter is the sole publisher of move/capture/end events.
- Time is a closed-form game-time model based on integer milliseconds; do not replace it with a tick loop.
- The wire protocol uses absolute server timestamps and delta-only payloads.
- The game tier scales by draining, never by eviction.
- Tests are deterministic and clock-driven.

## Phase 0 — Establish the migration boundary and instrumentation

### Objective
Create a baseline that makes the existing engine observable and testable before structural changes begin.

### Key Tasks
- Inventory the current engine and split responsibilities into the target layers:
  - model: board, position, piece, player, game state
  - rules: move validation and geometry
  - real_time: motion, arrivals, capture resolution
  - engine: orchestration and event emission
- Introduce a thin instrumentation layer around the current engine so every state transition can be logged with:
  - game_id
  - event type
  - game_time_ms
  - monotonic_seq
  - actor
- Add a deterministic clock abstraction to the current engine so all logic can be driven by `advance_time(ms)` rather than wall-clock sleeps.
- Add a minimal event sink interface that can later be backed by NATS, in-process buses, or file-backed fixtures.
- Freeze the current gameplay semantics in a golden test suite before refactoring.
- Explicitly define the current engine’s current behaviour for:
  - move timing
  - jump timing
  - capture resolution
  - game-over conditions

### Verification/Testing
- Run the existing unit and integration suites and record their results as the migration baseline.
- Add deterministic tests that verify the engine produces the same result under a fake clock for the same command sequence.
- Verify that state transitions are observable in a stable order, including event emission order and timestamps.

---

## Phase 1 — Introduce the shared schema and delta wire contract

### Objective
Define the language-neutral wire contract before any server or client tier is rewritten.

### Key Tasks
- Create a shared schema package for the wire format, compiled into both the Go engine and the TypeScript client.
- Define:
  - envelope fields: `game_id`, `session_id`, `seq`, `client_ts`, `server_ts`
  - frame types: keyframe, delta, terminal event, rejection
  - payload structure for board deltas and terminal outcomes
- Replace any existing full-state snapshots with delta-only payloads.
- Ensure the schema is positional-array based and compact; target a typical move frame of roughly 105–150 bytes.
- Define the recovery semantics:
  - keyframe is the authoritative recovery path
  - gaps and reconnects resolve by keyframe delivery
- Version the protocol at handshake with major/minor semantics; minor changes must remain additive only.

### Verification/Testing
- Write schema conformance tests that validate serialization/deserialization in both directions.
- Verify that a delta frame can be applied to a known keyframe and produces the same resulting state as a full-state snapshot.
- Add tests that ensure no frame is emitted with sampled progress; timestamps are always absolute server times.
- Validate that the protocol remains sparse during idle periods and does not emit frames when no visible change occurred.

---

## Phase 2 — Replace the tick-based runtime with a discrete-event scheduler

### Objective
Replace the existing time progression model with an authoritative, deterministic discrete-event scheduler that matches the spec’s closed-form time semantics.

### Key Tasks
- Remove the concept of a 50 ms tick loop from the runtime.
- Introduce a per-game event heap with events such as:
  - arrival
  - capture resolution
  - pause start/end
  - terminal event
- Introduce a per-shard outer heap that schedules game work without requiring a lock on game state.
- Reimplement the time model as:
  - `time_at_cell = start + (index + 1) × DELAY`
  - `wall_time = game_time + pause_offset_ms`
- Implement deterministic event ordering by `(game_time, monotonic_seq)`.
- Ensure that the arbiter is the only producer of move/capture/end events.
- Replace any existing “advance simulation by time” logic with event-driven execution behind a clock interface.

### Verification/Testing
- Write deterministic tests with a mock clock that advance time in milliseconds and assert event ordering.
- Validate that a pause adds elapsed time to `pause_offset_ms` and re-keys the outer event heap correctly.
- Verify that at most one visible change causes at most one frame per game per drain pass.
- Test that the scheduler produces identical results for equivalent input sequences independent of wall-clock timing.

---

## Phase 3 — Separate the authoritative engine from the presentation and input layers

### Objective
Ensure that the current Python engine becomes the authoritative domain core and no longer mixes UI or transport concerns into the logic path.

### Key Tasks
- Refactor the current engine code so it depends only on:
  - model
  - rules
  - real_time
  - engine
- Move all UI-specific logic out of the core engine and into adapters.
- Remove any client-side prediction or rollback behaviour from the Python engine.
- Introduce an explicit command boundary that accepts commands from an external transport and returns events and frame updates.
- Define a pure “apply command” path that accepts an authoritative command and emits a deterministic result set.
- Make the engine output events rather than mutating UI state directly.

### Verification/Testing
- Write tests that call the core engine through the command boundary and verify output events without involving GUI or socket code.
- Confirm that the engine never depends on GUI modules for rule evaluation.
- Verify that a command that is invalid at the authoritative layer is rejected cleanly and does not affect state.

---

## Phase 4 — Introduce the stateless API and auth services

### Objective
Create the stateless entry tiers so HTTP traffic no longer competes with game simulation work.

### Key Tasks
- Create a FastAPI-based API Gateway with endpoints for:
  - register
  - login
  - refresh
  - profile
  - history
  - room create/join
  - quick-match enqueue
- Extract password hashing and token issuance into a dedicated Auth Service.
- Implement scrypt-based password hashing with the required parameters.
- Implement Ed25519-signed JWTs with:
  - access TTL 15 minutes
  - refresh TTL 30 days
  - rotation and reuse detection
- Configure the gateway to verify JWTs locally against a cached JWKS provider.
- Ensure the auth service is deployed independently so KDF work never competes with game-node CPU.

### Verification/Testing
- Add contract tests for register/login/refresh flows.
- Verify token rotation and reuse detection produce deterministic outcomes.
- Test that the gateway rejects invalid tokens before the request reaches the game path.
- Validate that the auth service can be scaled independently of the game tier.

---

## Phase 5 — Introduce the Go game node and the NATS command/frame bus

### Objective
Move authoritative simulation to a Go game node and route traffic through NATS without allowing any non-authoritative tier to evaluate rules.

### Key Tasks
- Create a new Go service for the authoritative game node.
- Define the node process model with:
  - S shards
  - game assignment by `hash(game_id) mod S`
  - one goroutine per shard and no locks on state
- Implement the node’s inbound subject as `cmd.{shard}.{node_id}`.
- Implement command handling so the node:
  - subscribes only to the single inbound subject
  - stamps arrival time at the authoritative node
  - routes to the owning shard goroutine
  - validates commands against authoritative state
  - schedules events only after validation succeeds
- Implement outbound framing to:
  - `edge.{edge_id}` for player sockets
  - `spec.{shard}.{game_id}` for spectators when watched
- Ensure the node emits at most one frame per game per 10 ms and at most one per drain pass.
- Make the edge tier publish commands to the bus and never dial the game node directly.

### Verification/Testing
- Add integration tests that run the Go node against a virtual clock and verify the same move sequence produces the same event/output order.
- Test that command loss on the inbound bus is treated as a dropped command, not a replayed or re-ordered action.
- Validate frame emission caps with a synthetic burst of commands and assert no more than the permitted number of frames is emitted.
- Verify that a command published to a dead node subject is dropped and the edge must re-issue the action after reconnect/recovery.

---

## Phase 6 — Implement the WebSocket edge gateway and session routing

### Objective
Build the player-facing edge tier so it only holds sockets and forwards opaque game frames without becoming a game authority.

### Key Tasks
- Create a Go WebSocket gateway service that holds player sockets only.
- Implement per-socket rate limiting at 10 commands/s with burst 20 before publish.
- Parse only the envelope, never the game payload.
- Cache `(bus_shard, node_id)` per socket after the join response and first keyframe.
- Implement session routing, including Redis-backed `sess:{user_id}` updates and session eviction semantics.
- Add WebSocket ping/pong for liveness and close sockets on bus shard loss after the 2 s timeout.
- Ensure the edge tier never performs directory lookups on the hot path; it uses cached routing metadata only.

### Verification/Testing
- Simulate socket bursts and verify the rate limiter rejects or coalesces commands according to the configured policy.
- Test that a reconnect after a shard outage results in socket closure and a pause-by-offset transition on the game node.
- Verify that the edge forwards only envelope metadata and leaves payload evaluation entirely to the authoritative node.

---

## Phase 7 — Add matchmaker, allocator, room lobbies, and Redis-backed placement

### Objective
Introduce the control-plane services required to create games, place them on nodes, and manage room lifecycle.

### Key Tasks
- Implement the Matchmaker as an in-memory sharded queue keyed by `(region, rating bucket)`.
- Implement widening rating bands: ±100, +50 every 5 s, capped at ±400.
- Implement the Game Allocator as a stateless Redis-backed service.
- Add the four allocator responsibilities:
  - placement
  - directory
  - supervision
  - room lobbies
- Implement room semantics with the required one-way state machine:
  - waiting → live → ended
- Implement the claim flow for the second seat using an atomic Redis operation and return the client’s role from the API response.
- Ensure that a spectator is never promoted to a player and that a dropped player pauses and then forfeits after the pause budget is exhausted.

### Verification/Testing
- Add tests for the claim operation to confirm only one seat 2 claim succeeds and subsequent joins are treated as spectator-only operations.
- Verify that a room in `waiting` state never exposes a `game_id` until the seat claim succeeds.
- Test allocator supervision by expiring a lease and asserting a rebuild workflow is triggered.
- Verify redis boundaries: the allocator writes placement metadata and room state to Redis, while game-results and durable user data remain outside the hot path.

---

## Phase 8 — Add spectator relay, keyframe cadence, and replay rebuild support

### Objective
Enable spectator fan-out and recovery without introducing spectator input into the authoritative path.

### Key Tasks
- Create the Spectator Relay service.
- Subscribe to `spec.{shard}.{game_id}` and cache keyframes at the required 10 s internal cadence for watched games only.
- Keep the relay read-only and ensure no spectator input reaches the game tier.
- Implement a short post-game cache.
- Implement the rebuild path so a survivor node replays the Redis-backed game log after allocator supervision detects a failed node.
- Ensure the first keyframe from the rebuilt game carries the new `node_id` so edges repoint their caches.

### Verification/Testing
- Simulate a watched game and assert the relay receives keyframes and serves them with bounded delay.
- Test that the relay never publishes spectator commands into the authoritative command subject.
- Validate rebuild behaviour by failing a node, reassigning the game, and ensuring the new node emits a keyframe that updates the edge routing cache.

---

## Phase 9 — Separate durable data and hot-path data

### Objective
Ensure PostgreSQL and Redis are used in the correct places so the simulation tier remains fast and the durable tier remains reliable.

### Key Tasks
- Keep PostgreSQL for durable data only:
  - users
  - game results
- Keep Redis for ephemeral data only:
  - session directory
  - room state
  - game placement records
  - game log
  - rate limiters
- Implement result writing through a dedicated Result Writer service that consumes terminal events.
- Make `game_results` writes idempotent through the primary key / idempotency key pattern.
- Apply Elo in batch form with the specified K-factor and default rating.
- Ensure the game node never depends on PostgreSQL for live state.

### Verification/Testing
- Test that a terminal event results in exactly one durable result write, even if the event is replayed.
- Verify Redis keys are cleaned or expired according to their TTL policy.
- Verify that the hot path does not require a PostgreSQL round trip for move processing or frame delivery.

---

## Phase 10 — Production hardening, deployment, and observability

### Objective
Make the system operationally safe at scale and align it with the production deployment model.

### Key Tasks
- Add Kubernetes manifests and deployment configs for the tiered services.
- Add a Docker Compose harness for local development.
- Implement Prometheus metrics with no high-cardinality labels; export bus shard queue depth and canary-game SLI metrics.
- Add preStop drain hooks for game nodes with a 150 s drain period.
- Configure multi-AZ deployment for the game tier, Redis fleet, and bus shards.
- Set up retention policies for result data and room/game lifecycle cleanup.
- Add structured logs and correlation IDs for requests, commands, and terminal events.

### Verification/Testing
- Run the development harness with the full stack and verify all tiers start and communicate deterministically.
- Simulate node shutdown and ensure the node refuses new games, drains existing games, and exits without live migration.
- Verify that metrics remain bounded and do not grow with per-game cardinality.

---

## Implementation order summary

The migration should proceed in the following order:

1. Instrument and stabilize the current Python engine.
2. Define the shared delta schema and wire contract.
3. Replace the tick loop with the deterministic discrete-event scheduler.
4. Separate the authoritative engine from UI and transport concerns.
5. Introduce the stateless API/auth services.
6. Introduce the Go game node and NATS bus.
7. Add the WebSocket edge gateway and routing logic.
8. Add allocator, matchmaking, rooms, and Redis placement state.
9. Add spectator relay and rebuild support.
10. Split durable and ephemeral storage responsibilities.
11. Add deployment, observability, and hardening.

## Recommended implementation strategy for this repository

Because the current project already has a real-time engine and a layered Python structure, the least risky migration path is:

- Keep the existing Python engine as the initial domain model and refactor it into a pure authoritative core.
- Introduce schema and event abstractions first.
- Build the scheduler, then migrate the engine into the Go game node.
- Keep the current board/rules/realtime modules as the source of truth for the first rewrite, but make them compile into the new authoritative engine contract.
- Do not implement a client-side engine, prediction layer, or reconciliation path; all authoritative decisions must come from the game node.
