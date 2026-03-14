# Flag-Guessr

A multiplayer flag-guessing quiz game built with raw TCP sockets and Python. Players connect to a central server, view ANSI-rendered country flags in their terminal, and race to guess the correct country before time runs out.

## Features

- [x] Raw TCP socket communication
- [x] Custom length-prefixed binary protocol with JSON payloads
- [x] Multi-client support via threaded server
- [x] Username-based login system
- [x] Thread-safe client/server with proper locking
- [x] Admin-controlled lobby
- [x] Country flags converted to ANSI art
- [x] Rich terminal UI on the client side
- [x] Timed question rounds with countdown
- [x] Answer evaluation and scoring
- [x] Live leaderboard after each round
- [x] SSL/TLS encrypted connections (end-to-end)

## Project Structure

```
flag-guessr/
├── README.md
├── requirements.txt
├── data/
│   └── ansi_flags.json        # Pre-rendered ANSI flag art
├── scripts/
│   └── flag_converter.py      # One-time script to generate flag data
├── server/
│   └── server.py              # Secure TCP server, lobby, game logic
├── client/
│   └── client.py              # Secure TCP client, Rich UI, input handling
└── certs/                     # SSL/TLS certificates
    ├── server.crt
    └── server.key
```

## Setup

### Prerequisites

- Python 3.10+
- OpenSSL (for generating certificates)
- A terminal with truecolor support (e.g. Kitty, iTerm2, Windows Terminal)

### 1. Clone the repository

```bash
git clone https://github.com/Vishanth21/flag-guessr.git
cd flag-guessr
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Generate SSL Certificates

The game requires TLS encryption. Generate a self-signed certificate:

```bash
mkdir -p certs
openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout certs/server.key -out certs/server.crt
```

> [!NOTE]
> During generation, you can leave the fields blank by entering `.` when prompted.

### 4. Generate flag data (first time only / optional: if you dont have the json file)

This downloads 196 country flag PNGs and converts them to ANSI art:

```bash
python scripts/flag_converter.py
```

> This creates `data/ansi_flags.json` (~196 entries). Takes a few minutes.

## How to Play

### Start the server

```bash
python server/server.py
```

The server will listen on `127.0.0.1:65432` and wait for clients.

### Connect clients

Open a new terminal for each player:

```bash
python client/client.py <username>
```

Example:

```bash
python client/client.py player1
python client/client.py player2
```

### Start the game

In the **server terminal**, type:

```
start
```

The server broadcasts flag questions to all connected clients.

## Configuration

| Setting | File | Default | Description |
|---|---|---|---|
| `HOST` | `server.py` / `client.py` | `127.0.0.1` | Server bind address |
| `PORT` | `server.py` / `client.py` | `65432` | Server port |
| `FLAG_CDN` | `flag_converter.py` | `w160` | Source image resolution |
| `RENDER_W` | `flag_converter.py` | `30` | ANSI flag width (columns) |

## Tech Stack

- **Networking**: Raw TCP sockets (`socket` module)
- **Protocol**: Custom 4-byte length-prefixed JSON framing (`struct` + `json`)
- **Concurrency**: `threading` with `Lock` and `Event` synchronization
- **Client UI**: [`rich`](https://github.com/Textualize/rich) for colorful terminal output
- **Flag Rendering**: [`climage`](https://github.com/pnappa/CLImage) for PNG to ANSI conversion
- **Flag Source**: [flagcdn.com](https://flagcdn.com)

## Protocol Specification

All messages follow: `[4-byte big-endian length][JSON payload]`

### Client to Server

| Type | Payload |
|---|---|
| `JOIN` | `{"type": "JOIN", "username": "Player1"}` |
| `ANSWER` | `{"type": "ANSWER", "question_id": 1, "answer": "France", "client_elapsed_time": 2.5}` |
| `CHAT` | `{"type": "CHAT", "message": "hello"}` |

### Server to Client

| Type | Payload |
|---|---|
| `STATUS` | `{"type": "STATUS", "message": "..."}` |
| `QUESTION` | `{"type": "QUESTION", "question_id": 1, "time_limit": 10, "flag_data": "...", "options": ["France", "Italy", "Spain", "Germany"]}` |
| `EVALUATION` | `{"type": "EVALUATION", "result": "correct", "score_earned": 15, "message": "..."}` |
| `LEADERBOARD` | `{"type": "LEADERBOARD", "rankings": [{"username": "Player1", "score": 15}, ... ]}` |