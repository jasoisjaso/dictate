@echo off
rem Start Dictate in the background (tray icon, no console window).
cd /d "%~dp0"
if not exist ".venv-win\Scripts\pythonw.exe" (echo Run setup-windows.bat first & pause & exit /b 1)
start "" ".venv-win\Scripts\pythonw.exe" -m src.main
