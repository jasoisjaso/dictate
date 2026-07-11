@echo off
setlocal
cd /d "%~dp0\.."

REM ---------------------------------------------------------------------------
REM Nuitka standalone build (folder, NOT onefile: fewer AV false positives,
REM faster start). Produces build\main.dist\Dictate.exe
REM
REM   packaging\build_nuitka.bat        -> GPU build (bundles CUDA wheels, big)
REM   packaging\build_nuitka.bat cpu    -> CPU-only build (small, runs anywhere)
REM ---------------------------------------------------------------------------

call .venv-win\Scripts\activate.bat
python -m pip install -q nuitka || goto :err

set VARIANT=%1
if "%VARIANT%"=="" set VARIANT=gpu

set EXTRA=
if /i "%VARIANT%"=="gpu" (
  set EXTRA=--include-data-dir=.venv-win\Lib\site-packages\nvidia=nvidia
  echo Building GPU variant [bundles cuBLAS/cuDNN, ~1.5 GB]
) else (
  echo Building CPU variant [no CUDA libs, much smaller]
)

python -m nuitka ^
  --standalone ^
  --assume-yes-for-downloads ^
  --enable-plugin=pyside6 ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=assets\dictate.ico ^
  --company-name=Dictate ^
  --product-name=Dictate ^
  --file-version=1.0.0 ^
  --product-version=1.0.0 ^
  --include-package=faster_whisper ^
  --include-package-data=faster_whisper ^
  --include-package=av ^
  --include-package=ctranslate2 ^
  --include-package=onnxruntime ^
  --include-package=src ^
  --include-data-dir=config=config ^
  %EXTRA% ^
  --output-dir=build ^
  --output-filename=Dictate.exe ^
  dictate_launcher.py || goto :err

echo.
echo Built build\dictate_launcher.dist\Dictate.exe (%VARIANT% variant)
exit /b 0

:err
echo BUILD FAILED
exit /b 1
