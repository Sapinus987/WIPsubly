@echo off
title Subly Server
cd /d %~dp0
call env\Scripts\activate.bat

if exist subly_server.log del /f subly_server.log

echo  Subly Server demarre sur ws://0.0.0.0:8765
echo  Ctrl+C pour arreter.
echo.

python -u server.py
if errorlevel 1 (
    echo.
    echo [ERREUR] Le serveur a quitte avec une erreur.
    pause
)
