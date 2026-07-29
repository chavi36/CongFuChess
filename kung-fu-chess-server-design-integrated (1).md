# Kung-Fu Chess — Server Design Architecture (Integrated Version)

**Status:** design document for an academic project  
**Input:** *Kung-Fu Chess — Scale-Up Design Brief* (referenced below as "the brief")  
**Design point:** 10,000,000 concurrent users, ~1.43M concurrent games  
**Optimizes for:** defensible reasoning and explicit tradeoffs, not operational realism  

---

#### 0. How to read this document
Section 1 restates the invariants that survive the rewrite. Sections 2–3 fix the load model and the tier map. Sections 4–10 are the design proper, one tier at a time. Section 11 is the wire protocol, 12 the data flows, 13 the capacity math, 14 the failure analysis. Sections 15–18 close the open questions, list what was traded away, name what must be measured before any of these numbers can be trusted, and give a staged migration path.

Every number in this document is an **estimate derived from an unmeasured baseline**. §17 lists the seven measurements that would confirm or destroy them. Where a number drives a structural decision, the sensitivity is stated inline.

Two conventions:
* **"Frame"** = one serialized server→client message for one game. Frames are identical for every recipient of a game, so a frame is encoded once and written N times.
* **"Game time"** vs **"wall time"**: all engine timestamps are integer milliseconds in *game time*. Wall time = game time + the game's accumulated pause offset (§7.5).

---

#### 1. Invariants — what must remain true
These are load-bearing properties of the existing prototype. The rewrite replaces the implementation of nearly everything, so the invariants have to be stated as contracts rather than as code.

| # | Invariant | Enforced by |
|---|---|---|
| I1 | The engine is the sole authority on game state. No client, gateway, relay, or bus node evaluates a rule. | Relays handle frames as opaque bytes (§10). Gateways parse only the envelope, never the payload (§5). |
| I2 | Strict one-directional layering: model ← rules/events ← real_time ← game_engine; shared (wire contract) depends only on model. | The shared contract becomes a language-neutral schema (§11.1) compiled into both the Go engine and the TS client. Nothing else may import it. |
| I3 | The arbiter is the only publisher of move/capture/end events; everything else subscribes. | The event bus seam is now also the process boundary — the same seam, one layer out (§6.3). |
| I4 | Temporal model is closed-form: time_at_cell = start + (index+1) × DELAY. | Preserved verbatim. It is what makes the discrete-event scheduler (§7), the pause-by-offset (§7.5), and the sparse-frame wire (§11) all possible. |
| I5 | The wire carries absolute times against a server clock, never sampled progress. | PiecePayload/StatePayload semantics survive into the delta protocol unchanged (§11.2). |
| I6 | Change coalescing: one visible change ⇒ one frame, regardless of how many internal events produced it. | Dirty flags survive; the drain loop emits at most one frame per game per pass (§7.4). |
| I7 | Tests are deterministic — fake clock, explicit advance_time(ms), no sleeps. | The scheduler takes a clock interface; the fake clock now also drives multi-node tests via a shared virtual clock in the harness (§18). |

**I4 is the single most valuable thing this codebase has.** Almost every scaling decision below is a consequence of it. A tick-based engine of the same game would not be economically deployable at this scale on the same hardware.

---

#### 2. Load model
##### 2.1 Derived load (validated against the brief)
Using 2 players + 5 viewers = 7 people per room, 60 s average game, ~1 combined move/second/game, ~3 state-changing frames/second/game:

