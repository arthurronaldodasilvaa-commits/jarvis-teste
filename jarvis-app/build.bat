@echo off
REM Gera dist\JarvisApp.exe (executavel unico, sem console).
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe

%PY% -m PyInstaller --noconfirm --clean ^
  --name JarvisApp ^
  --onefile ^
  --noconsole ^
  --add-data "ui;ui" ^
  --collect-all webview ^
  --hidden-import webview.platforms.edgechromium ^
  --exclude-module tkinter ^
  --exclude-module numpy ^
  --exclude-module pandas ^
  --exclude-module PIL ^
  --exclude-module test ^
  --exclude-module unittest ^
  --exclude-module pydoc ^
  --exclude-module doctest ^
  --exclude-module setuptools ^
  --exclude-module pip ^
  app.py

echo.
echo Pronto: %~dp0dist\JarvisApp.exe
