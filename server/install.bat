@echo off
title Subly Server — Installation
chcp 65001 >nul
cd /d %~dp0
echo.
echo  ============================================
echo   Subly Server  --  Installation
echo  ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python introuvable. Installe Python 3.10+ depuis https://www.python.org/
    pause & exit /b 1
)

echo [1/5] Creation de l'environnement virtuel...
python -m venv env
call env\Scripts\activate.bat

echo [2/5] Mise a jour pip...
python -m pip install --upgrade pip --quiet

echo [3/5] Dependances Python...
pip install fastapi "uvicorn[standard]" websockets faster-whisper streamlink transformers sentencepiece numpy --quiet

echo [4/5] PyTorch CUDA 11.8...
pip install torch --index-url https://download.pytorch.org/whl/cu118 --quiet

echo [5/5] Librairies CUDA...
pip install "nvidia-cublas-cu12==12.3.4.1" "nvidia-cudnn-cu12==9.1.0.70" --quiet

echo [6/6] Telechargement ffmpeg...
powershell -Command "Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'ffmpeg.zip'" >nul
powershell -Command "Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'ffmpeg_tmp' -Force" >nul
if not exist ffmpeg\bin mkdir ffmpeg\bin
powershell -Command "Get-ChildItem 'ffmpeg_tmp' -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1 | Copy-Item -Destination 'ffmpeg\bin\ffmpeg.exe' -Force" >nul
rmdir /s /q ffmpeg_tmp >nul 2>&1
del ffmpeg.zip >nul 2>&1

echo.
echo  ============================================
echo   Installation terminee.
echo   Lance launch.bat pour demarrer le serveur.
echo  ============================================
echo.
pause
