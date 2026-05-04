@echo off
title Subly
cd /d %~dp0
call env\Scripts\activate.bat

:: Tuer toute instance precedente
taskkill /f /im pythonw.exe >nul 2>&1
timeout /t 1 /nobreak >nul

:: Supprimer l'ancien log
if exist subly_crash.log del /f subly_crash.log

:: Lancer Subly
python -u subly.py
if errorlevel 1 (
    echo.
    echo [ERREUR] Subly a quitte avec une erreur. Voir subly_crash.log
    pause
)
