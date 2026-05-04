"""
Subly Server — Backend FastAPI + WebSocket

Rôle : charger Whisper large-v3 + NLLB-200 1.3B, capturer les streams Twitch,
transcrire (russe) et traduire (français), puis diffuser le texte à tous les
clients connectés via WebSocket.

Ordre d'initialisation critique :
  CTranslate2 / Whisper (CUDA) doit être importé AVANT PyQt5.
  Ici, pas de PyQt5 : aucun risque de conflit.
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

# ── DLL CUDA ───────────────────────────────────────────────────────────────────
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
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Cherche ffmpeg dans server/ffmpeg/ (install propre) puis à la racine du projet (fallback)
_FFMPEG_LOCAL  = os.path.join(_BASE_DIR, "ffmpeg", "bin", "ffmpeg.exe")
_FFMPEG_PARENT = os.path.join(os.path.dirname(_BASE_DIR), "ffmpeg", "bin", "ffmpeg.exe")
FFMPEG_PATH = _FFMPEG_LOCAL if os.path.exists(_FFMPEG_LOCAL) else _FFMPEG_PARENT
_NLLB_NAME  = "facebook/nllb-200-distilled-1.3B"
SAMPLE_RATE = 16_000
CHUNK_SEC   = 5
HOST        = "0.0.0.0"
PORT        = 8765

# ── Modèles (initialisés au démarrage via lifespan) ───────────────────────────
_whisper     = None
_nllb_tok    = None
_nllb_model  = None
_fr_tok_id   = None
_loop: asyncio.AbstractEventLoop = None

# ── Sessions actives (channel → ChannelSession) ───────────────────────────────
_sessions: Dict[str, "ChannelSession"] = {}


# ══════════════════════════════════════════════════════════════════════════════
#  Chargement des modèles
# ══════════════════════════════════════════════════════════════════════════════
def _load_models():
    global _whisper, _nllb_tok, _nllb_model, _fr_tok_id
    from faster_whisper import WhisperModel
    from huggingface_hub import snapshot_download
    from transformers import NllbTokenizer, AutoModelForSeq2SeqLM

    print("[Subly] Téléchargement / vérification Whisper large-v3...")
    model_path = snapshot_download("Systran/faster-whisper-large-v3")
    print("[Subly] Init Whisper CUDA...")
    _whisper = WhisperModel(model_path, device="cuda", compute_type="float16")

    print("[Subly] Chargement NLLB-200 1.3B...")
    _nllb_tok   = NllbTokenizer.from_pretrained(_NLLB_NAME, src_lang="rus_Cyrl")
    _nllb_model = AutoModelForSeq2SeqLM.from_pretrained(
        _NLLB_NAME, torch_dtype="auto").to("cuda")
    _fr_tok_id  = _nllb_tok.convert_tokens_to_ids("fra_Latn")
    print("[Subly] Modèles prêts.")


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
#  ChannelSession — capture + transcription + traduction pour une chaîne
# ══════════════════════════════════════════════════════════════════════════════
class ChannelSession:
    def __init__(self, channel: str):
        self.channel   = channel
        self.clients: Set[WebSocket] = set()
        self._audio_q  = queue.Queue()
        self._running  = True
        self._ctx      = []          # contexte glissant (2 derniers segments RU)
        self._sl_proc  = None
        self._ff_proc  = None

        threading.Thread(target=self._capture, daemon=True).start()
        threading.Thread(target=self._process, daemon=True).start()

    # ── Gestion des clients ────────────────────────────────────────────────
    def add_client(self, ws: WebSocket):
        self.clients.add(ws)

    def remove_client(self, ws: WebSocket):
        self.clients.discard(ws)

    # ── Diffusion (appelée depuis un thread sync) ──────────────────────────
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

    # ── Capture Twitch ─────────────────────────────────────────────────────
    def _capture(self):
        url = f"https://www.twitch.tv/{self.channel}"
        sl  = ["streamlink", "--stdout", url, "best"]
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

    # ── Transcription + traduction ─────────────────────────────────────────
    def _process(self):
        while self._running:
            try:
                data = self._audio_q.get(timeout=1)
            except queue.Empty:
                continue

            audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            segs, _ = _whisper.transcribe(audio, language="ru")
            ru = " ".join(s.text for s in segs).strip()
            if not ru:
                continue

            try:
                self._ctx.append(ru)
                if len(self._ctx) > 2:
                    self._ctx.pop(0)
                ru_ctx = " ".join(self._ctx)

                inp = _nllb_tok(
                    ru_ctx, return_tensors="pt",
                    padding=True, truncation=True, max_length=512,
                ).to("cuda")
                out = _nllb_model.generate(
                    **inp, forced_bos_token_id=_fr_tok_id,
                    num_beams=2, max_new_tokens=128,
                    repetition_penalty=1.2, no_repeat_ngram_size=3,
                )
                fr = _nllb_tok.decode(out[0], skip_special_tokens=True)
                self._broadcast_sync(fr)
            except Exception as ex:
                self._broadcast_sync(f"Erreur traduction : {ex}")

    # ── Arrêt ──────────────────────────────────────────────────────────────
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
    """Health-check pour le client."""
    return {"status": "ok", "sessions": list(_sessions.keys())}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """
    Protocole :
      Client → serveur : {"action": "start"|"stop", "channel": "nom"}
      Serveur → client : {"channel": "nom", "text": "traduction"}
    """
    await ws.accept()
    active: Set[str] = set()

    try:
        while True:
            msg = await ws.receive_json()
            action  = msg.get("action", "")
            channel = msg.get("channel", "").strip().lower()
            if not channel:
                continue

            if action == "start":
                if channel not in _sessions:
                    _sessions[channel] = ChannelSession(channel)
                _sessions[channel].add_client(ws)
                active.add(channel)

            elif action == "stop":
                if channel in _sessions:
                    _sessions[channel].remove_client(ws)
                    if not _sessions[channel].clients:
                        _sessions[channel].stop()
                        del _sessions[channel]
                active.discard(channel)

    except WebSocketDisconnect:
        pass
    finally:
        for ch in list(active):
            if ch in _sessions:
                _sessions[ch].remove_client(ws)
                if not _sessions[ch].clients:
                    _sessions[ch].stop()
                    del _sessions[ch]


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
