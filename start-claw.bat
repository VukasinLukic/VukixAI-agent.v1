@echo off
chcp 65001 >nul
title Agent | Lokalni AI Agent
color 0A

echo.
echo  ==========================================
echo   Agent ^| Lokalni AI Agent
echo   Model: qwen3-coder:30b ^| Ollama
echo  ==========================================
echo.

set OLLAMA_MODEL=qwen3-coder:30b
set OLLAMA_BASE_URL=http://localhost:11434
set PYTHONUTF8=1

echo [1] Provjeravam Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [!] Ollama nije aktivna. Pokrecujem u pozadini...
    start /min "" ollama serve
    timeout /t 4 /nobreak >nul
    echo [OK] Ollama pokrenuta.
) else (
    echo [OK] Ollama vec radi.
)

echo.
echo [2] Ulazim u claw-code direktorijum...
cd /d "%~dp0claw-code"

echo [3] Pokrecujem interaktivni chat...
echo.
python -m src.main chat
pause
