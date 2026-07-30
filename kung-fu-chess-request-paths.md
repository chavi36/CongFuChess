# Kung-Fu Chess — Request Paths and Execution Flow

This document describes every major request path in the architecture and shows what each request does step by step.

---

## 1. Login Request Path

### Request
- Client sends login credentials over HTTP.

### Path
1. Client → API Gateway
2. API Gateway → Auth Service
3. Auth Service validates credentials
4. Auth Service issues access/refresh tokens
5. API Gateway returns the auth response to the client

### What happens
- The system verifies the user identity.
- A session is established.
- The client receives authentication material for later requests.

### End result
- The client is authenticated and can continue to rooms, matchmaking, or game operations.

---

## 2. Register Request Path

### Request
- Client sends registration data.

### Path
1. Client → API Gateway
2. API Gateway → Auth Service
3. Auth Service creates the account and hashes credentials
4. Auth Service returns success or error
5. API Gateway returns the response to the client

### What happens
- The user account is created.
- Passwords are stored securely using the configured hashing method.

### End result
- The user becomes a valid account in the system.

---

## 3. Create Room Request Path

### Request
- Client calls the room creation endpoint.

### Path
1. Client → API Gateway
2. API Gateway → Allocator
3. Allocator creates a room lobby record
4. Allocator writes the room state to Redis
5. Allocator returns room code and role information to the client

### What happens
- A waiting room is created.
- The host becomes the room owner.
- The room remains inactive until a second player claims the seat.

### End result
- A lobby exists and is ready for a second participant.

---

## 4. Join Room Request Path

### Request
- Client calls the join-room endpoint.

### Path
1. Client → API Gateway
2. API Gateway → Allocator
3. Allocator checks room state and seat availability
4. If the second seat is free:
   - Allocator claims the seat
   - Allocator selects a Game Node
   - Allocator writes game metadata to Redis
   - Allocator sends create_game to the chosen node
   - Room state changes from waiting to live
5. If the second seat is already taken:
   - the caller becomes a spectator
   - the response includes relay or room-state information
6. Allocator returns the result to the client

### What happens
- The room transitions into a live game or remains a spectator path.
- The system assigns the caller a role.

### End result
- The client either becomes player 2 or joins as a spectator.

---

## 5. Quick Match Request Path

### Request
- Client requests a quick match.

### Path
1. Client → API Gateway
2. API Gateway → Matchmaker
3. Matchmaker evaluates rating bucket and queue state
4. Matchmaker finds or waits for a compatible opponent
5. Matchmaker passes the result to Allocator
6. Allocator selects a Game Node
7. Allocator creates the game and issues create_game
8. The game starts on the assigned node

### What happens
- Two players are paired.
- A game is created and assigned to a game node.

### End result
- A live game is created for the matched players.

---

## 6. Move Command Request Path

### Request
- Player sends a move over WebSocket.

### Path
1. Client → Player Gateway
2. Player Gateway parses the envelope
3. Player Gateway validates rate limit
4. Player Gateway publishes the command to the NATS bus
5. NATS delivers the command to the correct Game Node
6. Game Node validates the move against authoritative state
7. Game Node updates the game state
8. Game Node emits one or more frames
9. NATS delivers frames to the edge and relay
10. Player Gateway forwards frames to the appropriate client sockets

### What happens
- The move is accepted or rejected.
- If accepted, the game state changes.
- The update is sent back to the current players and spectators.

### End result
- The client sees the move reflected on screen.

---

## 7. Spectator Join Request Path

### Request
- A spectator requests to watch a live game.

### Path
1. Client → Player Gateway or API Gateway depending on the interface
2. The system resolves the game or room state
3. The Spectator Relay subscribes to the relevant watched-game stream
4. The Game Node emits frames for the watched game
5. The relay forwards those frames to the spectator client

### What happens
- The spectator receives a read-only stream of the ongoing game.
- The relay does not send input back to the game node.

### End result
- The spectator views the live match.

---

## 8. Game Frame Delivery Path

### Request
- Not a user request, but the system’s internal delivery path for updates.

### Path
1. Game Node produces a frame
2. Frame is published to the NATS bus
3. NATS distributes it to:
   - player edges for connected players
   - spectator relay for watchers
4. Edge and relay forward the frame to clients

### What happens
- The latest authoritative game state is sent to all relevant viewers.

### End result
- All connected participants receive the latest state update.

---

## 9. Disconnect and Pause Path

### Request
- A player disconnects or loses a session.

### Path
1. Player loses connection or session continuity
2. Player Gateway detects session loss or heartbeat failure
3. The Game Node enters pause-by-offset mode
4. The game waits for a reconnect window
5. If the player returns in time, the game resumes
6. If not, the game ends by forfeit

### What happens
- The game pauses instead of terminating immediately.
- The system gives the player a short reconnect window.

### End result
- The game either resumes or ends by forfeit.

---

## 10. Node Failure and Rebuild Path

### Request
- A game node becomes unhealthy or unreachable.

### Path
1. The allocator supervises node liveness through Redis lease tracking
2. A node failure is detected
3. The allocator selects a replacement node
4. The new node replays the game log from Redis
5. The rebuilding node resumes the game from the replayed state
6. The first keyframe is sent to re-point edges and clients

### What happens
- The system recovers the game on a new node with minimal disruption.

### End result
- The game continues after a rebuild.

---

## 11. Game End Path

### Request
- The game reaches a terminal state.

### Path
1. Game Node detects the end condition
2. Game Node emits a terminal event
3. Result Writer consumes the terminal event
4. Result Writer writes the result to PostgreSQL
5. Elo updates are applied in the result-processing flow

### What happens
- The game outcome is recorded durably.
- Player ratings are updated.

### End result
- The completed game is persisted and rated.

---

## 12. Session Heartbeat Path

### Request
- A client or gateway sends a heartbeat.

### Path
1. Client → Player Gateway
2. Gateway updates the session state in Redis
3. Redis stores the latest active session mapping
4. The system uses this to detect stale sessions or force reconnect behavior

### What happens
- The server knows which sessions are live.

### End result
- The system can safely route or invalidate sockets.

---

## 13. Request Path Summary

Here is the architecture in compact form:

- Authentication request: client → API Gateway → Auth Service
- Room creation: client → API Gateway → Allocator → Redis
- Room join: client → API Gateway → Allocator → Redis / Game Node
- Quick match: client → API Gateway → Matchmaker → Allocator → Game Node
- Move command: client → Player Gateway → NATS → Game Node → NATS → client/relay
- Spectator stream: Game Node → NATS → Spectator Relay → spectator client
- Game end: Game Node → Result Writer → PostgreSQL

---

## 14. Simple Mental Model

If you want to think about the system as a request pipeline, use this rule:

- HTTP requests mostly go through the control plane.
- WebSocket/game traffic goes through the real-time plane.
- The game node is the authoritative center of real-time decisions.
- Redis and PostgreSQL are the persistence and coordination layers.
