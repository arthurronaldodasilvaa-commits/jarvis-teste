@echo off
title Jarvis - Diagnostico
color 0B
cd /d "%~dp0"
setlocal

echo ============================================================
echo   JARVIS - DIAGNOSTICO
echo   (manda o resultado inteiro desta tela pro Arthur)
echo ============================================================
echo.

REM --- acha a pasta voice ---
set VOICE=
if exist "voice\JarvisVoice.exe"        set VOICE=voice
if exist "payload\voice\JarvisVoice.exe" set VOICE=payload\voice
if "%VOICE%"=="" (
  echo [X] Nao achei JarvisVoice.exe. Rode este arquivo de DENTRO da pasta
  echo     onde o Jarvis foi instalado (a que tem a pasta "voice").
  echo.
  pause
  exit /b
)
echo [OK] pasta do Jarvis: %CD%\%VOICE%
echo.

echo --- Arquivos principais -------------------------------------
if exist "%VOICE%\JarvisVoice.exe"      (echo   [OK] JarvisVoice.exe) else (echo   [FALTA] JarvisVoice.exe)
if exist "%VOICE%\JarvisVoice_diag.exe" (echo   [OK] JarvisVoice_diag.exe) else (echo   [FALTA] JarvisVoice_diag.exe)
if exist "%VOICE%\_internal"            (echo   [OK] _internal\) else (echo   [FALTA] _internal\  ^<-- provavel antivirus)
if exist "%VOICE%\config.toml"          (echo   [OK] config.toml) else (echo   [FALTA] config.toml)
if exist "%VOICE%\_internal\python311.dll" (echo   [OK] python311.dll) else (echo   [FALTA] python311.dll  ^<-- provavel antivirus)
echo.

echo --- Windows / CPU ------------------------------------------
ver
wmic cpu get name /value 2>nul | find "Name"
echo.

echo --- Visual C++ Redistributable ----------------------------
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed 2>nul | find "Installed" >nul && (echo   [OK] VC++ 2015-2022 x64 instalado) || (echo   [FALTA] VC++ Redistributable x64  ^<-- pode ser a causa)
echo.

echo --- Ollama ------------------------------------------------
where ollama >nul 2>&1 && (ollama list 2>nul) || echo   [X] ollama nao encontrado no PATH
echo.

echo --- Antivirus: ameacas recentes --------------------------
powershell -NoProfile -Command "try{ Get-MpThreatDetection -ErrorAction Stop | Sort-Object InitialDetectionTime -Descending | Select-Object -First 5 InitialDetectionTime, @{n='Ameaca';e={$_.ThreatID}}, Resources | Format-List }catch{ 'sem dados do Defender (ou outro antivirus)' }"
echo.

echo ============================================================
echo   RODANDO O JARVIS COM JANELA (voce vai VER o erro, se tiver)
echo   Deixe aberto uns 30 segundos. Depois feche esta janela.
echo ============================================================
echo.
"%VOICE%\JarvisVoice_diag.exe"

echo.
echo --- Ultimas linhas do log --------------------------------
if exist "%VOICE%\jarvis_voice.log" (
  powershell -NoProfile -Command "Get-Content '%VOICE%\jarvis_voice.log' -Tail 25"
) else (
  echo   (nenhum jarvis_voice.log foi criado - o programa nem chegou a iniciar)
)
echo.
pause
