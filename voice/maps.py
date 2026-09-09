#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
maps.py — Google Maps por voz (sem chave de API, via URL).

  "como chegar em <lugar>"        -> traça rota (origem = local atual)
  "procura <coisa> [em/perto]"    -> busca no mapa
  "restaurantes 5 estrelas em X"  -> busca "melhores restaurantes em X"
  "abre o google maps"            -> só abre o Maps
"""
from __future__ import annotations

import re
import webbrowser
from urllib.parse import quote_plus

_ROUTE = re.compile(
    r"\b(?:como\s+(?:eu\s+)?cheg\w+|rota\b|caminho\s+(?:ate|pra|para)|"
    r"dire[cç][oõ]es?\b|navega\w*|me\s+leva\w*|"
    r"tra[cç]a\w*\s+(?:uma\s+)?rota|ir\s+(?:ate|pra|para)|viajar\s+(?:pra|para|ate)|"
    r"(?:bora|vamos?|vamo|vou|to\s+indo)\s+(?:pro|pra|pras|pros|para|ao|a|ate))\b"
    r"(?:\s+(?:o|a|à|ao|até|ate|pra|pro|pros|pras|para|em|no|na|nos|nas|de|do|da|dos|das))*\s+(.+)"
)

_PLACE = re.compile(
    r"\b(restaurante|churrascaria|pizzaria|lanchonete|hamburgueria|cafe|cafeteria|padaria|"
    r"sorveteria|hotel|pousada|hostel|farmacia|drogaria|hospital|clinica|"
    r"posto\s+de\s+(?:gasolina|combustivel)|supermercado|mercado|atacado|shopping|"
    r"academia|empresa|escritorio|coworking|loja|banco|aeroporto|rodoviaria|"
    r"parque|museu|cinema|teatro|igreja|barbearia|salao|pet\s*shop|oficina)\w*\b"
)
_NEAR = re.compile(r"\bperto\s+de\s+mim\b|\baqui\s+perto\b|\bpr[oó]xim[oa]s?\b")
_MAPS = re.compile(r"\bmaps?\b|\bmapa\b|\bgoogle\s*maps\b")
_TOP = re.compile(
    r"\b(?:com\s+|de\s+)?(?:5\s*estrelas?|cinco\s*estrelas?|nota\s*(?:5|maxima|dez|10)|"
    r"bem\s+avaliad\w*|melhor(?:es)?|mais\s+bem\s+avaliad\w*|top|com\s+avaliacao\s*(?:5|maxima|alta))\b"
)
_VERB = re.compile(
    r"^(?:procur\w+|ach\w+|encontr\w+|busc\w+|me\s+mostr\w+|mostr\w+|"
    r"onde\s+(?:tem|fica|ficam|posso\s+\w+|eu\s+\w+|acho|encontro)|"
    r"quero\s+(?:achar|encontrar|ver|ir\s+n?[oa]?)|tem\s+algum\w*|"
    r"como\s+(?:acho|encontro|achar|encontrar)|"
    r"abr\w+|abre|lig\w+|da\s+uma\s+olhada\s+em)\s+"
)


def _clean(q: str) -> str:
    q = _VERB.sub("", q).strip()
    q = re.sub(r"^(?:o|a|ao|à|até|ate|pra|pro|pros|pras|para|em|no|na|nos|nas|de|do|da|dos|das)\s+", "", q)
    q = re.sub(r"\b(?:no|na|pelo|pela|l[aá]\s+no)\s+(?:google\s*)?(?:maps?|mapa)\b", "", q)
    q = re.sub(r"\bno\s+google\b", "", q)
    q = re.sub(r"\b(?:por\s+favor|pra\s+mim|agora|a[ií])\b", "", q)
    return q.strip(" ,.?!").strip()


_OPEN = re.compile(r"\b(?:abr\w+|abre|lig\w+|mostra\w+|carreg\w+|inicia\w+)\s+"
                   r"(?:o\s+|a\s+)?(?:google\s*)?maps?\b")


def handle(t: str) -> str | None:
    """t = texto normalizado (sem acento, minúsculo). Retorna a fala, ou None."""
    if _OPEN.search(t) and not _ROUTE.search(t):
        webbrowser.open("https://www.google.com/maps")
        return "Abrindo o Google Maps, senhor."

    m = _ROUTE.search(t)
    if m:
        dest = _clean(m.group(1))
        if dest:
            webbrowser.open("https://www.google.com/maps/dir/?api=1&destination=" + quote_plus(dest))
            return f"Traçando a rota até {dest}, senhor."

    is_maps = bool(_MAPS.search(t) or _PLACE.search(t) or _NEAR.search(t))
    if not is_maps:
        return None

    q = _clean(t)
    if _TOP.search(t):
        q = ("melhores " + _TOP.sub("", q)).strip()
        q = re.sub(r"\s{2,}", " ", q)

    if not q or q in ("maps", "mapa", "google maps"):
        webbrowser.open("https://www.google.com/maps")
        return "Abrindo o Google Maps, senhor."

    webbrowser.open("https://www.google.com/maps/search/?api=1&query=" + quote_plus(q))
    return f"Procurando {q} no mapa, senhor."
