# 🦄 Subly

Real-time **Russian → French** subtitle overlay for Twitch streams.  
Subly listens to any Twitch channel, transcribes the speech with Whisper, translates it with NLLB-200, and displays a floating subtitle window directly on your screen.

---

## Features

- **Live subtitles** — 5-second chunks, continuously updated
- **Multi-channel** — monitor several streams simultaneously, each with its own overlay
- **Offline AI** — everything runs locally, no API key needed
- **Custom overlay** — resizable, draggable, adjustable font size, toggleable opacity
- **Clean UI** — frameless dark interface with a Twitch-inspired palette

---

## Requirements

| Component | Minimum |
|-----------|---------|
| OS | Windows 10/11 64-bit |
| GPU | NVIDIA GPU with CUDA support (8 GB VRAM recommended) |
| VRAM | ~7 GB (Whisper large-v3 + NLLB-200 1.3B) |
| RAM | 8 GB |
| Python | 3.10+ |
| CUDA Driver | 520+ (check with `nvidia-smi`) |

> ⚠️ **CPU-only is not supported.** Both models are loaded on CUDA.

---

## Models used

| Role | Model |
|------|-------|
| Speech-to-text | [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3) |
| Translation | [facebook/nllb-200-distilled-1.3B](https://huggingface.co/facebook/nllb-200-distilled-1.3B) |

Models are downloaded automatically from Hugging Face on first launch (~4 GB total).

---

## Installation

```bat
git clone https://github.com/Sapinus987/WIPsubly.git
cd WIPsubly
install.bat
```

`install.bat` will:
1. Create a Python virtual environment (`env/`)
2. Install all Python dependencies
3. Install PyTorch with CUDA 11.8
4. Install pinned CUDA libraries (cublas, cudnn) compatible with CTranslate2 4.x
5. Download `ffmpeg.exe` into `ffmpeg/bin/`

---

## Usage

```bat
lancer.bat
```

1. Subly loads Whisper and NLLB-200 (first launch takes a few minutes for downloads)
2. A splash screen appears during initialization
3. The **Control Panel** opens — type a Twitch channel name and press **+**
4. A subtitle overlay appears on screen for that channel
5. Use the **font size slider** to adjust text size across all overlays

### Overlay controls

| Action | How |
|--------|-----|
| Move | Drag anywhere on the overlay |
| Resize | Bottom-right grip |
| Toggle opacity | Orange button (top-left) |
| Close | Red button (top-left) |

---

## Project structure

```
WIPsubly/
├── subly.py       # Entry point — critical init order (CUDA before Qt)
├── ui.py          # All PyQt5 classes (ControlPanel, OverlayWindow, …)
├── install.bat    # One-click installer
├── lancer.bat     # Launcher
├── requirements.txt
└── .gitignore
```

> `ffmpeg/` and `env/` are created locally by `install.bat` and are not versioned.

---

## Technical notes

**Initialization order matters.**  
PyQt5 initializes Direct3D/OpenGL GPU resources that conflict with CTranslate2's CUDA context if imported first. `subly.py` enforces the correct order:

1. CTranslate2 / Whisper (CUDA)
2. PyQt5
3. Transformers / PyTorch

**Sliding context window.**  
The last 2 transcribed Russian segments are concatenated before translation, giving NLLB-200 enough context to produce coherent output across chunk boundaries.

---

## License

This project is provided as-is for personal use.
