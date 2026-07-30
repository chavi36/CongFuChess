# Kung-Fu Chess — Architecture Map

This document is a flow-oriented architecture description derived from the Kung-Fu Chess server spec. It follows the same structure as the server design: each component receives something, transforms it, and passes it to the next component.

---

## 1. Core architecture principle

The architecture is built around one main rule:

- The game node is the only authority for rules and game state.
- Clients never decide the game outcome.
- The system is layered in one direction:
  - model ← rules/events ← real_time ← game_engine

That means every request and every state update eventually flows through the same path:

- client input
- edge gateway
- bus
- game node
- edge/relay/result writer
- storage or client output

---

## 2. Architecture by layer

### 2.1 Client layer

The client is the entry point for all user interaction.

- What it sends:
  - HTTP requests for login, registration, room actions, matchmaking
  - WebSocket commands for moves and game updates
- What it becomes:
  - authenticated requests
  - game commands
  - game frame updates
- What happens next:
  - HTTP goes to the API Gateway
  - WS commands go to the Player Gateway
  - game frames come back from the gateway or relay

---

### 2.2 API Gateway

The API Gateway handles non-real-time operations.

- Receives:
  - register requests
  - login requests
  - refresh requests
  - profile and history requests
  - room create/join requests
  - quick-match enqueue requests
- Turns them into:
  - authentication checks
  - room operations
  - matchmaking queue actions
  - allocator instructions
- Passes next to:
  - Auth Service for identity and tokens
  - Matchmaker for quick-match queueing
  - Allocator for room and game placement

---

### 2.3 Auth Service

The Auth Service is a separate service because password hashing must not compete with game simulation.

- Receives:
  - user credentials
  - token refresh requests
- Turns them into:
  - hashed passwords
  - issued access and refresh tokens
  - verified identity for API and gateway requests
- Passes next to:
  - API Gateway and Player Gateway for authentication decisions

---

### 2.4 Player Gateway (WebSocket Edge)

The Player Gateway is the socket-facing edge tier.

- Receives:
  - WebSocket commands from players
  - heartbeat and session traffic
- Turns them into:
  - envelope parsing
  - rate-limit checks
  - command publication to the bus
- Passes next to:
  - NATS bus
  - then eventually to the authoritative game node

Important behavior:
- It does not talk directly to the game node.
- It only holds player sockets.
- It publishes commands to the bus and later receives frames back.

---

### 2.5 Matchmaker

The Matchmaker handles finding opponents for quick play.

- Receives:
  - player queue requests
- Turns them into:
  - matchmaking candidates inside rating buckets
  - a match decision when enough players exist
- Passes next to:
  - Game Allocator for placement and room/game creation

Its logic is sharded by region and rating band.

---

### 2.6 Game Allocator

The Allocator is the control-plane component that chooses where a game should live.

- Receives:
  - room creation requests
  - room join requests
  - quick-match match outcomes
- Turns them into:
  - a chosen game node
  - a new game record
  - room state transitions
  - create_game commands
- Passes next to:
  - Redis for storage and coordination
  - Game Node via control commands

The allocator performs four jobs:
1. Placement
2. Directory lookup
3. Supervision / node health
4. Room lobbies

---

### 2.7 Redis

Redis is the coordination and ephemeral state store.

- Receives:
  - session state
  - room state
  - game directory records
  - game logs for rebuild
- Turns them into:
  - fast lookup and coordination values
  - temporary state used by gateways, allocator, and node recovery
- Passes next to:
  - gateways for session routing
  - allocator for placement and room state
  - game node for rebuild replay

Redis stores things such as:
- session information
- room lobby state
- game placement metadata
- ephemeral game logs

---

### 2.8 NATS bus

The NATS bus carries real-time traffic between tiers.

- Receives:
  - player commands from the edge gateway
  - game frames from the game node
- Turns them into:
  - routed command delivery
  - routed frame delivery
- Passes next to:
  - game node for inbound commands
  - player gateway and spectator relay for outbound frames

There are two important directions:
- inbound path: edge → bus → game node
- outbound path: node → bus → edge/relay

---

### 2.9 Game Node

The Game Node is the heart of the system and the authoritative simulation engine.

- Receives:
  - commands from the bus
  - game creation instructions from the allocator
- Turns them into:
  - authoritative state changes
  - move execution
  - capture and end events
  - frames to send to players and spectators
- Passes next to:
  - NATS bus for outbound frames
  - Result Writer for terminal events
  - Redis for game logs during runtime and rebuild

The game node is the only place where game rules are evaluated.

---

### 2.10 Spectator Relay

The Spectator Relay handles read-only game views for watchers.

- Receives:
  - game frames from the bus
- Turns them into:
  - spectator streams with low latency
  - keyframe-based recovery for viewers
- Passes next to:
  - spectator clients

It does not participate in game logic and does not send player input back into the game tier.

---

### 2.11 Result Writer

The Result Writer handles the post-game outcome pipeline.

