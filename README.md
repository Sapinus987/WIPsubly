# 🦄 Subly

Real-time **Russian → French** subtitle overlay for Twitch streams.

Subly is split into two parts:
- **Server** — captures Twitch streams, transcribes speech with Whisper and translates with DeepL
- **Client** — lightweight overlay UI, connects to the server via WebSocket, no GPU required

---

## Architecture

```
┌─────────────────────────────────┐        ┌─────────────────────────────┐
│  Server  (GPU machine)          │        │  Client  (any machine)      │
│                                 │        │                             │
│  Whisper large-v3  (STT)        │◄──WS──►│  PyQt5 overlay UI           │
│  DeepL API         (translate)  │        │  Enter channel → subtitles  │
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
| VRAM | ~2 GB (Whisper large-v3 only) |
| Python | 3.10+ |
| DeepL API key | Free account — see below |

### Client
| Component | Minimum |
|-----------|---------|
| OS | Windows / macOS / Linux |
| Python | 3.10+ |
| GPU | Not required |

---

## DeepL API key (required)

Subly uses [DeepL](https://www.deepl.com) for Russian → French translation.

**The free plan includes 1,000,000 characters/year** — more than enough for personal streaming use.

### How to get your free API key

1. Go to **[deepl.com/pro#developer](https://www.deepl.com/pro#developer)**
2. Click **"Sign up for free"**
3. Create an account (no credit card required for the free plan)
4. Once logged in, go to **Account → API Keys**
5. Copy your API key — it looks like: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx`

### Save your key

Create a file called `deepl.key` inside the `server/` folder and paste your key on a single line:

```
server/
└── deepl.key   ← create this file, paste your key inside
```

> ⚠️ Never share this file or commit it to a repository. It is already listed in `.gitignore`.

---

## Models

| Role | Model |
|------|-------|
| Speech-to-text | [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3) |
| Translation | [DeepL API](https://www.deepl.com/docs-api) |

Whisper is downloaded automatically on first server launch (~3 GB).

---

## Installation

### Server (GPU machine)

```bat
cd server
install.bat
```

Then create your `server/deepl.key` file with your DeepL API key.

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

Wait for:
```
[Subly] Serveur pret.
INFO:     Uvicorn running on http://0.0.0.0:8765
```

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
│   ├── server.py       # FastAPI + WebSocket + Whisper + DeepL
│   ├── deepl.key       # Your DeepL API key (create this file, never commit it)
│   ├── install.bat     # Server dependencies
│   └── launch.bat      # Start server
├── client/
│   ├── client.py       # PyQt5 overlay UI
│   ├── install.bat     # Client dependencies (PyQt5 + websockets only)
│   └── launch.bat      # Start client
├── benchmark.py        # Benchmark translation models vs DeepL
└── .gitignore
```

---

## License

This project is provided as-is for personal use.
