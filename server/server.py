"""
Subly Server — Backend FastAPI + WebSocket

Pipeline :
  Twitch (streamlink) → ffmpeg (audio PCM) → Whisper large-v3 (STT russe)
  → DeepL API (traduction FR) → WebSocket → clients légers

La clé DeepL est lue depuis le fichier server/deepl.key (une ligne, jamais versionné).
"""
import os
import sys
import asyncio
import threading
import queue
import subprocess
import numpy as np
from contextlib import asynccontextmanager
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

# ── DLL CUDA (Whisper / CTranslate2) ──────────────────────────────────────────
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
_VENV_SITE = os.path.join(sys.prefix, "Lib", "site-packages")
for _dll_dir in (
    os.path.join(_VENV_SITE, "ctranslate2"),
    os.path.join(_VENV_SITE, "nvidia", "cublas", "bin"),
    os.path.join(_VENV_SITE, "nvidia", "cudnn", "bin"),
    os.path.join(_VENV_SITE, "nvidia", "cuda_runtime", "bin"),
):
    if os.path.isdir(_dll_dir):
        os.add_dll_directory(_dll_dir)
        os.environ["PATH"] = _dll_dir + ";" + os.environ.get("PATH", "")

# ── Constantes ─────────────────────────────────────────────────────────────────
_BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
_FFMPEG_LOCAL  = os.path.join(_BASE_DIR, "ffmpeg", "bin", "ffmpeg.exe")
_FFMPEG_PARENT = os.path.join(os.path.dirname(_BASE_DIR), "ffmpeg", "bin", "ffmpeg.exe")
FFMPEG_PATH    = _FFMPEG_LOCAL if os.path.exists(_FFMPEG_LOCAL) else _FFMPEG_PARENT

# Streamlink : chemin complet dans le venv pour éviter les problèmes de PATH
_SCRIPTS = os.path.join(sys.prefix, "Scripts")
_SL_EXE  = os.path.join(_SCRIPTS, "streamlink.exe")
STREAMLINK = _SL_EXE if os.path.exists(_SL_EXE) else "streamlink"

SAMPLE_RATE    = 16_000
CHUNK_SEC      = 5
HOST           = "0.0.0.0"
PORT           = 8765

# ── Clé DeepL ─────────────────────────────────────────────────────────────────
def _load_deepl_key() -> str:
    # Priorité : variable d'environnement → fichier deepl.key
    key = os.environ.get("DEEPL_API_KEY", "").strip()
    if key:
        return key
    key_file = os.path.join(_BASE_DIR, "deepl.key")
    if os.path.exists(key_file):
        with open(key_file, encoding="utf-8") as f:
            key = f.read().strip()
    if not key:
        print("[Subly] ERREUR : clé DeepL introuvable.")
        print("        Crée le fichier server/deepl.key avec ta clé sur une seule ligne.")
        sys.exit(1)
    return key

DEEPL_KEY = _load_deepl_key()

# ── Globals ────────────────────────────────────────────────────────────────────
_whisper  = None
_deepl    = None
_loop: asyncio.AbstractEventLoop = None
_sessions: Dict[str, "ChannelSession"] = {}


