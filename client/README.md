# Battleship Online - Pygame Client

A modern, full-featured desktop client for the Battleship online 1v1 multiplayer game built with **Python 3.8+** and **Pygame 2.x**.

---

## Features

- **Asynchronous TCP Socket Networking**: Dedicated daemon thread handles TCP streaming, splitting newline-delimited JSON chunks and pushing into a thread-safe `queue.Queue`.
- **Non-blocking UI Thread**: 60 FPS Pygame main loop never blocks on network I/O.
- **Modern Dark UI**: Polished cyber-naval aesthetics with custom styling, modal dialogs, and toast notifications.
- **Interactive Ship Deployment**:
  - Drag/click placement on 10x10 battlegrid.
  - Orientation toggle (`R` key or Rotate button).
  - Real-time validity preview (green = valid, red = collision/out of bounds).
  - Quick Randomize button.
- **Combat Arena**:
  - Dual 10x10 boards: Your Fleet & Enemy Radar.
  - Turn indicators, missile targeting, and combat logs.
  - Draw offers and surrender confirmation modals.
- **Match History & Replay Viewer**:
  - Review past matches and ELO rating changes.
  - Interactive turn-by-turn replay with Play/Pause, step controls, and last move highlights.

---

## Requirements

- Python 3.8 or higher (supports Python 3.10, 3.11, 3.12, 3.13, 3.14)
- `pygame >= 2.0.0` or `pygame-ce >= 2.5.0`

### Installation

```bash
cd project_ltm
pip install -r client/requirements.txt
```

*(Note for Python 3.14+: install `pip install pygame-ce`)*

---

## Running the Client

### Default (connects to `127.0.0.1:8888`)

```bash
python -m client.main
```

### Custom Host and Port via CLI Arguments

```bash
python -m client.main --host 192.168.1.50 --port 8888
```

### Configuration via Environment Variables

The client also checks environment variables if CLI arguments are not specified:

- `BATTLESHIP_HOST`: Server IP / hostname (default: `127.0.0.1`)
- `BATTLESHIP_PORT`: Server port (default: `8888`)

On Windows PowerShell:
```powershell
$env:BATTLESHIP_HOST="127.0.0.1"
$env:BATTLESHIP_PORT="8888"
python -m client.main
```

---

## Controls

| Action | Control |
|---|---|
| Rotate Ship (Placement Screen) | `R` key or **Rotate** button |
| Target & Fire Missile | Left-click on enemy radar cell |
| Switch Input Fields (Login/Register) | `Tab` key |
| Submit Form | `Enter` key |
| Scroll Player/Match Lists | Mouse Wheel |
| Replay Step Prev / Next | Left / Right Arrow keys |
| Replay Play / Pause | Spacebar or **Play/Pause** button |

---

## Project Structure

```
client/
├── config.py                 # Network, screen size, colors, and ship configs
├── network.py                # Thread-safe TCP JSON newline socket client
├── game_state.py             # Global state (session, boards, match info, ELO)
├── main.py                   # Application entry point, CLI parser, main loop
├── requirements.txt          # Pygame dependency
├── README.md                 # Documentation
└── screens/
    ├── __init__.py
    ├── base_screen.py        # BaseScreen, UI components, TextInput, Modals
    ├── login.py              # Login interface & reconnection
    ├── register.py           # Account registration
    ├── lobby.py              # Online players, matchmaking, challenges
    ├── place_ships.py        # 10x10 Fleet deployment & ship validation
    ├── game.py               # Active combat, firing, surrender, draw offers
    ├── result.py             # Match result summary & ELO updates
    ├── history.py            # Past matches list & replay launcher
    └── replay.py             # Dual-board step-by-step match playback
```

---

## Network Protocol (JSON over TCP)

Every message is a JSON string terminated by `\n`.

### Client → Server Messages

- `LOGIN`: `{"type": "LOGIN", "username": "...", "password": "..."}`
- `REGISTER`: `{"type": "REGISTER", "username": "...", "password": "..."}`
- `LOGOUT`: `{"type": "LOGOUT", "session_token": "..."}`
- `LIST_PLAYERS`: `{"type": "LIST_PLAYERS", "session_token": "..."}`
- `CHALLENGE`: `{"type": "CHALLENGE", "session_token": "...", "opponent": "..."}`
- `CHALLENGE_REPLY`: `{"type": "CHALLENGE_REPLY", "session_token": "...", "challenger": "...", "accept": true|false, "match_id": "..."}`
- `PLACE_SHIP`: `{"type": "PLACE_SHIP", "session_token": "...", "match_id": "...", "ship_size": int, "row": int, "col": int, "orientation": "H"|"V"}`
- `READY`: `{"type": "READY", "session_token": "...", "match_id": "..."}`
- `FIRE`: `{"type": "FIRE", "session_token": "...", "match_id": "...", "row": int, "col": int}`
- `SURRENDER`: `{"type": "SURRENDER", "session_token": "...", "match_id": "..."}`
- `DRAW_OFFER`: `{"type": "DRAW_OFFER", "session_token": "...", "match_id": "..."}`
- `DRAW_REPLY`: `{"type": "DRAW_REPLY", "session_token": "...", "match_id": "...", "accept": true|false}`
- `HISTORY`: `{"type": "HISTORY", "session_token": "..."}`
- `REPLAY`: `{"type": "REPLAY", "session_token": "...", "match_id": "..."}`

### Server → Client Messages

- `LOGIN_OK`: `{"type": "LOGIN_OK", "session_token": "...", "username": "...", "elo": int}`
- `REGISTER_OK`: `{"type": "REGISTER_OK", "message": "..."}`
- `ERROR`: `{"type": "ERROR", "message": "..."}`
- `PLAYER_LIST` / `PLAYER_UPDATE`: `{"type": "PLAYER_LIST", "players": [{"username": "...", "elo": int, "status": "ONLINE"}]}`
- `CHALLENGE`: `{"type": "CHALLENGE", "from": "...", "match_id": "..."}`
- `MATCH_FOUND`: `{"type": "MATCH_FOUND", "match_id": "...", "opponent": "...", "opponent_elo": int, "you_go_first": bool}`
- `PLACE_SHIP_OK`: `{"type": "PLACE_SHIP_OK", "ship_size": int}`
- `READY_OK`: `{"type": "READY_OK"}`
- `OPPONENT_READY`: `{"type": "OPPONENT_READY"}`
- `YOUR_TURN`: `{"type": "YOUR_TURN", "match_id": "..."}`
- `FIRE_RESULT`: `{"type": "FIRE_RESULT", "row": int, "col": int, "result": "HIT"|"MISS", "sunk": bool, "ship_size": int, "game_over": bool, "winner": "..."}`
- `OPPONENT_FIRED`: `{"type": "OPPONENT_FIRED", "row": int, "col": int, "result": "HIT"|"MISS", "sunk": bool, "ship_size": int}`
- `GAME_OVER`: `{"type": "GAME_OVER", "winner": "...", "reason": "...", "elo_change": int, "new_elo": int}`
- `DRAW_OFFER`: `{"type": "DRAW_OFFER", "from": "..."}`
- `DRAW_RESULT`: `{"type": "DRAW_RESULT", "accepted": bool, "message": "..."}`
- `HISTORY_DATA`: `{"type": "HISTORY_DATA", "matches": [...]}`
- `REPLAY_DATA`: `{"type": "REPLAY_DATA", "match_id": "...", "player1": "...", "player2": "...", "moves": [...]}`
