@echo off
rem One-time setup: creates .venv-win and installs everything (~1.5 GB).
cd /d "%~dp0"

where py >nul 2>nul || (echo Python launcher not found - install Python 3.12 first & exit /b 1)

py -3.12 -m venv .venv-win 2>nul || py -3.11 -m venv .venv-win 2>nul || py -3.10 -m venv .venv-win
if not exist ".venv-win\Scripts\python.exe" (echo venv creation failed & exit /b 1)

.venv-win\Scripts\python -m pip install --upgrade pip
.venv-win\Scripts\pip install -r requirements-win.txt
if errorlevel 1 (echo install failed & exit /b 1)

echo.
echo Setup done. Start dictation with dictate.bat
