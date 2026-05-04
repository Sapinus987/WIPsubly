@echo off
title Subly — Build
chcp 65001 >nul
cd /d %~dp0

call env\Scripts\activate.bat

echo.
echo  ============================================
echo   Subly  --  Build executable
echo  ============================================
echo.

echo [1/3] Verification PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo     Installation de PyInstaller...
    pip install pyinstaller --quiet
)
echo     OK

echo [2/3] Nettoyage des anciens builds...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
echo     OK

echo [3/3] Build en cours (peut prendre plusieurs minutes)...
pyinstaller subly.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERREUR] Le build a echoue.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   Build termine avec succes.
echo   Executable : dist\subly\subly.exe
echo  ============================================
echo.
pause
