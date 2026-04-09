@echo off
chcp 65001 >nul
title VukixAI — Instalacija

echo.
echo  ==========================================
echo   VukixAI — Instalacija lokalne AI komande
echo  ==========================================
echo.

cd /d "%~dp0"

echo [1] Instaliram vukixAI paket (editable)...
pip install -e . --quiet
if errorlevel 1 (
    echo [!] pip install nije uspio. Provjeravamo Python...
    python --version
    pause
    exit /b 1
)
echo [OK] Paket instaliran.

echo.
echo [2] Testiram komandu...
python -m src.main summary >nul 2>&1
if errorlevel 1 (
    echo [!] Komanda ne radi. Provjeri greske gore.
) else (
    echo [OK] vukixAI komanda radi!
)

echo.
echo ==========================================
echo  Gotovo! Sada mozes koristiti:
echo.
echo    vukixAI          — pokreni chat
echo    vukixAI chat     — interaktivni chat
echo    vukixAI summary  — prikazi status
echo.
echo  Ili iz bilo kog foldera u terminalu:
echo    vukixAI
echo ==========================================
echo.
pause
