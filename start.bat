@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment not found.
  echo Please run setup.bat first.
  pause
  exit /b 1
)

call venv\Scripts\activate.bat

echo Starting IlmNote...
start "" http://127.0.0.1:5000
python app.py

pause