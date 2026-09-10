#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Utilitários compartilhados entre jarvis_voice.py e skills.py."""

from __future__ import annotations

import ctypes
import os
import re
import sys
import time
import unicodedata
from functools import lru_cache
from pathlib import Path

# Congelado (PyInstaller): a pasta é a do .exe, não a de extração temporária.
if getattr(sys, "frozen", False):
    HERE = Path(sys.executable).resolve().parent
else:
    HERE = Path(__file__).resolve().parent
LOG_PATH = HERE / "jarvis_voice.log"

# Arquivos compartilhados com o Jarvis App (pasta jarvis-app\).
_SHARED = HERE.parent / "jarvis-app"
APP_STATE_FILE = _SHARED / "state.json"        # daemon -> app  (o que o Jarvis está fazendo)
CONTROL_FILE = _SHARED / "control.json"        # app/atalho <-> daemon  (ligado/pausado)

_app_state = {"speaking": False, "amplitude": 0.0, "status": "SISTEMA ONLINE",
              "view": "brain", "camera_match": "Brio", "phase": "idle",
              "weather": "", "track": {}, "sys": {}, "notes": [], "study": None,
              "tasks": [], "timer": {"end": 0}}
_NOTES: list[dict] = []


def _atomic_write(path: Path, text: str) -> bool:
    """Grava via arquivo temporário + os.replace (troca atômica no mesmo volume).
    O app lê state.json 4x/s — sem isto, uma leitura pode pegar o arquivo pela
    metade e falhar o parse (HUD pisca). À prova de disco cheio / lock / erro
    de serialização: nunca levanta, só devolve False."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return True
    except Exception:                       # noqa: BLE001 — disco cheio, lock, etc.
        try:
            tmp.unlink()                     # não deixa lixo .tmp
        except OSError:
            pass
        return False


def write_app_state(**changes) -> None:
    """Atualiza o state.json do Jarvis App. Silencioso se o app nem existir."""
    import json

    _app_state.update({k: v for k, v in changes.items() if v is not None})
    try:
        payload = json.dumps(_app_state, ensure_ascii=False)
    except (TypeError, ValueError):
        return
    _atomic_write(APP_STATE_FILE, payload)


def push_note(msg: str, kind: str = "info") -> None:
    """Adiciona uma linha ao feed de notificações do cérebro (últimas 6)."""
    _NOTES.append({"t": time.time(), "msg": str(msg)[:120], "kind": kind})
    del _NOTES[:-6]
    write_app_state(notes=list(_NOTES))


_control_cache = {"data": {"paused": False, "view": "brain"}, "at": 0.0}
_CONTROL_TTL = 0.25   # relê o arquivo no máx. 4x/s (é minúsculo)


def read_control() -> dict:
    """Lê control.json. {'paused': bool}. Cache curto de 0,25s."""
    import json
    import time as _t

    if _t.monotonic() - _control_cache["at"] >= _CONTROL_TTL:
        _control_cache["at"] = _t.monotonic()
        try:
            _control_cache["data"] = json.loads(CONTROL_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return _control_cache["data"]


def write_control(**changes) -> dict:
    import json
    import time as _t

    data = dict(_control_cache["data"])
    for k in ("holo", "scan", "scan_hit"):   # eventos de uso único — não ficam grudados
        data.pop(k, None)
    data.update({k: v for k, v in changes.items() if v is not None})
    try:
        payload = json.dumps(data)
    except (TypeError, ValueError):
        return _control_cache["data"]
    _atomic_write(CONTROL_FILE, payload)
    _control_cache["data"] = data
    _control_cache["at"] = _t.monotonic()
    return data


def rotate_log(max_kb: int = 512) -> None:
    """Mantém só a última metade do log se ele passar de max_kb. Chamar no start."""
    try:
        if LOG_PATH.stat().st_size <= max_kb * 1024:
            return
        lines = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
        LOG_PATH.write_text("\n".join(lines[-len(lines) // 2:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


@lru_cache(maxsize=2048)
def _norm_cached(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    """minúsculas, sem acento, sem pontuação, espaços colapsados.
    Cacheado — está no caminho quente (dispatch chama dezenas de vezes)."""
    return _norm_cached(s or "")


# --- teclado (Win32) --------------------------------------------------------
_u32 = ctypes.windll.user32
KEYEVENTF_KEYUP = 0x02

VK = {
    "CTRL": 0x11, "ALT": 0x12, "SHIFT": 0x10, "WIN": 0x5B, "ENTER": 0x0D,
    "V": 0x56, "A": 0x41, "D": 0x44, "M": 0x4D, "F4": 0x73, "TAB": 0x09, "ESC": 0x1B,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28, "SNAPSHOT": 0x2C,
    "VOL_MUTE": 0xAD, "VOL_DOWN": 0xAE, "VOL_UP": 0xAF,
    "MEDIA_NEXT": 0xB0, "MEDIA_PREV": 0xB1, "MEDIA_STOP": 0xB2, "MEDIA_PLAY": 0xB3,
}


def tap(vk: int, times: int = 1) -> None:
    for _ in range(times):
        _u32.keybd_event(vk, 0, 0, 0)
        _u32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.03)


def combo(*names: str) -> None:
    vks = [VK[n] for n in names]
    for vk in vks:
        _u32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.04)
    for vk in reversed(vks):
        _u32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def set_clipboard(text: str) -> bool:
    """Coloca texto (unicode) na área de transferência via Win32 direto."""
    c = ctypes
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    k32 = c.windll.kernel32
    u32 = c.windll.user32

    k32.GlobalAlloc.restype = c.c_void_p
    k32.GlobalAlloc.argtypes = [c.c_uint, c.c_size_t]
    k32.GlobalLock.restype = c.c_void_p
    k32.GlobalLock.argtypes = [c.c_void_p]
    k32.GlobalUnlock.argtypes = [c.c_void_p]
    u32.OpenClipboard.argtypes = [c.c_void_p]
    u32.SetClipboardData.restype = c.c_void_p
    u32.SetClipboardData.argtypes = [c.c_uint, c.c_void_p]

    data = text.encode("utf-16-le") + b"\x00\x00"
    h = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not h:
        return False
    p = k32.GlobalLock(h)
    c.memmove(p, data, len(data))
    k32.GlobalUnlock(h)

    for _ in range(6):
        if u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        u32.EmptyClipboard()
        if not u32.SetClipboardData(CF_UNICODETEXT, h):
            return False
    finally:
        u32.CloseClipboard()
    return True


def paste_text(text: str) -> None:
    if set_clipboard(text):
        time.sleep(0.25)
        combo("CTRL", "V")


def get_clipboard() -> str:
    """Lê texto (unicode) da área de transferência via Win32."""
    c = ctypes
    CF_UNICODETEXT = 13
    k32, u32 = c.windll.kernel32, c.windll.user32
    k32.GlobalLock.restype = c.c_void_p
    k32.GlobalLock.argtypes = [c.c_void_p]
    k32.GlobalUnlock.argtypes = [c.c_void_p]
    u32.GetClipboardData.restype = c.c_void_p
    u32.GetClipboardData.argtypes = [c.c_uint]
    for _ in range(6):
        if u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return ""
    try:
        h = u32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = k32.GlobalLock(h)
        text = c.c_wchar_p(p).value or ""
        k32.GlobalUnlock(h)
        return text
    finally:
        u32.CloseClipboard()
