@echo off
title Subly — Installation
chcp 65001 >nul
echo.
echo  ============================================
echo   Subly  --  Installation
echo  ============================================
echo.

:: Verifier Python 3.8+ (requis pour os.add_dll_directory)
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou introuvable dans PATH.
    echo Telecharge Python 3.10+ sur https://www.python.org/downloads/
    pause & exit /b 1
)

echo [1/6] Creation de l'environnement virtuel...
python -m venv env
call env\Scripts\activate.bat

echo [2/6] Mise a jour de pip...
python -m pip install --upgrade pip --quiet

echo [3/6] Dependances Python...
pip install faster-whisper streamlink transformers sentencepiece PyQt5 numpy --quiet

echo [4/6] PyTorch CUDA 11.8...
pip install torch --index-url https://download.pytorch.org/whl/cu118 --quiet

echo [5/6] Librairies CUDA (versions compatibles CTranslate2 4.x)...
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
echo   Lance lancer.bat pour demarrer Subly.
echo  ============================================
echo.
pause
