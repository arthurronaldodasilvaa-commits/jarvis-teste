@echo off
REM Inicia o Jarvis (voz + app) de forma DESTACADA — sobrevive a fechar esta janela.
setlocal

REM 1) assistente de voz (se ainda nao estiver rodando; a trava de instancia unica cuida disso)
start "" /b wscript.exe "E:\OpenJarvis\voice\run_jarvis_voice.vbs"

REM 2) app do cerebro / camera
start "" "E:\OpenJarvis\jarvis-app\dist\JarvisApp.exe"

echo Jarvis iniciado.
echo   - voz: roda escondido (feche pelo Gerenciador de Tarefas -> pythonw.exe)
echo   - app: janela em tela cheia (Esc fecha)
timeout /t 3 >nul
