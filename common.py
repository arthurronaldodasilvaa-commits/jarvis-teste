#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Utilitários compartilhados entre jarvis_voice.py e skills.py."""

from __future__ import annotations

import ctypes
import re
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_PATH = HERE / "jarvis_voice.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def norm(s: str) -> str:
    """minúsculas, sem acento, sem pontuação, espaços colapsados."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


# --- teclado (Win32) --------------------------------------------------------
_u32 = ctypes.windll.user32
KEYEVENTF_KEYUP = 0x02

VK = {
    "CTRL": 0x11, "ALT": 0x12, "SHIFT": 0x10, "WIN": 0x5B, "ENTER": 0x0D,
    "V": 0x56, "A": 0x41, "F4": 0x73, "TAB": 0x09, "ESC": 0x1B,
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
