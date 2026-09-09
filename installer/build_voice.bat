@echo off
REM Congela o daemon de voz -> dist\JarvisVoice\  (pasta, ~350 MB).
cd /d "%~dp0"
set PY=..\src\.venv\Scripts\python.exe
%PY% -m PyInstaller --noconfirm --clean --distpath dist --workpath build JarvisVoice.spec
echo.
echo Pronto: %~dp0dist\JarvisVoice\JarvisVoice.exe
