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

from common import HERE, log

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


_DOW = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4,
        "sabado": 5, "domingo": 6}


def parse_recurring(t: str, now: datetime | None = None):
    """'todo dia às 8', 'toda segunda às 9', 'de hora em hora'.
    Devolve (primeiro_ts, human, rule) ou None. rule = {'every':..., 'hh':, 'mm':}."""
    now = now or datetime.now()
    t = " " + t + " "
    if re.search(r"\bde hora em hora\b|\btoda hora\b|\ba cada hora\b", t):
        nxt = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        return nxt.timestamp(), "de hora em hora", {"every": "hourly"}

    m = re.search(r"\b(todo dia|todos os dias|diariamente|toda (?:manha|noite|tarde)|"
                  r"toda\s+(segunda|terca|quarta|quinta|sexta|sabado|domingo)|"
                  r"toda semana|semanalmente)\b", t)
    if not m:
        return None
    hh, mm = 8, 0
    hm = re.search(r"\bas\s+(\d{1,2})(?:\s*(?:e|:|h)\s*(\d{1,2})|\s*e meia)?", t)
    if hm:
        hh = int(hm.group(1))
        mm = 30 if "e meia" in t else int(hm.group(2) or 0)
    elif "toda noite" in t:
        hh = 20
    elif "toda tarde" in t:
        hh = 14

    dow = _DOW.get(m.group(2)) if m.group(2) else None
    if dow is not None:
        rule = {"every": "weekly", "dow": dow, "hh": hh, "mm": mm}
        human = f"toda {m.group(2)}-feira às {hh}h" if dow < 5 else f"todo {m.group(2)} às {hh}h"
    elif "semana" in m.group(1):
        rule = {"every": "weekly", "dow": now.weekday(), "hh": hh, "mm": mm}
        human = f"toda semana às {hh}h"
    else:
        rule = {"every": "daily", "hh": hh, "mm": mm}
        human = f"todo dia às {hh}h" + (f"{mm:02d}" if mm else "")
    return _next_occurrence(rule, now), human, rule


def _next_occurrence(rule: dict, now: datetime) -> float:
    if rule["every"] == "hourly":
        return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0).timestamp()
    target = now.replace(hour=rule["hh"], minute=rule["mm"], second=0, microsecond=0)
    if rule["every"] == "daily":
        if target <= now:
            target += timedelta(days=1)
    else:  # weekly
        days = (rule["dow"] - now.weekday()) % 7
        target += timedelta(days=days)
        if target <= now:
            target += timedelta(days=7)
    return target.timestamp()


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


def add(text: str, when_ts: float, rule: dict | None = None) -> bool:
    items = _load()
    now = time.time()
    txt = text.strip()
    # dedup: mesmo texto criado nos últimos 90 s = provável eco/loop de voz.
    for it in items:
        if it.get("text") == txt and not it.get("rule") and now - it.get("made", 0) < 90:
            log(f"lembrete ignorado (duplicado em {now - it.get('made', 0):.0f}s): {txt!r}")
            return False
    it = {"text": txt, "at": when_ts, "made": now}
    if rule:
        it["rule"] = rule
    items.append(it)
    _save(items)
    log(f"lembrete{'  (recorrente)' if rule else ''}: {txt!r} para "
        f"{datetime.fromtimestamp(when_ts):%d/%m %H:%M}")
    return True


def due(now_ts: float | None = None) -> list[dict]:
    """Devolve os lembretes vencidos. Remove os pontuais; reagenda os recorrentes."""
    now_ts = now_ts or time.time()
    items = _load()
    ready = [x for x in items if x["at"] <= now_ts]
    if not ready:
        return []
    keep = [x for x in items if x["at"] > now_ts]
    for r in ready:
        if r.get("rule"):
            nxt = dict(r)
            nxt["at"] = _next_occurrence(r["rule"], datetime.now() + timedelta(seconds=1))
            keep.append(nxt)
    _save(keep)
    return ready


def pending() -> list[dict]:
    return sorted(_load(), key=lambda x: x["at"])


def clear_all() -> int:
    n = len(_load())
    _save([])
    return n
