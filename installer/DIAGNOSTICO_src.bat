@echo off
chcp 65001 >nul
title Jarvis - Diagnostico
color 0B
cd /d "%~dp0"
setlocal
set BASE=%~dp0
if "%BASE:~-1%"=="\" set BASE=%BASE:~0,-1%

echo ============================================================
echo   JARVIS - DIAGNOSTICO   (manda o print desta tela pro Arthur)
echo ============================================================
echo.
echo Pasta: %BASE%
echo.

echo --- Arquivos principais ----------------------------------
if exist "%BASE%\python\python.exe"          (echo   [ok] python\python.exe) else (echo   [FALTA] python\python.exe)
if exist "%BASE%\python\pythonw.exe"         (echo   [ok] python\pythonw.exe) else (echo   [FALTA] python\pythonw.exe)
if exist "%BASE%\libs\numpy"                 (echo   [ok] libs\numpy) else (echo   [FALTA] libs\  ^(extraiu o zip inteiro?^))
if exist "%BASE%\voice\jarvis_voice.py"      (echo   [ok] voice\jarvis_voice.py) else (echo   [FALTA] voice\jarvis_voice.py)
if exist "%BASE%\voice\config.toml"          (echo   [ok] voice\config.toml) else (echo   [FALTA] voice\config.toml ^(rodou o INSTALAR.bat?^))
if exist "%BASE%\models\faster-whisper-tiny\model.bin" (echo   [ok] modelos de voz) else (echo   [FALTA] models\ ^(baixa incompleto?^))
echo.

echo --- Windows / CPU ---------------------------------------
ver
wmic cpu get name /value 2>nul | find "Name"
echo.

echo --- Smart App Control -----------------------------------
powershell -NoProfile -Command "try{ (Get-MpComputerStatus).SmartAppControlState }catch{ 'nao consegui ler' }"
echo   (Se aparecer 'On' ou 'Eval' e o Jarvis nao abrir mesmo assim, me avise.)
echo.

echo --- Ollama ---------------------------------------------
where ollama >nul 2>&1 && (ollama list 2>nul) || echo   [X] ollama nao esta no PATH
echo.

echo ============================================================
echo   RODANDO O JARVIS COM JANELA  (o erro, se tiver, aparece aqui)
echo   Deixe rodar uns 40 segundos. Se ficar escrito "escuta ATIVA",
echo   ta funcionando. Depois feche esta janela.
echo ============================================================
echo.
"%BASE%\python\python.exe" "%BASE%\voice\jarvis_voice.py"

echo.
echo --- Ultimas linhas do log -------------------------------
if exist "%BASE%\voice\jarvis_voice.log" (
  powershell -NoProfile -Command "Get-Content '%BASE%\voice\jarvis_voice.log' -Tail 25"
) else (
  echo   (nenhum log criado - nem chegou a iniciar)
)
echo.
pause
