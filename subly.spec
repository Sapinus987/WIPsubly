# -*- mode: python ; coding: utf-8 -*-
"""
Spec PyInstaller pour Subly — build onedir, sans console.

Stratégie DLL CUDA :
  1. ctranslate2.dll + libiomp5md.dll  → depuis le package ctranslate2
  2. cudnn64_9.dll (version complète)  → depuis nvidia-cudnn-cu12 (écrase le stub ct2)
  3. cublas*.dll                        → depuis nvidia-cublas-cu12
Toutes les DLLs atterrissent à la racine de dist/subly/ — chemin cherché en
premier par Windows, et ajouté via os.add_dll_directory() au démarrage.
"""
import os
import glob
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all

SITE = os.path.join(SPECPATH, "env", "Lib", "site-packages")

# ── DLLs CUDA ──────────────────────────────────────────────────────────────────
_binaries = []

# ctranslate2 : DLL runtime + OpenMP (on exclut son stub cudnn, remplacé ci-après)
for _dll in glob.glob(os.path.join(SITE, "ctranslate2", "*.dll")):
    if "cudnn" not in os.path.basename(_dll).lower():
        _binaries.append((_dll, "."))

# cublas
for _dll in glob.glob(os.path.join(SITE, "nvidia", "cublas", "bin", "*.dll")):
    _binaries.append((_dll, "."))

# cudnn complet (remplace le stub de ctranslate2)
for _dll in glob.glob(os.path.join(SITE, "nvidia", "cudnn", "bin", "*.dll")):
    _binaries.append((_dll, "."))

# ffmpeg
_binaries.append((
    os.path.join(SPECPATH, "ffmpeg", "bin", "ffmpeg.exe"),
    os.path.join("ffmpeg", "bin"),
))

# ── Imports dynamiques (transformers, streamlink) ──────────────────────────────
_tf_datas, _tf_binaries, _tf_hidden = collect_all("transformers")
_sl_hidden = collect_submodules("streamlink")

# ── Données embarquées ────────────────────────────────────────────────────────
_datas = (
    _tf_datas
    + collect_data_files("faster_whisper")   # inclut assets/silero_vad_v6.onnx
    + collect_data_files("ctranslate2")      # inclut specs/*.py
    + collect_data_files("huggingface_hub")
    + collect_data_files("sentencepiece")
)

# ── Analyse ───────────────────────────────────────────────────────────────────
a = Analysis(
    ["subly.py"],
    pathex=[SPECPATH],
    binaries=_binaries + _tf_binaries,
    datas=_datas,
    hiddenimports=_tf_hidden + _sl_hidden + [
        "faster_whisper",
        "faster_whisper.transcribe",
        "faster_whisper.audio",
        "faster_whisper.tokenizer",
        "faster_whisper.feature_extractor",
        "faster_whisper.vad",
        "ctranslate2",
        "ctranslate2.specs",
        "ctranslate2.extensions",
        "sentencepiece",
        "huggingface_hub",
        "huggingface_hub.utils",
        "numpy",
        "PyQt5.QtWidgets",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "ui",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "PIL", "IPython", "jupyter",
        "notebook", "tkinter", "wx",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="subly",
    debug=False,
    strip=False,
    upx=False,          # UPX desactive : incompatible avec certaines DLLs CUDA
    console=False,      # Pas de fenetre console
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="subly",
)
