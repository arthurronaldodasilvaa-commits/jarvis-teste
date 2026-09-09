#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
wiki.py — fatos rápidos da Wikipédia em português (sem chave).

  "quem foi Santos Dumont"
  "o que é fotossíntese"
  "me fala sobre a Floresta Amazônica"
"""
from __future__ import annotations

import re
from urllib.parse import quote

from common import log

_UA = "JarvisVoice/1.0 (https://github.com/open-jarvis/OpenJarvis; assistente de voz local)"

_TRIGGER = re.compile(
    r"^(?:quem (?:foi|e|era|sao|s[aã]o)|o que (?:e|era|foi|s[aã]o|significa)|"
    r"o que (?:e|era) (?:um|uma|o|a)|me (?:fala|conta|explica) (?:sobre|o que e|quem foi|de)|"
    r"defini[cç][aã]o de|significado de|fala sobre|conta sobre)\s+(.+)")


def _search_title(term: str) -> str | None:
    import httpx
    try:
        r = httpx.get("https://pt.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "srsearch": term,
            "srlimit": 1, "format": "json"}, timeout=8,
            headers={"User-Agent": _UA})
        hits = r.json().get("query", {}).get("search", [])
        return hits[0]["title"] if hits else None
    except Exception as exc:  # noqa: BLE001
        log(f"wiki search: {exc}")
        return None


def _summary(title: str) -> str | None:
    import httpx
    try:
        r = httpx.get(
            "https://pt.wikipedia.org/api/rest_v1/page/summary/" + quote(title.replace(" ", "_")),
            timeout=8, headers={"User-Agent": _UA})
        if r.status_code != 200:
            return None
        j = r.json()
        if j.get("type") == "disambiguation":
            return None
        return (j.get("extract") or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        log(f"wiki summary: {exc}")
        return None


def lookup(raw: str) -> str | None:
    """raw = texto original (com acento). None = não é pergunta factual / não achou."""
    import unicodedata
    low = raw.strip().lower()
    flat = unicodedata.normalize("NFKD", low).encode("ascii", "ignore").decode()
    m = _TRIGGER.match(flat)
    if not m:
        return None
    # pega o mesmo trecho no texto ORIGINAL (com acento), pelo comprimento
    term = raw.strip()[m.start(1):m.end(1)]
    term = re.sub(r"[?.!]+$", "", term).strip()
    term = re.sub(r"(?i)^(a|o|um|uma|os|as)\s+", "", term)
    if len(term) < 2:
        return None

    title = _search_title(term) or term
    ext = _summary(title)
    if not ext:
        return None

    # 2 frases, no máximo ~320 caracteres
    frases = re.split(r"(?<=[.!?])\s+", ext)
    out = " ".join(frases[:2]).strip()
    if len(out) > 320:
        out = out[:317].rsplit(" ", 1)[0] + "…"
    return f"{out} (Wikipédia)"
