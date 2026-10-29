@echo off
setlocal
title Jarvis
cd /d "%~dp0"

REM Make sure the Ollama engine is running in the background
tasklist /fi "imagename eq ollama.exe" | find /i "ollama.exe" >nul
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
  ) else (
    start "" ollama serve
  )
  timeout /t 4 /nobreak >nul
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py
) else (
  echo Setup has not been run yet. Please double-click setup.bat first.
  pause
  exit /b 1
)

REM Keep the window open if the server stops unexpectedly
echo.
echo Jarvis stopped. Press any key to close.
pause >nul
