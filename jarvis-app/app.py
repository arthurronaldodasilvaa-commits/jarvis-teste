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
CONFIG_FILE = STATE_FILE.parent.parent / "voice" / "config.toml"
RELOAD_FLAG = STATE_FILE.parent / "reload.flag"
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


def _patch_toml_line(text: str, key: str, val, section: str | None = None) -> str:
    """Troca o valor de `key` no config.toml preservando o resto da linha.
    Se `section` for dado, só mexe DENTRO daquela seção `[section]` — a mesma
    chave (ex: `enabled`) aparece em várias seções."""
    import re
    if isinstance(val, bool):
        rep = "true" if val else "false"
    elif isinstance(val, (int, float)):
        rep = str(val)
    else:
        rep = '"' + str(val).replace("\\", "\\\\").replace('"', '\\"') + '"'

    body, offset = text, 0
    if section:
        m = re.search(rf'^\[{re.escape(section)}\]\s*$', text, re.M)
        if not m:
            return text
        start = m.end()
        nxt = re.search(r'^\[', text[start:], re.M)
        end = start + nxt.start() if nxt else len(text)
        body, offset = text[start:end], start

    pat = re.compile(rf'^(\s*{re.escape(key)}\s*=\s*)(?:""".*?"""|".*?"|[^\s#]+)(\s*(?:#.*)?)$',
                     re.M | re.S)
    if not pat.search(body):
        return text
    new_body = pat.sub(lambda m: f"{m.group(1)}{rep}{m.group(2)}", body, count=1)
    return text[:offset] + new_body + text[offset + len(body):]


def _sapi_voices() -> list:
    import subprocess
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Add-Type -AssemblyName System.Speech; "
             "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | "
             "ForEach-Object { $_.VoiceInfo.Name }"],
            capture_output=True, text=True, timeout=12, creationflags=0x08000000)
        return [l.strip() for l in r.stdout.splitlines() if l.strip()]
    except Exception:  # noqa: BLE001
        return []


def _profile_names() -> list:
    d = CONFIG_FILE.parent / "profiles"
    return [p.stem for p in d.glob("*.toml")] if d.is_dir() else []


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

    _VK = {"next": 0xB0, "prev": 0xB1, "play": 0xB3, "stop": 0xB2,
           "vol_up": 0xAF, "vol_down": 0xAE, "mute": 0xAD,
           "next_slide": 0x27, "prev_slide": 0x25}   # seta direita / esquerda

    def media(self, action: str, times: int = 1) -> bool:
        """Tecla de mídia disparada por gesto na câmera."""
        vk = self._VK.get(action)
        if not vk:
            return False
        u = ctypes.windll.user32
        for _ in range(max(1, min(int(times), 10))):
            u.keybd_event(vk, 0, 0, 0)
            u.keybd_event(vk, 0, 2, 0)
        return True

    def scan_result(self, kind: str, text: str) -> None:
        """A câmera leu um QR/código — grava scan.json pro daemon ler."""
        import time as _t
        try:
            (STATE_FILE.parent / "scan.json").write_text(
                json.dumps({"kind": kind, "text": str(text)[:400], "n": int(_t.time() * 1000)}),
                encoding="utf-8")
        except OSError:
            pass
        self._write_control(scan="")

    # ---- reconhecimento facial ----
    def face_db(self) -> dict:
        """Rostos aprendidos: {nome: [descritor de 128 números, ...]}."""
        return _read_json(STATE_FILE.parent / "faces.json", {})

    def face_save(self, name: str, descriptors: list) -> bool:
        """Junta descritores novos ao rosto <name> (guarda no máx. 8)."""
        name = str(name).strip().lower()[:30]
        if not name or not isinstance(descriptors, list):
            return False
        db = self.face_db()
        cur = db.get(name, [])
        for d in descriptors:
            if isinstance(d, list) and len(d) == 128:
                cur.append([round(float(x), 5) for x in d])
        db[name] = cur[-8:]
        try:
            (STATE_FILE.parent / "faces.json").write_text(
                json.dumps(db), encoding="utf-8")
        except OSError:
            return False
        self._write_control(face_enroll="")          # some com o pedido
        return True

    def face_seen(self, name: str) -> None:
        """A câmera reconheceu (ou não) alguém — grava face.json pro daemon."""
        import time as _t
        try:
            (STATE_FILE.parent / "face.json").write_text(
                json.dumps({"name": str(name or ""), "n": int(_t.time() * 1000)}),
                encoding="utf-8")
        except OSError:
            pass

    def face_forget(self, name: str) -> bool:
        db = self.face_db()
        n = str(name).strip().lower()
        if n not in db:
            return False
        db.pop(n, None)
        try:
            (STATE_FILE.parent / "faces.json").write_text(json.dumps(db), encoding="utf-8")
        except OSError:
            return False
        return True

    # ---- painel de configurações ----
    _CFG_KEYS = [
        ("profile", "active"), ("assistant", "address"), ("assistant", "user_name"),
        ("assistant", "wake_word"), ("assistant", "attention_reply"),
        ("tts", "engine"), ("tts", "sapi_voice"),
        ("audio", "input_device_match"), ("app", "camera_match"), ("app", "theme"),
        ("location", "city"), ("arrival", "enabled"), ("arrival", "phrase"),
        ("arrival", "briefing"), ("camera", "media_gestures"), ("camera", "auto_return_seconds"),
        ("danger", "allow_shutdown"), ("danger", "allow_typing"),
    ]

    def get_config(self) -> dict:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib
        try:
            data = tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {"_error": "não achei config.toml"}
        out = {}
        for sec, key in self._CFG_KEYS:
            out[f"{sec}.{key}"] = data.get(sec, {}).get(key)
        # opções pra dropdowns
        out["_voices"] = _sapi_voices()
        out["_profiles"] = _profile_names()
        return out

    def set_config(self, patch: dict) -> dict:
        try:
            txt = CONFIG_FILE.read_text(encoding="utf-8")
        except OSError:
            return {"ok": False, "msg": "config.toml não encontrado"}
        for dotted, val in (patch or {}).items():
            sec, _, key = dotted.rpartition(".")
            txt = _patch_toml_line(txt, key, val, sec or None)
        try:
            CONFIG_FILE.write_text(txt, encoding="utf-8")
            RELOAD_FLAG.write_text(str(__import__("time").time()), encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "msg": str(exc)}
        return {"ok": True}

    def log(self, msg: str) -> None:
        try:
            with open(STATE_FILE.parent / "app_debug.log", "a", encoding="utf-8") as fh:
                fh.write(f"[{__import__('time').strftime('%H:%M:%S')}] {msg}\n")
        except OSError:
            pass

    def toggle_fullscreen(self) -> None:
        if webview.windows:
            webview.windows[0].toggle_fullscreen()

    def close(self) -> None:
        for w in webview.windows:
            w.destroy()


def main() -> None:
    dev = "--dev" in sys.argv
    fs = "--windowed" not in sys.argv
    if already_running():
        focus_existing()
        return

    url = serve_ui()
    win = webview.create_window(
        WINDOW_TITLE,
        url,
        width=1280,
        height=800,
        fullscreen=fs,
        frameless=True,
        easy_drag=True,
        background_color="#000000",
        js_api=Api(),
        min_size=(640, 420),
    )

    def _startup():
        if fs:
            try:
                win.maximize()
            except Exception:  # noqa: BLE001
                pass

    webview.start(_startup, debug=dev, private_mode=False)


if __name__ == "__main__":
    main()
