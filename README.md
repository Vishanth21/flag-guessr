# Flag-Guessr

A multiplayer flag-guessing quiz game built with raw TCP sockets and Python. Players connect to a central server, view ANSI-rendered country flags in their terminal, and race to guess the correct country before time runs out.

## Features

- [x] Multiplayer flag-guessing with timed rounds and live leaderboard
- [x] Country flags rendered as ANSI art in the terminal
- [x] Rich terminal UI with non-blocking single-keypress input
- [x] Admin-controlled lobby and game start
- [x] SSL/TLS encrypted client-server communication
- [x] Payload size validation and body read timeouts

## Project Structure

```
flag-guessr/
├── README.md
├── pyproject.toml             # Project config & dependencies (uv)
├── uv.lock                    # Lockfile
├── data/
│   └── ansi_flags.json        # Pre-rendered ANSI flag art
├── scripts/
│   └── flag_converter.py      # One-time script to generate flag data
├── server/
│   ├── server.py              # Secure TCP server, lobby, connection handling
│   └── game.py                # Core game loop and flag selection logic
├── client/
│   └── client.py              # Secure TCP client, Rich UI, input handling
└── certs/                     # SSL/TLS certificates
    ├── server.crt
    └── server.key
```

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [OpenSSL](https://slproweb.com/download/Win64OpenSSL_Light-3_6_1.exe) (for generating certificates on Windows)
- A terminal with truecolor support (e.g. Kitty, iTerm2, Windows Terminal)

### 1. Clone the repository

```bash
git clone https://github.com/Vishanth21/flag-guessr.git
cd flag-guessr
```

### 2. Install dependencies

```bash
uv sync
```

This creates the virtual environment and installs all dependencies from `pyproject.toml` automatically.

### 3. Generate SSL Certificates

The game requires TLS encryption. Generate a self-signed certificate:

```bash
mkdir -p certs
openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout certs/server.key -out certs/server.crt
```

> [!NOTE]
> During generation, you can leave the fields blank by entering `.` when prompted.

### 4. Generate flag data (first time only / optional: if you don't have the json file)

This downloads 196 country flag PNGs and converts them to ANSI art:

```bash
uv run python scripts/flag_converter.py
```

> This creates `data/ansi_flags.json` (~196 entries). Takes a few minutes.

## How to Play

### Start the server

```bash
uv run python server/server.py
```

The server will listen on `127.0.0.1:65432` and wait for clients.

### Connect clients

Open a new terminal for each player:

```bash
uv run python client/client.py <username>
```

Example:

```bash
uv run python client/client.py player1
uv run python client/client.py player2
```

### Start the game

In the **server terminal**, type:

```
start <rounds> <timeout>
```

Example: `start 10 15` starts a game with 10 rounds and 15 seconds per question.

The server broadcasts flag questions to all connected clients. Players press **1-4** to answer.

## Configuration

| Setting | File | Default | Description |
|---|---|---|---|
| `HOST` | `server.py` / `client.py` | `127.0.0.1` | Server bind address |
| `PORT` | `server.py` / `client.py` | `65432` | Server port |
| `FLAG_CDN` | `flag_converter.py` | `w160` | Source image resolution |
| `RENDER_W` | `flag_converter.py` | `30` | ANSI flag width (columns) |

## Tech Stack

- **Networking**: Raw TCP sockets (`socket` module) with SSL/TLS
- **Protocol**: Custom 4-byte length-prefixed JSON framing (`struct` + `json`)
- **Concurrency**: `threading` with `Lock` and `Event` synchronization
- **Client UI**: [`rich`](https://github.com/Textualize/rich) for colorful terminal output
- **Client Input**: Non-blocking single-keypress via `tty`/`select` (POSIX) and `msvcrt` (Windows)
- **Flag Rendering**: [`climage`](https://github.com/pnappa/CLImage) for PNG to ANSI conversion
- **Flag Source**: [flagcdn.com](https://flagcdn.com)

## Protocol Specification

All messages follow: `[4-byte big-endian length][JSON payload]`

### Client to Server

| Type | Payload |
|---|---|
| `JOIN` | `{"type": "JOIN", "username": "Player1"}` |
| `ANSWER` | `{"type": "ANSWER", "question_id": 1, "answer": "France", "client_elapsed_time": 2.5}` |

### Server to Client

| Type | Payload |
|---|---|
| `STATUS` | `{"type": "STATUS", "message": "..."}` |
| `QUESTION` | `{"type": "QUESTION", "question_id": 1, "time_limit": 10, "flag_data": "...", "options": ["France", "Italy", "Spain", "Germany"]}` |
| `EVALUATION` | `{"type": "EVALUATION", "result": "correct", "score_earned": 15, "message": "..."}` |
| `LEADERBOARD` | `{"type": "LEADERBOARD", "rankings": [{"username": "Player1", "score": 15}, ... ]}` |