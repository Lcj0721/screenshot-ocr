@echo off
title Screenshot OCR
cd /d "%~dp0"

set "PYEXE=.venv\Scripts\python.exe"
set "PYWEXE=.venv\Scripts\pythonw.exe"

if not exist "%PYEXE%" (
  echo.
  echo   [ERROR] Not installed yet.
  echo   Please double-click "Install.bat" first.
  echo.
  pause
  exit /b 1
)

echo Checking runtime environment...
"%PYEXE%" -c "import mss,PIL,keyboard,pyperclip,pystray" 2>"env_err.txt"
if errorlevel 1 (
  echo.
  echo   [ERROR] Dependencies incomplete. Reason:
  echo.
  type "env_err.txt"
  echo.
  echo   Fix: double-click "Install.bat" again.
  del "env_err.txt" >nul 2>nul
  pause
  exit /b 1
)
del "env_err.txt" >nul 2>nul

"%PYEXE%" -c "import winocr" >nul 2>nul
if errorlevel 1 (
  echo   [WARN] OCR engine winocr missing. Re-run Install.bat.
)

echo Starting... App stays in system tray (blue girl icon, bottom-right).
start "" "%PYWEXE%" "app.py"
timeout /t 2 >nul