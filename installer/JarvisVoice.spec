# -*- mode: python ; coding: utf-8 -*-
# Congela o daemon de voz (jarvis_voice.py) numa pasta dist/JarvisVoice/.
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []
for pkg in ("faster_whisper", "ctranslate2", "av", "onnxruntime", "tokenizers", "winsdk"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass

hiddenimports += collect_submodules("numpy")
hiddenimports += collect_submodules("winsdk")
hiddenimports += ["sounddevice", "_sounddevice", "httpx", "httpcore", "sniffio",
                  "anyio", "certifi", "psutil", "pynvml", "pypdf"]
# módulos do Jarvis importados de forma tardia (dentro de funções)
hiddenimports += ["hooks", "llm", "skills_extra", "study", "teach", "invent",
                  "face", "facts", "materials", "tasks", "read_aloud", "aula",
                  "diary", "reminders", "weather", "calc", "news", "media", "wiki",
                  "translate", "maps", "spotify", "hud", "skills", "remote"]
hiddenimports += collect_submodules("qrcode")

import os as _os
_piper = "../voice/piper"
if _os.path.isdir(_piper):
    datas += [(_piper, "piper")]
# página do controle-pelo-celular (remote.py serve este HTML)
if _os.path.isfile("../voice/remote_page.html"):
    datas += [("../voice/remote_page.html", ".")]

a = Analysis(
    ["../voice/jarvis_voice.py"],
    pathex=["../voice"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "pandas", "PIL", "test", "unittest",
              "pydoc", "doctest", "setuptools", "pip", "torch", "transformers"],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="JarvisVoice", console=False, disable_windowed_traceback=False,
    upx=False,
)
# gêmeo COM console — só pra diagnóstico ("por que não abre?"). Compartilha o
# mesmo _internal. Robson roda este e vê o erro na tela.
exe_diag = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="JarvisVoice_diag", console=True, disable_windowed_traceback=False,
    upx=False,
)
coll = COLLECT(exe, exe_diag, a.binaries, a.datas, strip=False, upx=False, name="JarvisVoice")
