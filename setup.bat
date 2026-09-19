@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   IlmNote - Setup Starting...
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found.
  echo Download from: https://www.python.org/downloads/
  echo During install, tick "Add Python to PATH".
  pause
  exit /b 1
)

if not exist "venv" (
  echo Creating virtual environment...
  python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing packages...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo Creating directories...
if not exist "uploads\covers" mkdir uploads\covers
if not exist "static\fonts"    mkdir static\fonts

echo Initializing database...
python -c "from app import app; print('Database initialized.')"

echo.
echo ============================================
echo   SETUP COMPLETE.
echo   Now run start.bat to launch the app.
echo ============================================
pause