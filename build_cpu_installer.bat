@echo off
REM Build the CPU installer. Run from the repo root.
REM Requires Inno Setup 6 (ISCC.exe) on PATH, or set ISCC to its full path.
setlocal
cd /d "%~dp0"
if "%ISCC%"=="" set ISCC=ISCC.exe
"%ISCC%" /DVariant=cpu "packaging\installer.iss"
