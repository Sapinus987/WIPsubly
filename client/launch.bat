@echo off
title Subly Client
cd /d %~dp0
call env\Scripts\activate.bat
python -u client.py
if errorlevel 1 (
    echo.
    echo [ERREUR] Le client a quitte avec une erreur.
    pause
)
