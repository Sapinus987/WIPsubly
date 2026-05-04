# 🦄 Subly

Real-time **Russian → French** subtitle overlay for Twitch streams.

Subly is split into two parts:
- **Server** — runs the AI models (Whisper + NLLB-200), captures Twitch streams and sends translated subtitles
- **Client** — lightweight overlay UI, connects to the server via WebSocket, no GPU required

---

## Architecture

```
┌─────────────────────────────────┐        ┌─────────────────────────────┐
│  Server  (GPU machine)          │        │  Client  (any machine)      │
│                                 │        │                             │
│  Whisper large-v3  (STT)        │◄──WS──►│  PyQt5 overlay UI           │
│  NLLB-200 1.3B     (translate)  │        │  Enter channel → subtitles  │
│  streamlink + ffmpeg            │        │                             │
└─────────────────────────────────┘        └─────────────────────────────┘
```

Both can run on the **same machine** (use `ws://localhost:8765`) or on separate machines over a local network.

---

## Requirements

### Server
| Component | Minimum |
|-----------|---------|
| OS | Windows 10/11 64-bit |
| GPU | NVIDIA with CUDA support |
| VRAM | ~7 GB (Whisper large-v3 + NLLB-200 1.3B) |
| Python | 3.10+ |

### Client
| Component | Minimum |
|-----------|---------|
| OS | Windows / macOS / Linux |
| Python | 3.10+ |
| GPU | Not required |

---

## Models

| Role | Model |
|------|-------|
| Speech-to-text | [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3) |
| Translation | [facebook/nllb-200-distilled-1.3B](https://huggingface.co/facebook/nllb-200-distilled-1.3B) |

Downloaded automatically on first server launch (~4 GB).

---

## Installation

### Server (GPU machine)

```bat
cd server
install.bat
```

### Client (any machine)

```bat
cd client
install.bat
```

---

## Usage

### 1 — Start the server

```bat
cd server
launch.bat
```

Wait for: `[Subly] Modèles prêts.` before connecting clients.

### 2 — Start the client

```bat
cd client
launch.bat
```

### 3 — Add a channel

- If client and server are on the **same machine**: leave the server field as `ws://localhost:8765`
- If on **separate machines**: replace `localhost` with the server's local IP (e.g. `ws://192.168.1.10:8765`)
- Enter a Twitch channel name and press **+**

---

## Project structure

```
Subly/
├── server/
│   ├── server.py       # FastAPI + WebSocket + Whisper + NLLB
│   ├── install.bat     # Server dependencies
│   └── launch.bat      # Start server
├── client/
│   ├── client.py       # PyQt5 overlay UI
│   ├── install.bat     # Client dependencies (PyQt5 + websockets only)
│   └── launch.bat      # Start client
└── .gitignore
```

---

## License

This project is provided as-is for personal use.