| Quantity | Value | Derivation |
|---|---|---|
| Concurrent games | **1.43M** | 10M ÷ 7 |
| Concurrent players / viewers | **2.86M / 7.14M** | 1.43M × 2, × 5 |
| Games created = games ended | **23.8k/s** | 1.43M ÷ 60 |
| Matchmaking requests | **47.6k/s** | 23.8k × 2 |
| Inbound commands | **1.43M/s** | 1/s/game |
| — inbound bus publishes | **1.43M/s** | commands now traverse the bus (§6.3) |
| — inbound bus bytes @60 B | **~86 MB/s** | 1.9% of the 4.5 GB/s egress line |
| — inbound msgs per bus shard | **~179k/s** | 1.43M ÷ 8 shards, single-region worst case |
| Frames encoded | **4.3M/s** | 3/s/game |
| Message deliveries | **30M/s** | 4.3M × 7 |
| — of which to players | **8.6M/s** | 4.3M × 2 |
| — of which to viewers | **21.5M/s** | 4.3M × 5 |
| Egress, full state @1.5 KB | **45 GB/s ≈ 360 Gbps** | not viable |
| Egress, delta @150 B | **4.5 GB/s ≈ 36 Gbps** | viable |
| Scheduler events | **~5.7M/s** | ~4 events per move (§7.2) |
| Log writes to Redis | **~120 MB/s** | §8.2 |
| Game-result rows | **23.8k/s ≈ 2.06B/day** | retention: §15.3 |

The brief's numbers hold. The one I would flag as fragile is **3 frames/second/game**: it is derived from the move rate, not measured, and every egress and delivery number is linear in it. If real play produces 2 moves/second per game, everything in the delivery and egress column doubles. §17 makes this measurement #1.

##### 2.2 Peak, and what "10M concurrent" means
The brief gives 10M concurrent users *and* a 3–5× daily peak factor. Taking both literally would mean provisioning for 50M. This design interprets **10M as the peak**, with a daily average of 2–3M and a trough near 1M. Consequences:
* Fleet sizing in §13 is peak sizing. Steady-state cost is ~⅓ of it.
* Every stateless tier (API, auth, matchmaker, allocator, relay) autoscales on its own signal.
* The **game tier scales down by draining, never by eviction** (§6.2, brief). A node refuses new games for ~2 minutes and empties itself, because games are only 30–90 s long. This is the single biggest operational simplification the short game length buys, and it is why no live migration exists anywhere in this design.

##### 2.3 Regional distribution (assumption A1 in the brief)
The split is unknown, so it is a parameter. The design behaves as follows at the two extremes:
* **All 10M in one region.** Capacity is fine — nothing in this design is globally serialized on the hot path. What degrades is *failure-domain concentration*: one region is one blast radius. Mitigation: within the region, shard the bus, the Redis fleet and the game tier across ≥3 availability zones, and make each shard independently survivable (§14).
* **Evenly across ten regions (1M each).** Capacity per region is trivially small. What degrades is **matchmaking liquidity, not compute.** With 1M concurrent users a region has ~286k queued-or-playing players; spread over ~30 rating buckets with a normal distribution around 1200, the tail buckets may have single-digit occupancy at any instant. Quick match in the tail fails and the "no player found, keep waiting?" prompt (§6.6, brief) fires far more often.

---

#### 3. Constraints and what they cost
##### 3.1 JSON on the wire (hard)
Deltas at ~150 B replace full state at ~1.5 KB, recovering the egress budget: **36 Gbps instead of 360 Gbps**.

| | JSON delta | Binary delta (hypothetical) |
|---|---|---|
| Typical move frame | ~150 B | ~28 B |
| Fleet egress | 4.5 GB/s (36 Gbps) | 0.85 GB/s (7 Gbps) |
| Encode cost | ~1.5 µs/frame | ~0.2 µs/frame |
| Fleet encode CPU | ~6.5 cores | ~0.9 cores |

**Cost of the constraint: ~29 Gbps of egress and ~6 cores.**

##### 3.2 No client-side engine (hard)
Resolved in §15.1. Short version: the client interpolates from absolute times, which is not an engine, and renders local, non-authoritative input affordances. No prediction, no rollback, no reconciliation anywhere in the system.

##### 3.3 Move latency must be imperceptible (hard)
Quantified as an SLO: **p99 from command keypress to the commanding player's own screen showing motion < 120 ms**, and **p99 to the opponent's screen < 180 ms**.

