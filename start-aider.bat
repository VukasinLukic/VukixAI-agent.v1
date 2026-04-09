@echo off
chcp 65001 >nul
title Aider — Lokalni AI Coding Agent
color 0B

echo.
echo  ==========================================
echo   Aider ^| Git-Native AI Coding Agent
echo   Model: qwen2.5-coder:14b ^| Ollama
echo  ==========================================
echo.

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
echo [2] Provjeravam Aider (Python 3.12)...
py -3.12 -m aider --version >nul 2>&1
if errorlevel 1 (
    echo [!] Aider nije instaliran. Instaliram na Python 3.12...
    py -3.12 -m pip install aider-chat
)

echo.
echo [3] Pokrecujem Aider u trenutnom folderu...
echo     Ukucaj /help za listu komandi, /exit za izlaz.
echo.

set OLLAMA_API_BASE=http://localhost:11434

if "%1"=="" (
    py -3.12 -m aider --model ollama_chat/qwen2.5-coder:7b --no-show-model-warnings
) else (
    py -3.12 -m aider --model ollama_chat/qwen2.5-coder:7b --no-show-model-warnings %*
)
pause
