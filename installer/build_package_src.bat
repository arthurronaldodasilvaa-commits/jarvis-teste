@echo off
REM ============================================================
REM  Monta o pacote "source" do Jarvis — roda com o Python
REM  portatil da python.org (assinado), sem .exe congelado.
REM  Passa pelo Smart App Control do Windows 11.
REM
REM  Pre-requisitos nesta pasta:
REM    packB_py\      = python-3.11.x-embed-amd64.zip extraido
REM    packB_libs\    = pip install --target packB_libs -r requirements-runtime.txt
REM    OllamaSetup.exe (opcional)
REM ============================================================
cd /d "%~dp0"
set OUT=pacoteB\Jarvis
set PY=..\src\.venv\Scripts\python.exe

echo Limpando %OUT% ...
if exist pacoteB rmdir /s /q pacoteB
mkdir "%OUT%"

echo [1/7] Python portatil ...
xcopy /e /i /q /y "packB_py" "%OUT%\python" >nul
> "%OUT%\python\python311._pth" echo python311.zip
>> "%OUT%\python\python311._pth" echo .
>> "%OUT%\python\python311._pth" echo ..\libs
>> "%OUT%\python\python311._pth" echo ..\voice
>> "%OUT%\python\python311._pth" echo ..\jarvis-app

echo [2/7] Bibliotecas (libs) ...
xcopy /e /i /q /y "packB_libs" "%OUT%\libs" >nul
del /q "%OUT%\libs\*.whl" 2>nul
del /q "%OUT%\libs\*.pth" 2>nul
for /d /r "%OUT%\libs" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

echo [3/7] Codigo do assistente de voz ...
mkdir "%OUT%\voice"
copy /y "..\voice\*.py"    "%OUT%\voice\" >nul
copy /y "..\voice\*.toml"  "%OUT%\voice\" >nul
xcopy /e /i /q /y "..\voice\study"    "%OUT%\voice\study" >nul
xcopy /e /i /q /y "..\voice\profiles" "%OUT%\voice\profiles" >nul
xcopy /e /i /q /y "..\voice\piper"    "%OUT%\voice\piper" >nul
copy /y "..\manual\jarvis-manual.html" "%OUT%\voice\manual.html" >nul
del /q "%OUT%\voice\test_audio.py" 2>nul
for /d /r "%OUT%\voice" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

echo [4/7] Codigo do cerebro holografico ...
mkdir "%OUT%\jarvis-app"
copy /y "..\jarvis-app\app.py" "%OUT%\jarvis-app\" >nul
xcopy /e /i /q /y "..\jarvis-app\ui" "%OUT%\jarvis-app\ui" >nul

echo [5/7] Modelos de voz (faster-whisper) ...
%PY% prep_models.py "%OUT%\models"

echo [6/7] Instalador do Ollama ...
mkdir "%OUT%\ollama"
if exist "OllamaSetup.exe" (
  copy /y "OllamaSetup.exe" "%OUT%\ollama\OllamaSetup.exe" >nul
) else (
  echo   AVISO: OllamaSetup.exe nao encontrado. O INSTALAR.bat vai mandar
  echo   o usuario baixar de ollama.com.
)

echo [7/7] Instalador + docs ...
copy /y "INSTALAR.bat"                  "%OUT%\INSTALAR.bat" >nul
copy /y "DIAGNOSTICO_src.bat"           "%OUT%\DIAGNOSTICO.bat" >nul
copy /y "LEIA-ME_src.txt"               "%OUT%\LEIA-ME.txt" >nul
if exist "..\COMANDOS.md" copy /y "..\COMANDOS.md" "%OUT%\COMANDOS.md" >nul
copy /y "..\manual\jarvis-manual.html"  "%OUT%\MANUAL.html" >nul

echo.
echo Pasta montada em:  %~dp0%OUT%
echo.
echo IMPORTANTE: antes de compactar, teste rodando INSTALAR.bat de dentro
echo de %OUT% . E avise o Robson pra DESBLOQUEAR o .zip (botao direito ^>
echo Propriedades ^> Desbloquear) ANTES de extrair.