##### 3.4 Not a constraint: language
* **Game tier: Go.** Chosen over Rust for goroutine-per-game-shard ergonomics and sub-millisecond GC pauses.
* **Edge / relay tier: Go**, socket-holding workload.
* **API gateway, auth, matchmaker, allocator, result writer: Python (FastAPI)** is acceptable.

---

#### 4. Architecture overview
##### 4.1 Tier inventory
| Tier | Stateful? | Scaling signal | Why it is its own tier |
|---|---|---|---|
| **API Gateway** | no | HTTP RPS | Non-real-time surface: register, login, refresh, profile, history, room create/join, quick-match enqueue. Nothing here is on the frame path. |
| **Auth Service** | no | KDF queue depth | Password hashing must never compete with simulation for CPU. |
| **WS Player Gateway** | socket-affine only | concurrent sockets | Terminates TLS, verifies JWT, applies rate limits, publishes commands to the bus, demuxes frames to sockets. Holds no game-node connections. |
| **Spectator Relay** | no (cache only) | concurrent sockets | Read-only, ≤1 s delay, identical frames. |
| **Matchmaker** | in-memory queues | queue depth per shard | Sharded by (region, rating bucket); no global consistency (§8.1). |
| **Game Allocator** | no (Redis-backed) | placements/sec | Chooses a node for each new game, maintains directory, supervises node liveness, manages room lobbies (§8.3, §8.4). |
| **Game Node** | **yes — authoritative** | concurrent games | The only tier that knows the rules. ~20k games per node (§13.2). |
| **Result Writer** | no | queue depth | Consumes terminal events, writes game_results, applies Elo in batches (§12.5). |
| **NATS** | no | msgs/sec per cluster | Sharded into independent clusters; §6.3. |
| **Redis** | ephemeral | keys / ops | Game logs, session directory, rate limiters, room registry. |
| **PostgreSQL** | durable | write rate, storage | Users and game results only. Off the hot path entirely (§14). |

##### 4.2 The three structural moves
1. **Discrete-event scheduler replaces the 50 ms tick** (§7).
2. **Two-tier spectator fan-out** (§10).
3. **Both hot-path directions cross the bus** — `cmd.{shard}.{node_id}` inbound, direct edge addressing outbound, per-game subjects only for watched games (§6.3).

---

#### 5. Edge: API Gateway and WS Player Gateway
##### 5.1 API Gateway
Plain stateless HTTP behind an L7 load balancer. Endpoints include registration, authentication, room management, and matchmaking enqueuing.

Updated Room Endpoints (§8.4 integration):
* `POST /v1/rooms` — Create room lobby (returns room code, role=host).
* `POST /v1/rooms/{code}/join` — Join room lobby or game (allocator assigns player 2 or spectator role; triggers `create_game` when seat 2 is claimed).

##### 5.2 WS Player Gateway
Holds player sockets only. Performs token-bucket rate limiting (10 cmd/s/socket, burst 20) and envelope parsing, then **publishes every accepted command to the bus** on `cmd.{shard}.{node_id}`. It never dials a game node.

The gateway learns `(bus_shard, node_id)` for a game from the join response and the first keyframe, and caches it against the socket. Its entire outbound connection set is to its bus shards: no node directory, no node health state, no re-dial logic.

Rate limiting stays at the edge and stays *before* the publish, so rejected commands never reach the bus. This is what keeps the inbound bus line at the 1.43M/s of §2.1 rather than at the rate-limit ceiling.

**Cache invalidation.** A rebuilt game (§12.7) lands on a new node. The rebuilding node's first keyframe carries the current `node_id`; the gateway repoints on receipt. Commands published to the dead node's subject in the interim are dropped by the bus for want of a subscriber — the same user-visible outcome as a command that was in flight when the node died, and already covered by the 4–6 s rebuild stall.

