#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
invent.py — o Jarvis "inventa" um holograma novo.

  "Jarvis, cria um holograma de um átomo de carbono"
  "Jarvis, inventa um modelo do ciclo da água"
  "Jarvis, desenha um esquema de uma alavanca"

O LLM não escreve código — ele descreve o desenho como uma lista de PEÇAS
(bola, bastão, seta, linha, curva, anel, caixa, rótulo…) num JSON. O
ui/models.js monta isso com segurança. Peça ruim = nada aparece + aviso.
"""
from __future__ import annotations

import json
import re

from common import log

_TRIGGER = re.compile(
    r"\b(cri[ae]|criar|invent[ae]|inventar|monta|montar|desenh[ae]|desenhar|faz|fazer|"
    r"gera|gerar|imagina|imaginar|bola|projeta|projetar|ilustra|ilustrar|constr[oó]i)\s+"
    r"(?:(?:um|uma|o|a|uns|umas)\s+)?"
    r"(?:(?:holograma|modelo|esquema|diagrama|desenho|representacao|ilustracao|"
    r"visualizacao|figura)\s+(?:de|da|do|dos|das|sobre|pra|para|d[eo]\s+um[a]?)?\s+)?"
    r"(.+)")

_ALT = re.compile(
    r"\b(?:me\s+)?(?:mostra|ve|ver|quero\s+ver|poe|bota)\s+(?:um|uma)?\s*"
    r"(?:holograma|modelo|esquema|diagrama|representacao)\s+"
    r"(?:de|da|do|sobre)\s+(.+)")

_SYS = """Você descreve um DESENHO 3D esquemático (holograma de estudo) como JSON de UMA linha.
Formato: {"title":"<nome curto>","spin":true/false,"parts":[ ... ]}

Cada peça de "parts" é um objeto com "t" (tipo) e campos:
  {"t":"ball","at":[x,y,z],"r":0.3,"c":"cinza","label":"C"}      esfera/átomo/ponto
  {"t":"stick","from":[..],"to":[..],"c":"soft"}                 bastão/ligação
  {"t":"arrow","from":[..],"to":[..],"c":"amber","label":"F"}    seta/vetor/força
  {"t":"line","pts":[[..],[..],[..]],"c":"neon"}                 linha/contorno
  {"t":"curve","expr":"sin(x)","c":"neon"}                       curva de função (x de -3 a 3)
  {"t":"ring","at":[..],"r":1.2,"c":"cyan"}                      anel/órbita/círculo
  {"t":"box","at":[..],"size":[1,1,1],"c":"neon"}               caixa/bloco
  {"t":"axes","size":3}                                         eixos x/y
  {"t":"label","at":[x,y,z],"text":"6 prótons","c":"soft"}      texto

Cores: neon, soft, amber, green, red, azul, rosa, cinza, branco, dim.
Coordenadas de -3 a 3. Máximo 20 peças. Seja esquemático e claro, com rótulos.
Responda SÓ o JSON. Nada antes, nada depois.

Exemplo — "átomo de carbono":
{"title":"Átomo de carbono","spin":true,"parts":[{"t":"ball","at":[0,0,0],"r":0.4,"c":"cinza","label":"núcleo"},{"t":"label","at":[0,-0.9,0],"text":"6p + 6n","c":"soft"},{"t":"ring","at":[0,0,0],"r":1.2,"c":"dim"},{"t":"ring","at":[0,0,0],"r":2.1,"c":"dim"},{"t":"ball","at":[1.2,0,0],"r":0.08,"c":"azul","label":"e⁻"},{"t":"ball","at":[-1.2,0,0],"r":0.08,"c":"azul"},{"t":"ball","at":[2.1,0,0],"r":0.08,"c":"azul"},{"t":"ball","at":[0,2.1,0],"r":0.08,"c":"azul"},{"t":"ball","at":[-2.1,0,0],"r":0.08,"c":"azul"},{"t":"ball","at":[0,-2.1,0],"r":0.08,"c":"azul"}]}

Exemplo — "alavanca":
{"title":"Alavanca","spin":false,"parts":[{"t":"line","pts":[[-2.5,0,0],[2.5,0.2,0]],"c":"neon"},{"t":"line","pts":[[-0.2,-0.9,0],[0,0,0],[0.2,-0.9,0]],"c":"soft"},{"t":"label","at":[0,-1.2,0],"text":"apoio","c":"soft"},{"t":"arrow","from":[-2.3,0.6,0],"to":[-2.3,-0.1,0],"c":"amber","label":"F"},{"t":"arrow","from":[2.2,1.4,0],"to":[2.2,0.3,0],"c":"red","label":"carga"},{"t":"label","at":[0,1.8,0],"text":"F x b = P x a","c":"soft"}]}
"""


def match(t: str) -> str | None:
    """t normalizado. Devolve o TEMA pedido, ou None."""
    m = _TRIGGER.search(t) or _ALT.search(t)
    if not m:
        return None
    tema = m.group(m.lastindex).strip()
    # tira cauda tipo "na tela", "na camera", "pra mim"
    tema = re.sub(r"\s+(na tela|na camera|pra mim|por favor|agora)\s*$", "", tema).strip()
    return tema or None


def make_spec(tema: str, brain) -> dict | None:
    try:
        out = brain._post(
            [{"role": "system", "content": _SYS},
             {"role": "user", "content": tema}],
            600, temperature=0.3)
    except Exception as exc:                      # noqa: BLE001
        log(f"invent: LLM falhou ({exc})")
        return None
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        log(f"invent: sem JSON ({out[:120]!r})")
        return None
    txt = m.group(0)
    for _ in range(3):                            # conserta cauda cortada: fecha colchetes
        try:
            spec = json.loads(txt)
            break
        except ValueError:
            if txt.count("{") > txt.count("}"):
                txt += "}"
            elif txt.count("[") > txt.count("]"):
                txt += "]"
            else:
                log(f"invent: JSON inválido ({txt[:150]!r})")
                return None
    else:
        return None
    parts = spec.get("parts") or spec.get("elementos") or []
    if not isinstance(parts, list) or not parts:
        return None
    spec["parts"] = parts[:24]
    spec.setdefault("title", tema)
    return spec
