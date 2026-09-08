' Inicia o Jarvis Voz sem abrir janela de terminal.
' Atalho: coloque um atalho deste arquivo em  shell:startup  para iniciar com o Windows.
Set sh = CreateObject("WScript.Shell")
py  = "E:\OpenJarvis\src\.venv\Scripts\pythonw.exe"
scr = "E:\OpenJarvis\voice\jarvis_voice.py"
sh.Run """" & py & """ """ & scr & """", 0, False