##### 5.3 Session routing and "last login wins"
Redis key `sess:{user_id}` updated on heartbeat. New logins evict old sockets via `session.evict`.

---

#### 6. Bus: NATS topology and addressing
##### 6.1 Why NATS rather than Redis Pub/Sub
Sharded NATS provides wildcard hierarchies, queue groups, and leaf nodes without forcing key-space scaling alignment.

##### 6.2 Bus sharding
Partitioned into independent clusters: `bus_shard = hash(game_id) mod K` (K ≈ 8 per region).

##### 6.3 Addressing — the subscription-interest problem
Both directions of the hot path cross the bus.

* **Inbound:** `cmd.{shard}.{node_id}` — one subject per game node, subscribed by that node alone, published to by any edge holding a player socket for a game on that node.
* **Outbound:** direct edge addressing (`edge.{edge_id}`) for players; lazy per-game subjects (`spec.{shard}.{game_id}`) for watched games only.

Subject cardinality is unchanged in order of magnitude: inbound adds one subject per game node — 90 at peak (§13) — not one per game. `cmd.{shard}.{game_id}` would have added 1.43M subjects and promoted measurement #5 (§17) to the design's dominant risk. Addressing by node is what makes the extra hop cheap.

##### 6.4 Delivery guarantees
At-most-once via core NATS, now in both directions.

* **Outbound:** sequence gaps trigger keyframe requests, unchanged.
* **Inbound:** a dropped command is a move that never happened. The piece does not move, the player sees no motion within their own 120 ms SLO window, and re-issuing costs one keypress. There are no command acks, no inbound retry, and no dedupe window — adding them would put a state machine on the hot path to protect against a loss rate far below the rate at which players mis-click.

The asymmetry is deliberate: outbound loss is invisible to the player and therefore must be repaired by the protocol; inbound loss is immediately visible to the player and is therefore repaired by the player.

---

#### 7. Game tier: the engine
##### 7.1 Process model
Go process with S shards (one goroutine/OS thread per shard). Games assigned by `hash(game_id) mod S` with no locks on game state.

##### 7.2 Discrete-event scheduler
Replaces 50 ms tick with event heaps (per-game heap + per-shard outer heap). Averaging ~4 events per move.

##### 7.3 Command handling & 7.4 Frame emission
The node subscribes to exactly one inbound subject, `cmd.{shard}.{node_id}`, and accepts no inbound connections of its own. Each command envelope carries `(game_id, session_id, seq, client_ts)`; the node routes it to the owning shard goroutine by `hash(game_id) mod S` and stamps the authoritative arrival time there (§7.6), so bus transit falls *inside* the latency the server measures rather than outside it. Unicast command rejections. Frame emission rate-limited to 1 frame per game per 10 ms; serializes JSON once per frame for all recipients.

##### 7.5 Pause as a time offset
Pause records `paused_at`; resume adds elapsed time to `pause_offset_ms` and re-keys outer heap entry. Emits keyframe on resume.

##### 7.6 Replay determinism
Integer millisecond timestamps, server-assigned timestamps in command logs, deterministic ordering via `(game_time, monotonic_seq)`.

---

#### 8. Control plane
##### 8.1 Matchmaker
In-memory queues sharded by (region, rating bucket). Widening bands over time (±100 widening +50 per 5 s, cap ±400).

##### 8.2 Game log (ephemeral, in Redis)
Asynchronous batched pipeline to Redis. TTL = game lifetime. Used solely for game rebuilds upon node failure.

##### 8.3 Game Allocator
Stateless service, Redis-backed. Four jobs:
1. **Placement.** Selects least-loaded game node, writes `game:{id}`, issues `create_game`.
2. **Directory.** Resolves `game:{id}` and Crockford base32 room codes (~80 bits).
3. **Supervision.** Supervises node liveness via Redis lease (3 s TTL, 1 s renewal) and orders game rebuilds on failure.
4. **Room lobbies.** Owns `room:{code}` the same way it owns `game:{id}` — same Redis instance, same claim-then-place pattern. A room's seat-2 claim *is* a `create_game` trigger; nothing else about placement, directory-writing, or node selection differs from quick match (§12.3, §8.4).

