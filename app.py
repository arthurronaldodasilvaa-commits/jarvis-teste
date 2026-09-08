#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Jarvis App — janela do "cérebro" holográfico.

Independente do assistente de voz: abre e fecha sozinho. Mais pra frente o
jarvis_voice.py vai escrever em state.json e o cérebro reage (pulsa quando
o Jarvis fala). Por enquanto: fundo preto + holograma azul girando.

    python app.py            janela normal (frameless)
    python app.py --dev      com ferramentas de desenvolvedor
"""

from __future__ import annotations

import ctypes
import json
import sys
from pathlib import Path

import webview

FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))   # recursos empacotados
BASE_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent  # pasta real
STATE_FILE = BASE_DIR / "state.json"
UI = APP_DIR / "ui" / "index.html"

MUTEX_NAME = "Global\\JarvisAppSingleton"
WINDOW_TITLE = "JARVIS"


def already_running() -> bool:
    ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def focus_existing() -> None:
    hwnd = ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 9)      # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(hwnd)


class Api:
    """Ponte JS <-> Python. O cérebro chama get_state() ~5x/s."""

    def get_state(self) -> dict:
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"speaking": False, "amplitude": 0.0, "status": "SISTEMA ONLINE"}

    def ping(self) -> str:
        return "ok"

    def close(self) -> None:
        for w in webview.windows:
            w.destroy()


def main() -> None:
    dev = "--dev" in sys.argv
    if already_running():
        focus_existing()
        return

    webview.create_window(
        WINDOW_TITLE,
        str(UI),
        width=960,
        height=720,
        frameless=True,
        easy_drag=True,
        background_color="#000000",
        js_api=Api(),
        min_size=(480, 360),
    )
    webview.start(debug=dev, private_mode=False)


if __name__ == "__main__":
    main()
