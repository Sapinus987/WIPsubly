"""
Subly — point d'entree
Ordre critique d'initialisation :
  1. CTranslate2 / Whisper (CUDA) — AVANT PyQt5
  2. PyQt5 (via ui.py)            — APRES CTranslate2
  3. Transformers / PyTorch       — APRES PyQt5

PyQt5 initialise des ressources GPU (Direct3D/OpenGL) qui entrent en conflit
avec l'init CUDA de CTranslate2 si PyQt5 est charge en premier.
"""
import sys
import os

# ── Evite les conflits Intel OpenMP (ctranslate2) vs autres runtimes ──────────
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# ── Chemin de base (compatible frozen PyInstaller et execution normale) ────────
if getattr(sys, "frozen", False):
    # PyInstaller 6.x onedir : les DLLs et ressources sont dans _internal/ (= sys._MEIPASS)
    _BASE_DIR = sys._MEIPASS
    os.add_dll_directory(_BASE_DIR)
else:
    # Execution normale depuis le venv
    _BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
    # Python 3.8+ Windows n'utilise plus os.environ["PATH"] pour charger les DLLs
    # des extensions C. os.add_dll_directory() est obligatoire.
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
_NLLB_NAME = "facebook/nllb-200-distilled-1.3B"


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import traceback
    import faulthandler

    _LOG      = os.path.join(_BASE_DIR, "subly_crash.log")
    _log_file = open(_LOG, "w", encoding="utf-8")
    _log_file.write("=== Subly demarrage ===\n"); _log_file.flush()
    faulthandler.enable(_log_file)

    try:
        # ── 1. faster-whisper (CTranslate2) — AVANT PyQt5 ─────────────────────
        _log_file.write("Import faster_whisper...\n"); _log_file.flush()
        from faster_whisper import WhisperModel
        from huggingface_hub import snapshot_download

        _log_file.write("Verification modele large-v3...\n"); _log_file.flush()
        model_path = snapshot_download("Systran/faster-whisper-large-v3")
        _log_file.write(f"Modele : {model_path}\n"); _log_file.flush()

        _log_file.write("Init Whisper CUDA...\n"); _log_file.flush()
        whisper_model = WhisperModel(
            model_path, device="cuda", compute_type="float16")
        _log_file.write("Whisper OK\n"); _log_file.flush()

        # ── 2. PyQt5 (via ui.py) — APRES CTranslate2 ──────────────────────────
        _log_file.write("Import PyQt5 / ui...\n"); _log_file.flush()
        from PyQt5.QtWidgets import QApplication
        import ui  # importe PyQt5 + definit toutes les classes UI
        _load_fonts = ui._load_fonts
        _log_file.write("PyQt5 OK\n"); _log_file.flush()

        app = QApplication(sys.argv)
        app.setApplicationName("Subly")
        _load_fonts()

        splash = ui.LoadingSplash()
        splash.show()
        app.processEvents()

        # ── 3. Transformers / PyTorch — APRES PyQt5 ───────────────────────────
        _log_file.write("Import transformers...\n"); _log_file.flush()
        from transformers import NllbTokenizer, AutoModelForSeq2SeqLM
        _log_file.write("Transformers OK\n"); _log_file.flush()

        splash.set_status("Chargement NLLB-200 1.3B...")
        _log_file.write("Chargement NLLB...\n"); _log_file.flush()
        nllb_tok   = NllbTokenizer.from_pretrained(_NLLB_NAME, src_lang="rus_Cyrl")
        nllb_model = AutoModelForSeq2SeqLM.from_pretrained(
            _NLLB_NAME, torch_dtype="auto").to("cuda")
        fr_tok_id  = nllb_tok.convert_tokens_to_ids("fra_Latn")
        _log_file.write("NLLB OK\n"); _log_file.flush()

        splash.close()
        _log_file.write("Ouverture ControlPanel...\n"); _log_file.flush()

        cp = ui.ControlPanel(whisper_model, nllb_tok, nllb_model, fr_tok_id)
        cp.show()

        _log_file.write("Boucle Qt lancee\n"); _log_file.flush()
        faulthandler.disable()
        _log_file.close()
        sys.exit(app.exec_())

    except Exception:
        traceback.print_exc(file=_log_file)
        _log_file.flush()
        raise
