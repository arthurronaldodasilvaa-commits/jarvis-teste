@echo off
REM ============================================================
REM  Monta a pasta "Jarvis (instalador)" pronta pra subir no Drive.
REM  Rode DEPOIS de:
REM     build_voice.bat      (gera dist\JarvisVoice\)
REM     ..\jarvis-app\build.bat  (gera ..\jarvis-app\dist\JarvisApp.exe)
REM     build_setup.bat     (gera dist\JarvisSetup.exe)
REM  E de ter baixado o OllamaSetup.exe (ver MONTAR_PACOTE.md).
REM ============================================================
cd /d "%~dp0"
set OUT=pacote\Jarvis
set PY=..\src\.venv\Scripts\python.exe

echo Limpando %OUT% ...
if exist pacote rmdir /s /q pacote
mkdir "%OUT%\payload"

echo [1/6] daemon de voz ...
xcopy /e /i /y "dist\JarvisVoice" "%OUT%\payload\voice" >nul
copy /y "..\voice\config.toml"        "%OUT%\payload\voice\config.toml" >nul
copy /y "..\voice\hooks.toml"         "%OUT%\payload\voice\hooks.toml" >nul
copy /y "..\voice\skills_extra.toml"  "%OUT%\payload\voice\skills_extra.toml" >nul
if exist "..\voice\skills_learned.toml" copy /y "..\voice\skills_learned.toml" "%OUT%\payload\voice\skills_learned.toml" >nul
xcopy /e /i /y "..\voice\profiles"  "%OUT%\payload\voice\profiles" >nul
xcopy /e /i /y "..\voice\study"     "%OUT%\payload\voice\study" >nul
REM padroes do pacote: perfil = robson, tema = cyan (o config de dev pode ter outros)
%PY% -c "import re,pathlib; p=pathlib.Path(r'%OUT%\payload\voice\config.toml'); t=p.read_text(encoding='utf-8'); t=re.sub(r'(?m)^active\s*=\s*\S+', 'active = \"robson\"', t, count=1); t=re.sub(r'(?m)^theme\s*=\s*\"\w+\"', 'theme = \"cyan\"', t, count=1); p.write_text(t, encoding='utf-8')"

echo [2/6] aplicativo (cerebro holografico) ...
mkdir "%OUT%\payload\jarvis-app"
copy /y "..\jarvis-app\dist\JarvisApp.exe" "%OUT%\payload\jarvis-app\JarvisApp.exe" >nul

echo [3/6] modelos de voz (faster-whisper) ...
%PY% prep_models.py "%OUT%\payload\models"

echo [4/6] instalador do Ollama ...
mkdir "%OUT%\payload\ollama"
if exist "OllamaSetup.exe" (
  copy /y "OllamaSetup.exe" "%OUT%\payload\ollama\OllamaSetup.exe" >nul
) else (
  echo   AVISO: OllamaSetup.exe nao encontrado nesta pasta.
  echo   Baixe de https://ollama.com/download/OllamaSetup.exe e rode de novo,
  echo   ou o instalador vai mandar o usuario baixar do site.
)

echo [5/6] o instalador + manual ...
copy /y "dist\JarvisSetup.exe" "%OUT%\JarvisSetup.exe" >nul
copy /y "LEIA-ME.txt" "%OUT%\LEIA-ME.txt" >nul
if exist "..\COMANDOS.md" copy /y "..\COMANDOS.md" "%OUT%\COMANDOS.md" >nul
REM manual html: no lugar que o daemon abre ("Jarvis, abre o manual") + na raiz pra pre-visualizar
if exist "..\manual\jarvis-manual.html" (
  copy /y "..\manual\jarvis-manual.html" "%OUT%\payload\voice\manual.html" >nul
  copy /y "..\manual\jarvis-manual.html" "%OUT%\MANUAL.html" >nul
)

echo [6/6] pronto.
echo.
echo Pasta montada em:  %~dp0%OUT%
echo Suba a pasta "Jarvis" inteira no Google Drive e compartilhe com seu pai.
