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

_ALT2 = re.compile(
    r"\b(quero|queria|preciso\s+de|me\s+d[aá])\s+(?:um|uma)\s+"
    r"(?:holograma|modelo|esquema|diagrama|desenho|ilustracao|sistema|representacao)\s+"
    r"(?:de\s+|da\s+|do\s+|sobre\s+)?(.+)")

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
Coordenadas de -3 a 3. NO MÁXIMO 12 peças — seja enxuto. Rótulos curtos.
Responda SÓ o JSON, em UMA linha. Nada antes, nada depois. Não repita peças.

Exemplo — "átomo de carbono":
{"title":"Átomo de carbono","spin":true,"parts":[{"t":"ball","at":[0,0,0],"r":0.4,"c":"cinza","label":"núcleo"},{"t":"label","at":[0,-0.9,0],"text":"6p + 6n","c":"soft"},{"t":"ring","at":[0,0,0],"r":1.2,"c":"dim"},{"t":"ring","at":[0,0,0],"r":2.1,"c":"dim"},{"t":"ball","at":[1.2,0,0],"r":0.08,"c":"azul","label":"e⁻"},{"t":"ball","at":[-1.2,0,0],"r":0.08,"c":"azul"},{"t":"ball","at":[2.1,0,0],"r":0.08,"c":"azul"},{"t":"ball","at":[0,2.1,0],"r":0.08,"c":"azul"},{"t":"ball","at":[-2.1,0,0],"r":0.08,"c":"azul"},{"t":"ball","at":[0,-2.1,0],"r":0.08,"c":"azul"}]}

Exemplo — "alavanca":
{"title":"Alavanca","spin":false,"parts":[{"t":"line","pts":[[-2.5,0,0],[2.5,0.2,0]],"c":"neon"},{"t":"line","pts":[[-0.2,-0.9,0],[0,0,0],[0.2,-0.9,0]],"c":"soft"},{"t":"label","at":[0,-1.2,0],"text":"apoio","c":"soft"},{"t":"arrow","from":[-2.3,0.6,0],"to":[-2.3,-0.1,0],"c":"amber","label":"F"},{"t":"arrow","from":[2.2,1.4,0],"to":[2.2,0.3,0],"c":"red","label":"carga"},{"t":"label","at":[0,1.8,0],"text":"F x b = P x a","c":"soft"}]}
"""


def match(t: str) -> str | None:
    """t normalizado. Devolve o TEMA pedido, ou None."""
    m = _TRIGGER.search(t) or _ALT.search(t) or _ALT2.search(t)
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
            1100, temperature=0.3)
    except Exception as exc:                      # noqa: BLE001
        log(f"invent: LLM falhou ({exc})")
        return None
    start = out.find("{")
    if start < 0:
        log(f"invent: sem JSON ({out[:120]!r})")
        return None
    txt = out[start:]

    # tenta parsear inteiro; se cortou no meio, SALVA as peças completas
    spec = None
    try:
        spec = json.loads(txt)
    except ValueError:
        spec = _salvage(txt, tema)
    if not spec:
        log(f"invent: não recuperei nada de ({txt[:150]!r})")
        return None

    parts = spec.get("parts") or spec.get("elementos") or []
    parts = [p for p in parts if isinstance(p, dict)][:24]
    if not parts:
        return None
    spec["parts"] = parts
    spec["title"] = str(spec.get("title") or spec.get("titulo") or tema)[:60]
    spec["spin"] = bool(spec.get("spin") or spec.get("girar"))
    return spec


def _salvage(txt: str, tema: str) -> dict | None:
    """JSON cortado no meio: extrai todo objeto {...} completo de dentro de parts."""
    tm = re.search(r'"tit(?:le|ulo)"\s*:\s*"([^"]*)"', txt)
    sp = re.search(r'"(?:spin|girar)"\s*:\s*(true|false)', txt)
    pi = txt.find('"parts"')
    if pi < 0:
        pi = txt.find('"elementos"')
    if pi < 0:
        return None
    br = txt.find("[", pi)
    if br < 0:
        return None
    depth, cur, objs = 0, "", []
    for ch in txt[br + 1:]:
        if ch == "{":
            depth += 1
        if depth > 0:
            cur += ch
        if ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    objs.append(json.loads(cur))
                except ValueError:
                    pass
                cur = ""
        elif ch == "]" and depth == 0:
            break
    if not objs:
        return None
    return {"title": tm.group(1) if tm else tema,
            "spin": bool(sp and sp.group(1) == "true"),
            "parts": objs}
