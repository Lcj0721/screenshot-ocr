@echo off
title Screenshot OCR (Debug)
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Please run "Install.bat" first.
  pause
  exit /b 1
)

echo Debug mode: errors will show in this window. Keep it open.
echo.
".venv\Scripts\python.exe" "app.py"
echo.
echo App exited. If you see a red error above, send it to the author.
pause