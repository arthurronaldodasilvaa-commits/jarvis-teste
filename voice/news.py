#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
news.py — manchetes por voz, via RSS do Google Notícias (sem chave).

  "quais as notícias?"          -> 4 manchetes de destaque
  "notícias de tecnologia"      -> manchetes do tópico
  "notícias sobre o São Paulo"  -> busca
"""
from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET

from common import log, norm

_BASE = "https://news.google.com/rss"
_LOCALE = "hl=pt-BR&gl=BR&ceid=BR:pt-419"
_TOPICS = {
    "tecnologia": "tecnologia", "tech": "tecnologia",
    "negocios": "economia", "economia": "economia", "mercado": "mercado financeiro",
    "ciencia": "ciência", "ciencias": "ciência",
    "saude": "saúde", "esporte": "esporte", "esportes": "esporte",
    "mundo": "mundo notícias", "brasil": "Brasil notícias", "politica": "política",
    "entretenimento": "entretenimento", "futebol": "futebol",
}
_CACHE: dict = {}


def _fetch(url: str) -> list[str]:
    hit = _CACHE.get(url)
    if hit and hit[1] > time.time():
        return hit[0]
    import httpx
    r = httpx.get(url, timeout=8, follow_redirects=True,
                  headers={"User-Agent": "Mozilla/5.0 JarvisVoice/1.0"})
    r.raise_for_status()
    root = ET.fromstring(r.text)
    titles = []
    for item in root.iter("item"):
        el = item.find("title")
        if el is not None and el.text:
            t = html.unescape(el.text)
            t = re.sub(r"\s+-\s+[^-]+$", "", t).strip()   # tira " - Fonte"
            if t:
                titles.append(t)
    _CACHE[url] = (titles, time.time() + 600)
    return titles


def headlines(query: str = "", n: int = 4) -> str:
    q = norm(query)
    topic = next((term for word, term in _TOPICS.items() if re.search(rf"\b{word}\b", q)), None)
    try:
        from urllib.parse import quote_plus
        if topic:
            url = f"{_BASE}/search?q={quote_plus(topic)}&{_LOCALE}"
        elif q:
            url = f"{_BASE}/search?q={quote_plus(query)}&{_LOCALE}"
        else:
            url = f"{_BASE}?{_LOCALE}"
        titles = _fetch(url)
    except Exception as exc:  # noqa: BLE001
        log(f"news: falhou ({exc})")
        return "Não consegui as notícias agora, senhor."

    if not titles:
        return "Não achei notícias sobre isso, senhor."
    top = titles[:n]
    corpo = "; ".join(top)
    return f"Destaques, senhor: {corpo}."