##### 8.4 Room create/join and role assignment
##### 8.4.0 The reframe
A room is not a game with an empty seat. It is a **lobby that has not yet earned a game**. No game node, no `game_id`, no scheduler, nothing on the game tier exists until a second player claims the open seat. At that instant the flow becomes identical to quick match (§12.3): the allocator places a node, sends `create_game`, and both edges get a keyframe.

This keeps the game tier's invariant intact — it is only ever handed complete, two-player games — and it means an abandoned room costs one Redis key with a TTL, not a drained game-node slot.

##### 8.4.1 State machine
Transitions are one-way. `live` never reverts to `waiting`, and there is no path back into `waiting` from `ended`. Rejoining after `ended` gets a spectator hint pointed at the relay's post-game cache (or, once the room TTL expires, a plain "room closed").

##### 8.4.2 Redis record
TTL: **10 minutes while waiting**, refreshed to **game lifetime while live** (owning game node takes over the heartbeat, same pattern as `game:{id}` in §8.3), then a short **60 s grace TTL once ended** so a spectator mid-reconnect isn't dropped instantly.

##### 8.4.3 The claim is the whole design
Two people can hit join in the same millisecond. Exactly one of them must become player 2. This is a single atomic operation on the allocator, using the same Redis instance and ownership model as `game:{id}` (§8.3) — no new coordination primitive:
* **Succeeds** (key was empty) → caller is player 2. Allocator immediately does what it does for quick match: pick a node, write `game:{id}`, send `ctl.node.{node}: create_game`, flip `room:{code}.state` → `live`, set `game_id`.
* **Fails** (key already held) → caller is a spectator, full stop, forever, for this room. Return whatever's already in `room:{code}`: a `game_id` and relay hint if live, or "still waiting" if the state transition hasn't landed yet (rare race — client retries the join call once).

The host's own `/join` on their own code, and player 2 refreshing their own client, must be idempotent: check `seat2_uid == caller_uid` before treating a repeat call as a new claim. No seat is re-issued.

##### 8.4.4 API
One endpoint. The response tells the client its role — the client never decides this for itself, and never infers it from timing.

##### 8.4.5 Sequence — second joiner wins the seat
A third arrival a moment later gets `HSETNX` failure, reads `state=live`, and receives `role=spectator, relay_hint` — no different from resolving `GET /v1/games/{id}/watch` in §5.1.

##### 8.4.6 Spectators who arrive during waiting
There is no `game_id` yet to hand them. Two acceptable options, pick one at implementation time — this doc doesn't need to force it:
* **Poll**: they hold the room code and re-issue `/join`, which keeps returning spectator, `state=waiting` until the seat is claimed.
* **Park and push**: the allocator keeps a short-lived list of waiting-spectator session ids on the room record and pushes a `relay_hint` control message to each when state flips to `live`.

Either way, no `spec.*` bus subject is created for a room nobody has claimed as live (§6.3) — spectators-before-the-game-exists never touch the bus.

##### 8.4.7 Non-negotiable invariant — no mid-game promotion
**A spectator is never promoted to a player, under any circumstance, including a disconnect by one of the two players.**

This isn't a policy choice made for simplicity's sake — it's forced by three things already in the design, and violating it would cost all three:

| Reason | Section |
|---|---|
| The game log records `(seq, game_time, session_id, ...)` per command. Swapping in a new `session_id` mid-game makes the rebuild-by-replay path (§8.2, §12.7) reconstruct a game that never happened. | §8.2 |
| Elo (§8.1, §12.5) is computed for the two `players[]` written at `create_game`. A promoted spectator has no matchmaking context — no rating band, no opponent consent — and rating the result would be meaningless. | §8.1, §12.5 |
| A dropped player already has a defined, working outcome: the pause-by-offset mechanism (§7.5) and the 10 s reconnect window (§12.6, Appendix A). Games are 60–90 s long — forfeiting a paused player who never returns is the correct and sufficient answer. Promotion would be solving a problem that doesn't exist. | §7.5, §12.6 |

