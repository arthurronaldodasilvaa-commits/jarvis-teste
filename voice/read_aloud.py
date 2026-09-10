#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
read_aloud.py — o Jarvis narra um texto longo (área de transferência, arquivo,
página web) com a voz do Piper, e para na hora que o Senhor pedir.

  "Jarvis, lê isso"           -> lê a área de transferência
  "Jarvis, lê esse arquivo E:/estudos/resumo.txt"
  "Jarvis, lê essa página"    -> se o clipboard tiver uma URL, baixa e lê
  "Jarvis, para de ler"       -> interrompe
"""
from __future__ import annotations

import re
import threading

from common import log

_stop = threading.Event()
_thread: threading.Thread | None = None


def reading() -> bool:
    return _thread is not None and _thread.is_alive()


def stop() -> None:
    _stop.set()


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?:;])\s+(?=[A-ZÀ-Ú0-9\"'“(])", text)
    out, buf = [], ""
    for p in parts:
        buf = (buf + " " + p).strip() if buf else p
        if len(buf) >= 160 or p.endswith((".", "!", "?")):
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return [s for s in out if s.strip()]


def start(mouth, text: str, fonte: str = "") -> str:
    global _thread
    if reading():
        stop()
        if _thread:
            _thread.join(timeout=2)
    text = (text or "").strip()
    if len(text) < 20:
        return "Não tem texto pra ler, senhor."
    sents = _sentences(text)[:400]
    _stop.clear()

    def run():
        try:
            mouth.say(f"Lendo{(' ' + fonte) if fonte else ''}, senhor.")
            for s in sents:
                if _stop.is_set():
                    break
                mouth.say(s)
            if not _stop.is_set():
                mouth.say("Terminei a leitura, senhor.")
        except Exception as exc:  # noqa: BLE001
            log(f"read_aloud: {exc}")

    _thread = threading.Thread(target=run, daemon=True)
    _thread.start()
    n = len(sents)
    return f"Começando, senhor. São {n} trecho{'s' if n != 1 else ''}. Diga \"para de ler\" quando quiser."


# --------------------------------------------------------------------------
def _from_url(url: str) -> str:
    try:
        import httpx
        r = httpx.get(url, timeout=12, follow_redirects=True,
                      headers={"User-Agent": "JarvisVoice/1.0 (assistente local)"})
        r.raise_for_status()
        html = r.text
    except Exception as exc:  # noqa: BLE001
        log(f"read_aloud/url: {exc}")
        return ""
    html = re.sub(r"<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", " ", html,
                  flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = re.sub(r"&[a-z]+;", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def source_text(t_norm: str) -> tuple[str, str] | None:
    """Descobre O QUE ler a partir do comando. Devolve (texto, rótulo) ou None."""
    from common import get_clipboard

    m = re.search(r"\bl[eê]\w*\s+(?:o\s+|esse\s+|este\s+)?arquivo\s+(.+)", t_norm)
    if m:
        from pathlib import Path
        p = Path(m.group(1).strip().strip('"'))
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="ignore"), f"o arquivo {p.name}"
            except OSError:
                return None
        return None

    clip = (get_clipboard() or "").strip()
    if re.search(r"\bp[aá]gina\b|\bsite\b|\blink\b|\bartigo\b", t_norm):
        mu = re.search(r"https?://\S+", clip)
        if mu:
            return _from_url(mu.group(0)), "a página"
        return None

    # "lê isso" / "lê o texto" -> área de transferência
    if clip and re.match(r"https?://\S+$", clip):
        return _from_url(clip), "a página"
    return (clip, "a área de transferência") if len(clip) >= 20 else None
