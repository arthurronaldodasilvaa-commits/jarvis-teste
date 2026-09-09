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
import functools
import http.server
import json
import os
import socketserver
import sys
import threading
from pathlib import Path

# Libera câmera/mic no WebView2 sem prompt (app local pessoal). TEM que vir
# antes do import webview.
os.environ.setdefault(
    "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
    "--use-fake-ui-for-media-stream --autoplay-policy=no-user-gesture-required",
)

import webview

FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))   # recursos empacotados


def _resolve_state_file() -> Path:
    # 1) override explícito
    env = os.environ.get("JARVIS_STATE_FILE")
    if env:
        return Path(env)
    # 2) frozen: o .exe mora em jarvis-app\dist\ -> state.json fica em jarvis-app\
    if FROZEN:
        d = Path(sys.executable).resolve().parent
        return (d.parent if d.name.lower() == "dist" else d) / "state.json"
    # 3) dev: ao lado do app.py
    return Path(__file__).resolve().parent / "state.json"


STATE_FILE = _resolve_state_file()
CONTROL_FILE = STATE_FILE.parent / "control.json"
UI_DIR = APP_DIR / "ui"

MUTEX_NAME = "Global\\JarvisAppSingleton"
WINDOW_TITLE = "JARVIS"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".wasm": "application/wasm", ".data": "application/octet-stream",
                      ".tflite": "application/octet-stream", ".binarypb": "application/octet-stream",
                      ".mjs": "text/javascript", ".js": "text/javascript"}

    def log_message(self, *a):  # noqa: ARG002
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve_ui() -> str:
    """Sobe um HTTP local servindo ui/ e devolve a URL do index.
    (getUserMedia + módulos/wasm exigem origem http, não file://.)"""
    handler = functools.partial(_QuietHandler, directory=str(UI_DIR))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}/index.html"


def already_running() -> bool:
    ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def focus_existing() -> None:
    hwnd = ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 9)      # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(hwnd)


def _read_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(default)


class Api:
    """Ponte JS <-> Python. O cérebro chama get_status() ~4x/s (1 só round-trip)."""

    def get_status(self) -> dict:
        s = _read_json(STATE_FILE, {"speaking": False, "amplitude": 0.0, "status": "SISTEMA ONLINE"})
        ctl = _read_json(CONTROL_FILE, {"paused": False, "view": "brain"})
        s.update(ctl)                        # paused, view, holo, ...
        s.setdefault("view", "brain")
        s["paused"] = bool(s.get("paused", False))
        return s

    def _write_control(self, **changes) -> dict:
        cur = _read_json(CONTROL_FILE, {"paused": False, "view": "brain"})
        cur.update(changes)
        try:
            CONTROL_FILE.write_text(json.dumps(cur), encoding="utf-8")
        except OSError:
            pass
        return cur

    def toggle_pause(self) -> dict:
        return self._write_control(paused=not _read_json(CONTROL_FILE, {}).get("paused", False))

    def set_view(self, view: str) -> dict:
        return self._write_control(view="camera" if view == "camera" else "brain")

    def toggle_view(self) -> dict:
        cur = _read_json(CONTROL_FILE, {}).get("view", "brain")
        return self._write_control(view="brain" if cur == "camera" else "camera")

    def log(self, msg: str) -> None:
        try:
            with open(STATE_FILE.parent / "app_debug.log", "a", encoding="utf-8") as fh:
                fh.write(f"[{__import__('time').strftime('%H:%M:%S')}] {msg}\n")
        except OSError:
            pass

    def close(self) -> None:
        for w in webview.windows:
            w.destroy()


def main() -> None:
    dev = "--dev" in sys.argv
    if already_running():
        focus_existing()
        return

    url = serve_ui()
    webview.create_window(
        WINDOW_TITLE,
        url,
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
