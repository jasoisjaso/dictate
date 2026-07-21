@echo off
setlocal
cd /d "%~dp0\.."

REM ---------------------------------------------------------------------------
REM Build the PORTABLE edition: a folder you drop on a USB stick and run.
REM No installer, no admin, no writes to the host beyond a temp lock file.
REM
REM   packaging\make_portable.bat        -> GPU edition (CUDA bundled, turbo+small models)
REM   packaging\make_portable.bat cpu    -> CPU edition (small model, runs anywhere)
REM ---------------------------------------------------------------------------

set VARIANT=%1
if "%VARIANT%"=="" set VARIANT=gpu
set OUT=portable\Dictate-Portable-%VARIANT%

call packaging\build_nuitka.bat %VARIANT% || goto :err

echo Assembling %OUT% ...
if exist "%OUT%" rmdir /s /q "%OUT%"
robocopy build\dictate_launcher.dist "%OUT%" /E /NFL /NDL /NJH /NJS
if errorlevel 8 goto :err

REM The marker file that flips paths.py into portable mode.
> "%OUT%\portable.txt" echo Dictate portable mode: config, models and logs live in the Data folder next to this file.

REM Pre-bundle the small model (multilingual, runs on anything) so the stick
REM works with NO internet on the host. On a GPU host WITH internet the app
REM upgrades itself: it fetches the big turbo model once, onto the stick.
REM (Not pre-bundled: it would push the zip past Gitea's 2 GB release limit.)
echo Downloading speech model into %OUT%\Data\models ...
.venv-win\Scripts\python.exe -c "from faster_whisper.utils import download_model; download_model('small', cache_dir=r'%OUT%\Data\models'); print('model bundled')" || goto :err

REM Dad-proof pointer at the top level of the stick folder (EN + BS).
(
echo Dictate Portable — voice typing off this USB stick.
echo.
echo 1. Open the Dictate-Portable-%VARIANT% folder.
echo 2. Double-click Dictate.exe
echo    ^(Windows may show "Windows protected your PC" — click "More info",
echo    then "Run anyway". It appears because this free app isn't code-signed.^)
echo 3. Look for the green microphone in the system tray ^(bottom-right^).
echo 4. Hold RIGHT CTRL and talk. Let go. Your words get typed.
echo.
echo Everything stays on this stick: settings, speech models, logs.
echo Nothing is installed on the computer and no admin password is needed.
echo.
echo ----------------------------------------------------------------------
echo.
echo BOSANSKI — Diktiranje glasom direktno sa ovog USB stika.
echo.
echo 1. Otvorite folder Dictate-Portable-%VARIANT%.
echo 2. Dupli klik na Dictate.exe
echo    ^(Windows moze prikazati upozorenje — kliknite "More info",
echo    zatim "Run anyway". Aplikacija je besplatna i nije potpisana.^)
echo 3. Zelena ikona mikrofona se pojavi pored sata ^(dole desno^).
echo 4. Drzite DESNI CTRL i govorite. Pustite. Rijeci se upisu.
echo.
echo U Postavkama izaberite bosanski jezik — i meni aplikacije se
echo automatski prebaci na bosanski.
echo.
echo Sve ostaje na ovom stiku: postavke, modeli, zapisi.
echo Nista se ne instalira na racunar i ne treba administratorska lozinka.
) > "%OUT%\README-FIRST.txt"

echo Zipping (this takes a while for the gpu edition)...
if exist "portable\Dictate-Portable-%VARIANT%.zip" del "portable\Dictate-Portable-%VARIANT%.zip"
tar -a -c -C portable -f "portable\Dictate-Portable-%VARIANT%.zip" "Dictate-Portable-%VARIANT%"
if errorlevel 1 goto :err

echo.
echo Done: portable\Dictate-Portable-%VARIANT%.zip
exit /b 0

:err
echo PORTABLE BUILD FAILED
exit /b 1
