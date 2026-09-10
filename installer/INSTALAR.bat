@echo off
chcp 65001 >nul
title Instalacao do Jarvis
color 0B
cd /d "%~dp0"
setlocal EnableDelayedExpansion

set BASE=%~dp0
if "%BASE:~-1%"=="\" set BASE=%BASE:~0,-1%
set PY=%BASE%\python\python.exe
set PYW=%BASE%\python\pythonw.exe

cls
echo.
echo    ============================================================
echo      J A R V I S   -   I N S T A L A C A O
echo    ============================================================
echo.
echo    Pasta: %BASE%
echo.

REM ---- checagens ----
if not exist "%PY%" (
  echo    [ERRO] Nao achei o Python em python\python.exe
  echo    Extraia a pasta INTEIRA do .zip antes de rodar isto.
  echo. & pause & exit /b 1
)
if not exist "%BASE%\voice\jarvis_voice.py" (
  echo    [ERRO] Nao achei voice\jarvis_voice.py . Pasta incompleta.
  echo. & pause & exit /b 1
)
echo    [ok] Python portatil encontrado
echo    [ok] Codigo do Jarvis encontrado
echo.

REM ---- perfil ----
set PROFILE=robson
echo    Quem vai usar o Jarvis?  (so muda como ele chama a pessoa)
echo       [1] Robson   (padrao)
echo       [2] Arthur
set /p OPT=   Escolha (Enter = 1):
if "%OPT%"=="2" set PROFILE=arthur
echo    -^> perfil: %PROFILE%
echo.

REM ---- ajustar config.toml (modelos com caminho absoluto, perfil, app) ----
echo    Ajustando a configuracao...
"%PY%" -X utf8 -c "import re,sys; p=r'%BASE%\voice\config.toml'; t=open(p,encoding='utf-8').read(); b=r'%BASE%'.replace('\\','/'); t=re.sub(r'(?m)^wake_model\s*=.*$', 'wake_model = \"'+b+'/models/faster-whisper-tiny\"', t, 1); t=re.sub(r'(?m)^command_model\s*=.*$', 'command_model = \"'+b+'/models/faster-whisper-small\"', t, 1); t=re.sub(r'(?m)^active\s*=.*$', 'active = \"%PROFILE%\"', t, 1); t=re.sub(r'(?m)^exe_path\s*=.*$', 'exe_path = \"\"', t, 1); open(p,'w',encoding='utf-8').write(t); print('   config ok')"
if errorlevel 1 ( echo    [ERRO] falha ao ajustar config & pause & exit /b 1 )

REM ---- launcher local (sem marca-da-web -> passa pelo Smart App Control) ----
echo    Criando o atalho de inicializacao...
> "%BASE%\iniciar_jarvis.vbs" echo ' Inicia o Jarvis (voz oculta + cerebro). Gerado pelo INSTALAR.bat.
>> "%BASE%\iniciar_jarvis.vbs" echo Set sh = CreateObject("WScript.Shell")
>> "%BASE%\iniciar_jarvis.vbs" echo Q = Chr(34)
>> "%BASE%\iniciar_jarvis.vbs" echo pyw = Q ^& "%PYW%" ^& Q
>> "%BASE%\iniciar_jarvis.vbs" echo sh.Run pyw ^& " " ^& Q ^& "%BASE%\voice\jarvis_voice.py" ^& Q, 0, False
>> "%BASE%\iniciar_jarvis.vbs" echo WScript.Sleep 2500
>> "%BASE%\iniciar_jarvis.vbs" echo sh.Run pyw ^& " " ^& Q ^& "%BASE%\jarvis-app\app.py" ^& Q, 0, False

REM ---- atalhos (Area de Trabalho, Menu Iniciar, Inicializar com o Windows) ----
powershell -NoProfile -Command ^
  "$w=New-Object -ComObject WScript.Shell;" ^
  "foreach($d in @($w.SpecialFolders('Desktop'), (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'), (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'))){" ^
  "  $s=$w.CreateShortcut((Join-Path $d 'Jarvis.lnk'));" ^
  "  $s.TargetPath=(Join-Path '%BASE%' 'iniciar_jarvis.vbs');" ^
  "  $s.WorkingDirectory='%BASE%'; $s.IconLocation='%SystemRoot%\System32\SHELL32.dll,13'; $s.Save() }"
echo    [ok] atalhos criados (Area de Trabalho + Menu Iniciar + inicia com o Windows)
echo.

REM ---- Ollama + modelo ----
echo    ------------------------------------------------------------
echo    O "cerebro" do Jarvis e o Ollama + o modelo qwen3.5:2b.
where ollama >nul 2>&1
if errorlevel 1 (
  echo    Ollama NAO esta instalado.
  if exist "%BASE%\ollama\OllamaSetup.exe" (
    echo    Vou abrir o instalador do Ollama. Clique em "Install", espere,
    echo    feche, e rode este INSTALAR.bat de novo.
    echo. & pause
    start "" "%BASE%\ollama\OllamaSetup.exe"
    echo. & echo    Depois que instalar o Ollama, rode este arquivo de novo.
    echo. & pause & exit /b 0
  ) else (
    echo    Baixe em  https://ollama.com/download  e instale. Depois rode
    echo    este INSTALAR.bat de novo.
    echo. & pause & exit /b 0
  )
)
ollama list 2>nul | findstr /i /c:"qwen3.5" >nul
if errorlevel 1 (
  echo    Falta baixar o modelo. Isso precisa de internet ^(~2,7 GB^).
  set /p GO=   Baixar agora? ^(s/n^):
  if /i "!GO!"=="s" (
    echo    Baixando qwen3.5:2b ... ^(pode demorar^)
    ollama pull qwen3.5:2b
  ) else (
    echo    Ok. Rode depois:  ollama pull qwen3.5:2b
  )
) else (
  echo    [ok] modelo qwen3.5:2b ja esta instalado
)
echo.

REM ---- pronto ----
echo    ============================================================
echo      PRONTO. O Jarvis foi instalado nesta pasta.
echo      - Abre junto com o Windows a partir de agora.
echo      - Atalho "Jarvis" na Area de Trabalho pra abrir na hora.
echo      - Manual completo: MANUAL.html  (dois cliques)
echo    ============================================================
echo.
set /p RUN=   Abrir o Jarvis agora? (s/n):
if /i "%RUN%"=="s" (
  start "" "%BASE%\iniciar_jarvis.vbs"
  echo    Abrindo... a janela do cerebro aparece em alguns segundos.
)
echo.
pause
