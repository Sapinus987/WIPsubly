# 🦄 Subly

Real-time subtitle overlay for Twitch streams.  
Subly listens to a stream, transcribes the speech with Whisper and translates it with DeepL — all displayed in a floating window on your screen.

**Supported input languages:** Russian 🇷🇺, Ukrainian 🇺🇦, English 🇬🇧, French 🇫🇷  
**Supported output languages:** French 🇫🇷, English 🇬🇧, Russian 🇷🇺, Ukrainian 🇺🇦

Any combination is supported — including same language input/output for live transcription (e.g. French → French for hearing-impaired viewers).

---

## How it works

Subly is split into two parts:

| Part | Role | Machine required |
|------|------|-----------------|
| **Server** | Captures the stream, transcribes speech, calls DeepL | Windows PC with NVIDIA GPU |
| **Client** | Displays the subtitle overlay | Any machine (no GPU needed) |

Both parts can run on the **same machine**, or on separate machines on the same network.

```
Twitch stream
     ↓
 Whisper large-v3   (speech → text, any supported language)
     ↓
 DeepL API          (text → translation, any supported language pair)
     ↓
 Client overlay     (displays subtitles)
```

---

## Requirements

### Server machine
| | Minimum |
|-|---------|
| OS | Windows 10/11 64-bit |
| GPU | NVIDIA (CUDA-compatible) |
| VRAM | 2 GB |
| RAM | 8 GB |
| Python | [3.10 or higher](https://www.python.org/downloads/) |
| Internet | Required (Twitch + DeepL API) |

### Client machine
| | Minimum |
|-|---------|
| OS | Windows, macOS or Linux |
| Python | [3.10 or higher](https://www.python.org/downloads/) |
| GPU | Not required |

---

## Step 1 — Clone the repository

```bat
git clone https://github.com/Sapinus987/WIPsubly.git
cd WIPsubly
```

> If you don't have Git installed, download it at **[git-scm.com](https://git-scm.com/downloads)**.

> ⚠️ **Python tip:** On the Python download page, click the large **"Download Python"** button (the recommended installer). Avoid downloading individual packages — they can cause PATH issues that prevent the install scripts from working.

---

## Step 2 — Get a free DeepL API key

Subly uses [DeepL](https://www.deepl.com) for translation. The **free plan gives 1,000,000 characters per year**, which is more than enough for personal use.

**How to get your key:**

1. Go to **[deepl.com/pro#developer](https://www.deepl.com/pro#developer)**
2. Click **"Sign up for free"** — no credit card required
3. Once logged in, open **Account → API Keys**
4. Copy your key — it looks like: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx`

**Save your key:**

Create a file named `deepl.key` inside the `server/` folder and paste your key on a single line:

```
server/
└── deepl.key   ← create this file and paste your key inside
```

> ⚠️ Never share this file or upload it anywhere. It is excluded from version control by `.gitignore`.

---

## Step 3 — Install the server

Run this once on the machine that has the GPU:

```bat
cd server
install.bat
```

This will automatically install all dependencies and download ffmpeg.

The Whisper model (~3 GB) will be downloaded on the **first launch** of the server.

---

## Step 4 — Install the client

Run this once on the machine that will display the subtitles (can be the same machine):

```bat
cd client
install.bat
```

---

## Step 5 — Start the server

```bat
cd server
launch.bat
```

Wait until you see this message before connecting any client:

```
[Subly] Serveur pret.
INFO:     Uvicorn running on http://0.0.0.0:8765
```

---

## Step 6 — Start the client

```bat
cd client
launch.bat
```

The control panel opens. The interface language is automatically set based on your system language (French or English).

---

## Step 7 — Add a channel

1. **Server field** — leave `ws://localhost:8765` if the server is on the same machine. If on another machine, replace `localhost` with its local IP address (e.g. `ws://192.168.1.10:8765`)
2. **Stream language** — choose the language spoken on the stream (Russian, Ukrainian, English or French)
3. **Translation language** — choose your target language (French, English, Russian or Ukrainian). You can also select the same language as the stream for live transcription without translation.
4. **Channel name** — enter a Twitch channel name and press **+**

A subtitle overlay appears on your screen for that channel.

---

## Overlay controls

| Action | How |
|--------|-----|
| Move | Drag anywhere on the overlay |
| Resize | Bottom-right corner grip |
| Reduce opacity | Orange button (top-left) |
| Close | Red button (top-left) |

---

## Project structure

```
Subly/
├── server/
│   ├── server.py       # Backend: Whisper + DeepL + WebSocket
│   ├── deepl.key       # Your DeepL API key — create this file yourself
│   ├── install.bat     # Install server dependencies
│   └── launch.bat      # Start the server
├── client/
│   ├── client.py       # Frontend: PyQt5 overlay UI
│   ├── install.bat     # Install client dependencies
│   └── launch.bat      # Start the client
├── benchmark.py        # Tool to compare translation models
└── .gitignore
```

---

## Troubleshooting

**The overlay shows nothing when the stream is silent**  
→ This is normal. Subly uses voice detection (VAD) and only translates when speech is detected.

**"Connection refused" error in the client**  
→ Make sure the server is fully started (wait for `Serveur pret.`) before launching the client.

**"deepl.key not found" error**  
→ Create the file `server/deepl.key` and paste your DeepL API key inside.

**The server crashes on startup**  
→ Make sure your NVIDIA drivers are up to date and that CUDA is available (`nvidia-smi` in a terminal).

---

## License

This project is provided as-is for personal use.
