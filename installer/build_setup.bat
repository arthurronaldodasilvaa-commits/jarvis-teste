@echo off
REM Gera dist\JarvisSetup.exe  (o instalador com janela, arquivo unico).
REM Usa a venv de voz (tem sounddevice/numpy para o teste de microfone).
cd /d "%~dp0"
set PY=..\src\.venv\Scripts\python.exe

%PY% -m PyInstaller --noconfirm --clean --distpath dist --workpath build ^
  --name JarvisSetup ^
  --onefile ^
  --noconsole ^
  --collect-all sounddevice ^
  --hidden-import numpy ^
  --exclude-module matplotlib --exclude-module pandas --exclude-module PIL ^
  --exclude-module torch --exclude-module transformers ^
  jarvis_setup.py

echo.
echo Pronto: %~dp0dist\JarvisSetup.exe
