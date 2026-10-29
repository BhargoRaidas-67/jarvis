@echo off
setlocal EnableDelayedExpansion
title Jarvis Setup
cd /d "%~dp0"
cls

echo ============================================================
echo   JARVIS - one-time setup for Windows
echo ============================================================
echo.

REM ---------- 0. Am I in the right folder? ----------
if not exist "app.py" goto wrongfolder
if not exist "requirements.txt" goto wrongfolder
if not exist "static\index.html" (
  echo   ERROR: the "static" folder is missing.
  echo   Extract the WHOLE zip again - do not move files around one by one.
  echo.
  pause
  exit /b 1
)
echo   Location: %CD%
echo.

REM ---------- 1. Python ----------
echo [1/4] Checking Python...
set "PY="
python --version >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY (
  py --version >nul 2>&1
  if not errorlevel 1 set "PY=py"
)
if not defined PY (
  echo.
  echo   Python is not installed yet.
  echo   I am opening the download page now. Please:
  echo     1. Download "Windows installer (64-bit)"  - version 3.11 or newer
  echo     2. On the FIRST screen, TICK  "Add python.exe to PATH"
  echo     3. Click "Install Now"
  echo     4. Close this window and double-click setup.bat again
  echo.
  start https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
for /f "tokens=*" %%v in ('%PY% --version') do echo   Found %%v
echo.

REM ---------- 2. Ollama ----------
echo [2/4] Checking Ollama (the local AI engine)...
set "OLLAMA=ollama"
ollama --version >nul 2>&1
if not errorlevel 1 goto ollamaok
REM installed but PATH not refreshed? look in the default install spot
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
  set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
  goto ollamaok
)
echo.
echo   Ollama is not installed. Installing it with winget...
winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
  set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
  goto ollamaok
)
echo.
echo   Automatic install did not work. Please install it by hand:
echo     https://ollama.com/download/windows
echo   Then double-click setup.bat again.
start https://ollama.com/download/windows
pause
exit /b 1
:ollamaok
echo   Ollama found.
echo.

REM ---------- 3. Python packages ----------
echo [3/4] Installing Python packages (this takes 1-3 minutes)...
if not exist ".venv" %PY% -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo   Could not create the Python environment. Re-run setup.bat as a normal user.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo   Package install failed. Check your internet connection and run setup.bat again.
  pause
  exit /b 1
)
echo   Packages installed.
echo.

REM ---------- 4. AI model ----------
echo [4/4] Downloading the AI model.
echo.
echo    Pick the model that fits your PC's RAM:
echo      1) qwen2.5:3b    -  about 2 GB  -  works on 8 GB RAM   (recommended start)
echo      2) qwen2.5:7b    -  about 5 GB  -  best quality, needs 16 GB RAM
echo      3) llama3.2:3b   -  about 2 GB  -  light and fast
echo      4) skip for now
echo.
set "CHOICE="
set /p CHOICE="   Enter 1, 2, 3 or 4 and press Enter: "

set "MODEL="
if "%CHOICE%"=="1" set "MODEL=qwen2.5:3b"
if "%CHOICE%"=="2" set "MODEL=qwen2.5:7b"
if "%CHOICE%"=="3" set "MODEL=llama3.2:3b"

REM make sure the engine is running so the download can happen
if defined MODEL (
  tasklist /fi "imagename eq ollama.exe" | find /i "ollama.exe" >nul
  if errorlevel 1 (
    start "" "%OLLAMA%" serve
    timeout /t 4 /nobreak >nul
  )
  echo.
  echo   Downloading %MODEL% ... this can take several minutes. Do not close this window.
  "%OLLAMA%" pull %MODEL%
  if errorlevel 1 (
    echo.
    echo   The download did not finish. You can retry later with:
    echo      ollama pull %MODEL%
  )
)

echo.
echo ============================================================
echo   Setup finished.
echo   Double-click  run.bat  to start Jarvis.
echo ============================================================
echo.
pause
exit /b 0

:wrongfolder
echo.
echo   WRONG FOLDER
echo   ------------
echo   setup.bat must sit in the same folder as app.py, agent.py,
echo   tools.py and the "static" folder.
echo.
echo   Right now it is in: %CD%
echo   and app.py is not there.
echo.
echo   Fix: go back to your Downloads, right-click the jarvis zip
echo        and choose "Extract All...", then open the extracted
echo        jarvis folder and run setup.bat from inside it.
echo.
pause
exit /b 1