If a disconnected player never reconnects within the pause window, the game ends by forfeit exactly as §12.6 already specifies. The room itself can be reused for a fresh room the same host may create — a **new game**, not a continuation — but that is a product decision outside this document's scope, not a server-design one.

---

#### 9. Auth tier
Separate deployment using scrypt ($N=2^{13}, r=8, p=1$). Issues Ed25519 JWTs (15 min access TTL, 30 day refresh TTL). Gateways verify JWTs locally using cached JWKS.

---

#### 10. Spectator relay tier
Two-level tree (L1 to L2). Caches keyframes every 10 s (`kf.{shard}.{game_id}`). Serves viewers with ≤1 s delay.

---

#### 11. Wire protocol
Language-neutral JSON schema. Positional array delta encoding (~105 B for moves). Sparse wire: zero frames during idle periods. WebSocket ping/pong for socket liveness.

---

#### 12. Data flows
* **12.1 Register & 12.2 Login:** Regionally sharded with global identity table.
* **12.3 Quick match:** In-memory queue matching with widening rating bands.
* **12.4 Move round trip:** see below.
* **12.5 Game end -> Elo:** Atomic Postgres transaction with `game_results` primary key acting as idempotency key.
* **12.6 Disconnect -> pause -> reconnect:** 10 s total pause budget per player per game.
* **12.7 Node failure -> game rebuild:** Allocator detects lease expiration (3 s) and assigns survivor node to rebuild game state from Redis logs (~4-6 s total stall).

##### 12.4 Move round trip (expanded)

| # | Hop | Work done |
|---|---|---|
| 1 | Client → edge | Keypress serialized to a WS frame. |
| 2 | Edge | Token bucket (10/s, burst 20); envelope parse only, never payload (I1); look up cached `(shard, node_id)` — no directory call on the hot path. |
| 3 | Edge → bus | Publish to `cmd.{shard}.{node_id}`, `shard = hash(game_id) mod 8`. |
| 4 | Bus → node | Delivered to the single subscriber on that subject. |
| 5 | Node | Arrival timestamp assigned; routed to shard goroutine by `hash(game_id) mod S`; validated against authoritative state; discrete events scheduled (§7.2). |
| 6 | Node → bus | 1–3 delta frames, each serialized once (§7.4), published to `edge.{edge_id}` per distinct edge and to `spec.{shard}.{game_id}` if the game is watched. |
| 7 | Bus → edges → clients | Edges demux frames onto sockets. |

The path is now symmetric: **edge → bus → node → bus → edge**. Nothing on it holds a cross-tier connection.

**What the extra hop costs.** One additional intra-region NATS traversal, budgeted at ~0.4 ms p50 and ~2 ms p99. Against the 120 ms own-screen SLO (§3.3) that is under 2% at p99. It is measurement #8 in §17, and the number is an assumption until it is measured.

**What it buys — fairness under contention.** Both players' commands for a game hash to the same bus shard and arrive on the same node subject, so the last leg before arbitration is a single queue rather than two independent TCP streams. Kung-Fu Chess has no turns: the case that decides games is two pieces racing for the same cell, resolved by whichever command the arbiter stamps first. Under the direct-dial topology that ordering could be decided by which player's edge→node connection happened to be less congested at that instant — an asymmetry with no upper bound, invisible to both players and to the server.

This does not equalize the two paths. The edge→bus leg is still per-player and still carries independent queueing. What it removes is the unbounded tail: two long-lived connections with independent congestion state can diverge by tens of milliseconds, while two publishes into one shard converge on a common queue whose depth is a metric the design already exports (§19).