- Receives:
  - terminal events from the game node
- Turns them into:
  - durable result rows
  - Elo updates
- Passes next to:
  - PostgreSQL for storage

---

### 2.12 PostgreSQL

PostgreSQL stores durable business data.

- Receives:
  - user data
  - game results
- Turns them into:
  - persistent records for accounts and completed games
- Passes next to:
  - read APIs and reporting surfaces

It is not on the hot real-time path.

---

## 3. End-to-end flows

### 3.1 Register and login flow

1. Client sends HTTP auth request.
2. API Gateway forwards it to Auth Service.
3. Auth Service validates or issues credentials and tokens.
4. Gateway returns a session/token response.
5. Client continues with room or game actions.

Flow summary:
- client → API Gateway → Auth Service → client

---

### 3.2 Create room flow

1. Client sends room creation request.
2. API Gateway forwards it to the Allocator.
3. Allocator creates a waiting room record in Redis.
4. Room state becomes waiting.
5. Host receives the room code and role.

Flow summary:
- client → API Gateway → Allocator → Redis → client

---

### 3.3 Join room flow

1. Client sends join request for a room.
2. API Gateway sends the request to the Allocator.
3. Allocator checks whether the second seat is still open.
4. If the second seat is claimed:
   - a game is created
   - a game node is selected
   - a create_game event is issued
5. If the seat is not available:
   - the caller becomes a spectator
   - the relay or room state is returned

Flow summary:
- client → API Gateway → Allocator → Redis/Node → client

---

### 3.4 Quick-match flow

1. Client queues for a match.
2. Matchmaker places the player into a rating-bucket queue.
3. When a match is found, Allocator selects a game node.
4. A new game is created and assigned to that node.
5. The game begins.

Flow summary:
- client → API Gateway → Matchmaker → Allocator → Game Node

---

### 3.5 Move round-trip flow

1. Player sends a move command over WebSocket.
2. Player Gateway validates the envelope and rate limit.
3. The command is published to the NATS bus.
4. The bus delivers it to the correct game node.
5. The game node validates the move and updates authoritative state.
6. The game node emits one or more frames.
7. The frames go back over the bus to the relevant edges and relay.
8. The clients receive the update and render it.

Flow summary:
- player → Player Gateway → NATS → Game Node → NATS → edge/relay → client

---

### 3.6 Spectator flow

1. A watcher joins a live game.
2. The relay subscribes to the spectator subject.
3. The game node emits frames for watched games.
4. The relay forwards those frames to viewers.

Flow summary:
- Game Node → NATS → Spectator Relay → spectator clients

---

### 3.7 Disconnect and pause flow

1. A player disconnects or loses a session.
2. The node detects the loss of the session.
3. The game enters pause-by-offset.
4. The player has a limited reconnect window.
5. If the player returns in time, gameplay resumes.
6. If not, the game ends by forfeit.

Flow summary:
- session loss → Game Node → pause logic → reconnect window → outcome

---

### 3.8 Node failure and rebuild flow

1. A game node becomes unhealthy.
2. The allocator detects the loss via lease supervision.
3. A new node is selected.
4. The game log is replayed from Redis.
5. The rebuilding node resumes game state.
6. The first keyframe repoints the edge caches.

Flow summary:
- node failure → allocator → Redis replay → new Game Node → keyframe → clients

---

### 3.9 Game end flow

1. The game reaches a terminal state.
2. The game node emits a terminal event.
3. Result Writer consumes it.
4. Result Writer writes the durable result and applies Elo.
5. PostgreSQL stores the final game outcome.

Flow summary:
- Game Node → Result Writer → PostgreSQL

---

## 4. What turns into what

Here is the system as a simple transformation map:

- User action → API request or WebSocket command
- API request → auth check / room action / matchmaking action
- Matchmaking action → match candidate
- Match candidate → allocator placement decision
- Placement decision → game creation on a game node
- Game command → authoritative simulation event
- Simulation event → delta frame
- Delta frame → edge delivery and spectator delivery
- Terminal event → durable result row and Elo update

---

## 5. The architecture in one sentence

The system is a layered real-time architecture where:
- the API and auth layers handle identity and lobby operations,
- the matchmaking and allocator layers decide where games live,
- the game node is the only authority for rules and state,
- the bus carries commands and frames,
- the relay serves spectators,
- and Redis/PostgreSQL hold the coordination and durable data.

---

## 6. Simple dependency map

```text
Clients
  ├─ HTTP requests → API Gateway → Auth Service / Matchmaker / Allocator
  └─ WS commands → Player Gateway → NATS → Game Node

Allocator
  ├─ uses Redis for coordination and room/game records
  └─ creates or places games on Game Nodes

Game Node
  ├─ receives commands from NATS
  ├─ writes logs to Redis
  ├─ emits frames to NATS
  └─ emits terminal events to Result Writer

Result Writer
  └─ writes to PostgreSQL

Spectator Relay
  └─ consumes watched game frames from NATS
```
