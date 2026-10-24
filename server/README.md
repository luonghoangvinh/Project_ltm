# Battleship Game Server (C / POSIX / SQLite / OpenSSL)

Production-ready, multi-threaded C server for the Battleship network game project.

## Architecture & Features

- **POSIX TCP Socket Server**: Non-blocking friendly, line-buffered framing (`\n`-delimited JSON), resilient against stream fragmentation and partial reads.
- **Multi-threaded Worker Architecture**: Thread-per-client model (`pthread`) with robust mutex locking across global shared states.
- **Protocol & Framing**: Full JSON messaging supporting Login, Register, Matchmaking, Ship Placement, Turn-based Battleship, Surrender, Draw Agreement, History, and Move Replays.
- **Authentication & Security**: SHA-256 password hashing via OpenSSL (`openssl/sha.h`), high-entropy session tokens, and input validation to guard against injection and buffer overflows.
- **Database Persistence**: SQLite3 with WAL mode, prepared statements, and transactions for users, matches, and replay moves.
- **ELO Rating System**: Standard competitive rating algorithm ($K=32$, floor of 100) automatically updating after each match.
- **Safe Signal & Disconnect Handling**: `SIGPIPE` ignored; graceful shutdown on `SIGINT` / `SIGTERM`; automatic match forfeit detection on sudden client disconnection.

---

## Directory Structure

```text
server/
├── include/
│   ├── common.h          # Global constants, enums, game definitions
│   ├── protocol.h        # Protocol framing and network buffer helpers
│   ├── network.h         # ClientInfo and ServerContext declarations
│   ├── auth.h            # Authentication and SHA-256 declarations
│   ├── session.h         # Session token generation and lifecycle
│   ├── matchmaking.h     # Challenge and matchmaking flow
│   ├── game.h            # Board, Ship, and Game state machine
│   ├── database.h        # SQLite database access layer
│   ├── rating.h          # ELO rating formulas
│   └── cjson/            # Bundled cJSON library
│       ├── cJSON.h
│       └── cJSON.c
├── src/
│   ├── main.c            # CLI args, signal handling, entry point
│   ├── network/
│   │   ├── server.c      # Socket bind/listen/accept loop
│   │   ├── client_handler.c # Thread dispatch, JSON parser, game handlers
│   │   └── protocol.c    # Frame reassembly, send/recv loops
│   ├── auth/
│   │   ├── auth.c        # Registration, login, SHA-256
│   │   └── session.c     # Session storage and token lookup
│   ├── matchmaking/
│   │   └── matchmaking.c # Challenge tracking and match creation
│   ├── game/
│   │   ├── board.c       # 10x10 board, placement validation, shot processing
│   │   ├── ship.c        # Ship counts, sizes, readiness checks
│   │   ├── game.c        # Turn sequencing, surrender, draw, ELO trigger
│   │   └── replay.c      # Move serialization for replay
│   ├── database/
│   │   └── database.c    # SQLite prepared queries and tables
│   └── rating/
│       └── rating.c      # ELO delta calculation
├── sql/
│   └── schema.sql        # SQLite table schema definitions
├── config/
│   └── server.example.conf # Configuration reference
├── Makefile              # GCC build script
└── README.md             # Documentation
```

---

## Prerequisites (Ubuntu 22.04 LTS)

Install the necessary development libraries and tools:

```bash
sudo apt-get update
sudo apt-get install -y build-essential libsqlite3-dev libssl-dev curl
```

---

## Building the Server

From the `server/` directory:

```bash
# Build binary
make

# Or fetch dependencies and build
make deps
make
```

The resulting binary will be placed at `server/build/battleship_server`.

To clean build artifacts:
```bash
make clean
```

---

## Running the Server

```bash
# Run with default settings (port 8888, db: battleship.db)
./build/battleship_server

# Or specify custom port and database path
./build/battleship_server --port 9000 --db custom_game.db

# Or use make run
make run
```

---

## Command Line Arguments

- `--port, -p <number>`: TCP port to bind and listen on (default: `8888`).
- `--db, -d <path>`: SQLite database file location (default: `battleship.db`).
- `--help, -h`: Display usage information.

---

## Network Protocol Summary

All messages are JSON objects formatted on a single line ending in `\n`.

### Authentication
- `LOGIN`: `{"type":"LOGIN","username":"alice","password":"secret"}`  
  $\to$ `{"type":"LOGIN_OK","session_token":"...","username":"alice","elo":1200}` or `{"type":"ERROR","message":"..."}`
- `REGISTER`: `{"type":"REGISTER","username":"alice","password":"secret"}`  
  $\to$ `{"type":"REGISTER_OK","message":"..."}` or `{"type":"ERROR","message":"..."}`
- `LOGOUT`: `{"type":"LOGOUT","session_token":"..."}`  
  $\to$ `{"type":"LOGOUT_OK"}`

### Lobby & Matchmaking
- `LIST_PLAYERS`: `{"type":"LIST_PLAYERS","session_token":"..."}`  
  $\to$ `{"type":"PLAYER_LIST","players":[{"username":"bob","elo":1200,"status":"IN_LOBBY"}]}`
- `CHALLENGE`: `{"type":"CHALLENGE","session_token":"...","target":"bob"}`  
  $\to$ target receives `{"type":"CHALLENGE","from":"alice","match_id":"uuid"}`
- `CHALLENGE_REPLY`: `{"type":"CHALLENGE_REPLY","session_token":"...","match_id":"uuid","accept":true}`  
  $\to$ both receive `{"type":"MATCH_FOUND","match_id":"uuid","opponent":"...","opponent_elo":1200,"you_go_first":true}`

### In-Game
- `PLACE_SHIP`: `{"type":"PLACE_SHIP","session_token":"...","match_id":"uuid","ship_id":0,"row":0,"col":0,"direction":0}`  
  $\to$ `{"type":"PLACE_SHIP_OK","ship_id":0}`
- `READY`: `{"type":"READY","session_token":"...","match_id":"uuid"}`  
  $\to$ `{"type":"READY_OK"}` (when both ready, first player receives `{"type":"YOUR_TURN","match_id":"uuid"}`)
- `FIRE`: `{"type":"FIRE","session_token":"...","match_id":"uuid","row":4,"col":5}`  
  $\to$ shooter receives `{"type":"FIRE_RESULT","row":4,"col":5,"result":"HIT","sunk":false,"ship_size":0,"game_over":false,"winner":""}`  
  $\to$ opponent receives `{"type":"OPPONENT_FIRED","row":4,"col":5,"result":"HIT","sunk":false,"ship_size":0}`  
  $\to$ active player receives `{"type":"YOUR_TURN","match_id":"uuid"}`
- `SURRENDER`: `{"type":"SURRENDER","session_token":"...","match_id":"uuid"}`  
  $\to$ `{"type":"GAME_OVER","winner":"...","reason":"SURRENDER","elo_change":...,"new_elo":...}`
- `DRAW_OFFER` & `DRAW_REPLY`: Agree or decline mutual draw.

### History & Replay
- `HISTORY`: `{"type":"HISTORY","session_token":"...","limit":10}`  
  $\to$ `{"type":"HISTORY_DATA","matches":[...]}`
- `REPLAY`: `{"type":"REPLAY","session_token":"...","match_id":"uuid"}`  
  $\to$ `{"type":"REPLAY_DATA","match_id":"uuid","moves":[...]}`