**What it costs structurally.** Bus shard loss becomes a bidirectional outage rather than an outbound one — see §14.

#### 13. Capacity
Fleet total ~650 machines at peak 10M concurrent users. Game tier: 90 nodes (16 vCPU, 32 GB RAM) holding 20,000 games each (density set by rebuild time budget, not CPU).

**Connection topology.** An E×G edge-to-node mesh is replaced by E+G connection sets to the bus. Stated honestly: at this fleet size the mesh would be a few thousand sockets, which is not itself a capacity problem. The cost it removes is *churn and coupling*, not sockets — the mesh re-forms on every edge autoscale event and on every 2-minute game-node drain (§2.2), and every deploy is a drain. Under the bus topology the edge tier tracks no game-node membership, holds no node health state, and duplicates none of the allocator's directory; the game tier accepts no inbound connections at all. Both tiers scale on their own signal without either observing the other.

---

#### 14. Failure analysis
All recovery paths (reconnect, rebuild, backpressure, gap detection) resolve via keyframe delivery. PostgreSQL and Redis log failures do not disrupt live gameplay.

**Bus shard loss — changed by §6.3.** Losing a shard now severs both directions for the ~1/8 of regional games hashed to it: commands stop arriving *and* frames stop leaving. This is worse than the outbound-only failure it replaces, and it needs an explicit answer, because a node whose commands have stopped cannot distinguish that from two players who have stopped moving — and the engine keeps advancing on real time either way, producing games that play on without their players.

The node cannot detect this: it has no view of socket state. **The edge is the authority.** An edge that loses its bus shard closes the affected player sockets. The node observes those closures through the existing session path and enters pause-by-offset (§7.5); if the shard does not recover inside the 10 s window, the game ends by forfeit exactly as §12.6 specifies.

Blast radius: 1/8 of a region's games, degraded to an already-designed outcome (pause, then forfeit) rather than to a silent desync. Detection latency is bounded by the edge's bus-connection timeout, which must therefore be set well under the 10 s pause budget — 2 s is the working value.

---

#### 15. Open questions — resolved
* **15.1 Client-side prediction:** Pure interpolation with local input affordances. Move delay kept at 1000 ms.
* **15.2 Repeated pauses:** Fixed 10-second total pause budget per player per game.
* **15.3 Retention:** 30 days of `game_results` in daily partitions, dropped via `DROP PARTITION`.
* **15.4 Abuse:** 10 cmd/socket/s rate limit, per-game timing histogram, queue segregation.
* **15.5 Protocol versioning:** Major version negotiated at handshake, additive-only minor changes.

---

#### 16. What was traded away
1. Binary wire format (traded for simpler tooling/debugging).
2. Move history and replays (traded for reduced storage/DB load).
3. Durable game log (traded for high throughput in Redis).
4. Cross-region quick match (traded to achieve latency SLO).
5. Spectator interactivity (traded to offload game tier).
6. Client-side prediction (traded to maintain absolute server authority).
7. One-session-per-user enforcement (traded for pause-driven device switching).
8. Per-game process isolation (traded for high density per node).
9. Strong rating consistency (traded for async PG write path).
10. Bot resistance (traded for scope reduction).
11. Live migration of games (traded for 2-minute drain deploys).
12. Global consistency in matchmaking (traded for in-memory queue speed).
13. Direct edge→node command dialing (traded ~0.4 ms p50 of added latency for a shared arbitration queue per game, symmetric hop counts, and zero cross-tier membership tracking — §12.4, §13). The bill is a bidirectional blast radius on bus shard loss (§14).

---

