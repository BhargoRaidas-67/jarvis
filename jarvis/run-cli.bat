@echo off
title Jarvis (terminal)
cd /d "%~dp0"
chcp 65001 >nul

REM start the Ollama engine if it is not already running
tasklist /fi "imagename eq ollama.exe" | find /i "ollama.exe" >nul
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
    timeout /t 4 /nobreak >nul
  )
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" cli.py %*
) else (
  python cli.py %*
)

echo.
pause
