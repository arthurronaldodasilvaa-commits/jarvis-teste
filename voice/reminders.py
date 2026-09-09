#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
reminders.py — lembretes e timers persistentes.

  "me lembra de tirar o bolo em 20 minutos"
  "me lembra às 15h de ligar pro João"
  "timer de 10 minutos"
  "me acorda daqui a uma hora e meia"

O daemon (jarvis_voice.py) roda um thread que checa `due()` a cada ~15 s
e fala os lembretes que venceram.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta

from common import HERE, log, norm

FILE = HERE / "reminders.json"

_NUM = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
    "quinze": 15, "vinte": 20, "trinta": 30, "quarenta": 45, "quarenta e cinco": 45,
    "sessenta": 60, "meia": 30, "meio": 30,
}


def _load() -> list[dict]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(items: list[dict]) -> None:
    try:
        FILE.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log(f"reminders: não salvou ({exc})")


def _num(word: str) -> int | None:
    word = word.strip()
    if word.isdigit():
        return int(word)
    return _NUM.get(word)


def parse_when(t: str, now: datetime | None = None) -> tuple[float, str] | None:
    """t = texto normalizado. Devolve (timestamp, texto_humano) ou None."""
    now = now or datetime.now()
    t = " " + t + " "

    # --- relativo: "em/daqui a X minutos" OU só "X minutos" (timer) ---
    m = re.search(r"\b(?:em|daqui a|dentro de|apos|depois de)\s+"
                  r"([\w ]+?)\s*(segundos?|minutos?|min|horas?|h)\b(?:\s+e meia)?", t)
    if not m:
        m = re.search(r"\b(\d+)\s*(segundos?|minutos?|min|horas?)\b", t)
    if m:
        qty = _num(m.group(1).strip()) or _extract_leading_int(m.group(1)) or 0
        unit = m.group(2)
        half = re.search(r"\bhora e meia\b", t) is not None or (
            "e meia" in t and unit.startswith("h"))
        if qty:
            if unit.startswith("seg"):
                delta, human = timedelta(seconds=qty), f"{qty} segundos"
            elif unit.startswith("h"):
                delta = timedelta(hours=qty, minutes=30 if half else 0)
                human = f"{qty}h" + (" e meia" if half else "")
            else:
                delta = timedelta(minutes=qty, seconds=30 if half else 0)
                human = f"{qty} minutos"
            return (now + delta).timestamp(), human

    # --- "meia hora", "um quarto de hora", "uma hora e meia" sem 'em' ---
    if re.search(r"\bmeia hora\b", t):
        return (now + timedelta(minutes=30)).timestamp(), "meia hora"
    if re.search(r"\b(um quarto de hora|quinze minutos)\b", t):
        return (now + timedelta(minutes=15)).timestamp(), "15 minutos"
    if re.search(r"\b(uma hora e meia|hora e meia)\b", t):
        return (now + timedelta(minutes=90)).timestamp(), "1h e meia"

    # --- horário do dia: "às 15h", "as 15:30", "às 9 e meia", "ao meio-dia" ---
    if re.search(r"\bmeio[- ]?dia\b", t):
        return _at(now, 12, 0), "meio-dia"
    if re.search(r"\bmeia[- ]?noite\b", t):
        return _at(now, 0, 0), "meia-noite"

    m = re.search(r"\b(?:as|a|ao)\s+(\d{1,2})"
                  r"(?:\s*(?:e|:|h)\s*(\d{1,2})|\s+(\d{2})(?!\s*(?:min|seg|hora))|\s*e meia)?", t)
    if m:
        hh = int(m.group(1))
        mm = 0
        if m.group(2):
            mm = int(m.group(2))
        elif m.group(3):
            mm = int(m.group(3))
        elif "e meia" in t:
            mm = 30
        if re.search(r"\b(da tarde|da noite)\b", t) and hh < 12:
            hh += 12
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            amanha = bool(re.search(r"\bamanha\b", t))
            ts = _at(now, hh, mm, tomorrow=amanha)
            label = f"{hh:02d}:{mm:02d}" + (" de amanhã" if amanha else "")
            return ts, label

    return None


def _extract_leading_int(s: str) -> int | None:
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else None


def _at(now: datetime, hh: int, mm: int, tomorrow: bool = False) -> float:
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if tomorrow or target <= now:
        target += timedelta(days=1)
    return target.timestamp()


def add(text: str, when_ts: float) -> None:
    items = _load()
    items.append({"text": text.strip(), "at": when_ts, "made": time.time()})
    _save(items)
    log(f"lembrete: {text!r} para {datetime.fromtimestamp(when_ts):%d/%m %H:%M}")


def due(now_ts: float | None = None) -> list[dict]:
    """Devolve (e remove) os lembretes já vencidos."""
    now_ts = now_ts or time.time()
    items = _load()
    ready = [x for x in items if x["at"] <= now_ts]
    if ready:
        _save([x for x in items if x["at"] > now_ts])
    return ready


def pending() -> list[dict]:
    return sorted(_load(), key=lambda x: x["at"])


def clear_all() -> int:
    n = len(_load())
    _save([])
    return n