#### 17. What must be measured before any of this is trusted
1. Frames/sec/game in real play.
2. Bytes/microseconds per delta encode.
3. Rebuild time vs. games per node density.
4. Memory per live game under load.
5. NATS throughput under subject churn (~143k subjects) **and under the added 1.43M/s of inbound command publishes** (§2.1).
6. End-to-end p99 command-to-render latency.
7. KDF wall time on actual target instances.
8. **p99 of the inbound bus hop alone**, edge-publish to node-arrival. §12.4 assumes ~2 ms. Above roughly 10 ms the fairness argument stops paying for itself and the direct-dial topology should be reconsidered.
9. **Ordering spread under contention** — for two commands racing for the same cell, the distribution of arbiter-stamp deltas versus the distribution of client keypress deltas. This is the measurement that actually tests the fairness claim in §12.4; #8 only tests its price.

---

#### 18. Migration path
Phases 0 to 7: from prototype instrumentation to delta protocol, discrete-event scheduler, schema generation, tier separation, Go engine rewrite, spectator relays, and database sharding.

---

#### 19. Observability & 20. Deployment & 21. Summary
Full Prometheus metric exposition without high-cardinality labels, canary game SLI tracking, Docker Compose development harness, Kubernetes deployment with 150 s preStop drain hooks on game nodes.

---

#### Appendix A — Constants

| Constant | Value | Notes |
|---|---|---|
| DEFAULT_MOVE_DELAY_MS | 1000 | per square; not shortened (§15.1) |
| Long rest | 2 × move delay | |
| Short rest (jumps) | 1 × move delay | |
| MATCH_ELO_RANGE | ±100 | widens +50 per 5 s, cap ±400 |
| K_FACTOR | 32 | flat, no provisional period |
| DEFAULT_RATING | 1200 | |
| Reconnect / pause window | 10,000 ms | total per player per game (§15.2) |
| Room lobby TTL (waiting) | 10 min | §8.4.2 |
| Room record TTL (ended) | 60 s | grace window for late spectators (§8.4.2) |
| Command rate limit | 10/s, burst 20 | per socket |
| Frame emission cap | 1 per game per 10 ms | safety limiter |
| Relay keyframe cadence | 10 s | internal only, watched games only |
| Access token TTL | 15 min | not enforced mid-game |
| Refresh token TTL | 30 d | rotated, reuse-detected |
| KDF | scrypt N=2^13, r=8, p=1 | ~25 ms (§9) |
| Room code | 16 chars Crockford base32 | ~80 bits |
| Node lease TTL | 3 s | renewed at 1 s |
| Game-node density | 20,000 games | bounded by rebuild time, not CPU (§13.2) |
| Bus shards | 8 per region | hash(game_id) mod 8 |
| Edge bus-connection timeout | 2 s | must stay well under the 10 s pause budget (§14) |
| Inbound command hop budget | ~0.4 ms p50 / ~2 ms p99 | assumption until measurement #8 (§12.4, §17) |
| Game-result retention | 30 days | daily partitions (§15.3) |

---

#### Appendix B — Subject and key namespaces
* **NATS Subjects:** `cmd.{shard}.{node_id}` (inbound player commands, §6.3), `ctl.game.{shard}.{node_id}`, `edge.{edge_id}`, `spec.{shard}.{game_id}`, `kf.{shard}.{game_id}`, `ctl.alloc`, `ctl.node.{node_id}`, `evt.result`.
* **Redis Keys:** `sess:{user_id}`, `game:{id}`, `room:{code}`, `node:{id}`, `log:{game_id}`.

---

#### Appendix C — Deliverable checklist

| Required | Section |
|---|---|
| Component / tier diagram | §4 |
| Flow: register | §12.1 |
| Flow: login | §12.2 |
| Flow: create / join room | **§8.4** |
| Flow: quick match | §12.3 |
| Flow: move round trip | §12.4 |
| Flow: spectator join | §10.2 |
| Flow: disconnect / pause / reconnect | §12.6 |
| Flow: game end → Elo | §12.5 |
| Flow: node failure → game rebuild | §12.7 |
| Capacity math per tier, with assumptions | §2, §13 |
| Delta protocol: frame shapes, keyframe cadence, delta contents | §11 |
| Failure analysis: user impact and blast radius | §14 |
| Explicit list of what was traded away and why | §16 |
