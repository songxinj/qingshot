@echo off
cd /d "%~dp0"
set "QINGSHOT_PYTHON=python"
set "QINGSHOT_PYTHONW=pythonw"
if exist "%~dp0.venv\Scripts\python.exe" (
  set "QINGSHOT_PYTHON=%~dp0.venv\Scripts\python.exe"
  set "QINGSHOT_PYTHONW=%~dp0.venv\Scripts\pythonw.exe"
)
"%QINGSHOT_PYTHON%" -c "import PySide6" >nul 2>&1
if errorlevel 1 (
  echo Please run: "%QINGSHOT_PYTHON%" -m pip install -r requirements.txt
  pause
  exit /b 1
)
start "" "%QINGSHOT_PYTHONW%" "%~dp0app.py"
