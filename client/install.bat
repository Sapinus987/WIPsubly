@echo off
title Subly Client — Installation
chcp 65001 >nul
cd /d %~dp0
echo.
echo  ============================================
echo   Subly Client  --  Installation
echo  ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python introuvable. Installe Python 3.10+ depuis https://www.python.org/
    pause & exit /b 1
)

echo [1/3] Creation de l'environnement virtuel...
python -m venv env
call env\Scripts\activate.bat

echo [2/3] Mise a jour pip...
python -m pip install --upgrade pip --quiet

echo [3/3] Dependances Python...
pip install PyQt5 websockets --quiet

echo.
echo  ============================================
echo   Installation terminee.
echo   Lance launch.bat pour demarrer le client.
echo  ============================================
echo.
pause