# ══════════════════════════════════════════════════════════════════════════════
#  Chargement des modèles
# ══════════════════════════════════════════════════════════════════════════════
def _load_models():
    global _whisper, _deepl
    import deepl
    from faster_whisper import WhisperModel
    from huggingface_hub import snapshot_download

    print("[Subly] Verification Whisper large-v3...")
    model_path = snapshot_download("Systran/faster-whisper-large-v3")
    print("[Subly] Init Whisper CUDA...")
    _whisper = WhisperModel(model_path, device="cuda", compute_type="float16")

    print("[Subly] Init DeepL...")
    _deepl = deepl.Translator(DEEPL_KEY)
    usage  = _deepl.get_usage()
    print(f"[Subly] DeepL pret — {usage.character.count:,} / {usage.character.limit:,} caracteres utilises.")
    print("[Subly] Serveur pret.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop
    _loop = asyncio.get_running_loop()
    await _loop.run_in_executor(None, _load_models)
    yield
    for session in list(_sessions.values()):
        session.stop()


app = FastAPI(title="Subly Server", lifespan=lifespan)


# ══════════════════════════════════════════════════════════════════════════════
#  ChannelSession
# ══════════════════════════════════════════════════════════════════════════════
class ChannelSession:
    # Correspondance DeepL source → code Whisper
    _DEEPL_TO_WHISPER = {"RU": "ru", "UK": "uk"}

    def __init__(self, channel: str, source_lang: str = "RU", target_lang: str = "FR"):
        self.channel     = channel
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._whisper_lang = self._DEEPL_TO_WHISPER.get(source_lang, "ru")
        self.clients: Set[WebSocket] = set()
        self._audio_q = queue.Queue()
        self._running = True
        self._ctx     = []   # contexte glissant : 2 derniers segments RU
        self._sl_proc = None
        self._ff_proc = None

        threading.Thread(target=self._capture, daemon=True).start()
        threading.Thread(target=self._process, daemon=True).start()

    # ── Clients ───────────────────────────────────────────────────────────
    def add_client(self, ws: WebSocket):
        self.clients.add(ws)

    def remove_client(self, ws: WebSocket):
        self.clients.discard(ws)

    # ── Broadcast thread-safe ─────────────────────────────────────────────
    def _broadcast_sync(self, text: str):
        if _loop and self.clients:
            asyncio.run_coroutine_threadsafe(self._broadcast(text), _loop)

    async def _broadcast(self, text: str):
        dead = set()
        for ws in list(self.clients):
            try:
                await ws.send_json({"channel": self.channel, "text": text})
            except Exception:
                dead.add(ws)
        self.clients -= dead

    # ── Capture Twitch ────────────────────────────────────────────────────
    def _capture(self):
        url = f"https://www.twitch.tv/{self.channel}"
        sl  = [STREAMLINK, "--stdout", url, "best"]
        ff  = [FFMPEG_PATH, "-i", "pipe:0",
               "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1", "pipe:1"]
        try:
            self._sl_proc = subprocess.Popen(
                sl, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
            self._ff_proc = subprocess.Popen(
                ff, stdin=self._sl_proc.stdout,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
            chunk = SAMPLE_RATE * 2 * CHUNK_SEC
            while self._running:
                data = self._ff_proc.stdout.read(chunk)
                if not data:
                    break
                self._audio_q.put(data)
        except Exception as ex:
            self._broadcast_sync(f"Erreur capture : {ex}")
        finally:
            for proc in (self._ff_proc, self._sl_proc):
                if proc:
                    try:
                        proc.kill()
                    except Exception:
                        pass

    # ── Transcription (Whisper) + traduction (DeepL) ──────────────────────
    def _process(self):
        while self._running:
            try:
                data = self._audio_q.get(timeout=1)
            except queue.Empty:
                continue

            audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            segs, _ = _whisper.transcribe(
                audio, language=self._whisper_lang,
                vad_filter=True,           # ignore les passages sans voix
                vad_parameters={"threshold": 0.5},  # sensibilité (0=tout garder, 1=très strict)
            )
            ru = " ".join(s.text for s in segs if s.no_speech_prob < 0.6).strip()
            if not ru:
                continue

            try:
                # Contexte glissant pour DeepL (meilleure cohérence narrative)
                self._ctx.append(ru)
                if len(self._ctx) > 2:
                    self._ctx.pop(0)
                ru_ctx = " ".join(self._ctx)

                result = _deepl.translate_text(
                    ru_ctx, source_lang=self.source_lang, target_lang=self.target_lang)
                self._broadcast_sync(result.text)
            except Exception as ex:
                self._broadcast_sync(f"Erreur traduction : {ex}")

    # ── Arrêt ─────────────────────────────────────────────────────────────
    def stop(self):
        self._running = False
        for proc in (self._ff_proc, self._sl_proc):
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass


# ══════════════════════════════════════════════════════════════════════════════
#  Endpoints
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/ping")
async def ping():
    return {"status": "ok", "sessions": list(_sessions.keys())}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    active: Set[str] = set()
    try:
        while True:
            msg         = await ws.receive_json()
            action      = msg.get("action", "")
            channel     = msg.get("channel", "").strip().lower()
            source_lang = msg.get("source_lang", "RU").upper()
            target_lang = msg.get("target_lang", "FR").upper()
            if not channel:
                continue

            key = f"{channel}_{source_lang}_{target_lang}"

            if action == "start":
                if key not in _sessions:
                    _sessions[key] = ChannelSession(channel, source_lang, target_lang)
                _sessions[key].add_client(ws)
                active.add(key)

            elif action == "stop":
                if key in _sessions:
                    _sessions[key].remove_client(ws)
                    if not _sessions[key].clients:
                        _sessions[key].stop()
                        del _sessions[key]
                active.discard(key)

    except WebSocketDisconnect:
        pass
    finally:
        for key in list(active):
            if key in _sessions:
                _sessions[key].remove_client(ws)
                if not _sessions[key].clients:
                    _sessions[key].stop()
                    del _sessions[key]


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
