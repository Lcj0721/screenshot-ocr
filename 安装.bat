@echo off
title Screenshot OCR - One-click Install
cd /d "%~dp0"

echo ============================================
echo    Screenshot OCR - One-click Install
echo ============================================
echo.

rem ---- 1. Find Python ----
set "PY="
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py") else (
  where python >nul 2>nul
  if %errorlevel%==0 (set "PY=python")
)

if not defined PY (
  echo [ERROR] Python not found.
  echo Please install Python 3.9+ from https://www.python.org/downloads/
  echo and CHECK "Add python.exe to PATH" during installation.
  echo Then run this script again.
  pause
  exit /b 1
)

echo [1/4] Python found: %PY%
%PY% --version

rem ---- 2. Create venv ----
echo.
echo [2/4] Creating virtual environment...
if not exist ".venv" (
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
  )
)

call .venv\Scripts\activate.bat

rem ---- 3. Install deps (Tsinghua mirror for fast CN download) ----
echo.
echo [3/4] Installing dependencies (needs internet, 1-3 min)...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple >"install.log" 2>&1
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple >>"install.log" 2>&1
if errorlevel 1 (
  echo.
  echo [ERROR] Dependency install failed. Details in install.log
  pause
  exit /b 1
)

rem ---- 3.5 Self-check ----
echo.
echo [CHECK] Verifying dependencies...
python -c "import mss, PIL, winocr, keyboard, pyperclip, pystray; print('ALL_OK')" >"check.log" 2>&1
if errorlevel 1 (
  echo [ERROR] Self-check failed. Details in check.log
  pause
  exit /b 1
)
del "check.log" >nul 2>nul
echo [CHECK] All dependencies OK.

rem ---- 4. Done ----
echo.
echo [4/4] Installation complete!
echo.
echo   Now double-click "StartOCR.bat" to run the app.
echo   Default hotkey: Ctrl + Win + X  (configurable in the app).
echo.
pause