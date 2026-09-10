#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
aula.py — "Jarvis, me dá uma aula sobre X".

O LLM monta um roteiro curto (3-5 passos). O Jarvis vai FALANDO cada passo e,
quando faz sentido, cria o holograma daquele ponto. Entre os passos ele espera
o Senhor dizer "continua" / "próximo".
"""
from __future__ import annotations

import json
import re
import time

from common import log, norm, write_control

# hologramas que a aula pode invocar (o LLM escolhe da lista)
_HOLOS = [
    "circulo_trigonometrico", "plano_inclinado", "lancamento_obliquo", "onda", "pendulo",
    "circuito", "circuito_paralelo", "campo_eletrico", "lente", "colisao",
    "vetores", "derivada", "integral", "superficie_3d",
    "molecula_agua", "molecula_metano", "geometria_molecular", "tabela_periodica", "pilha",
    "dna", "celula", "coracao", "neuronio", "sistema_solar",
    "grafico_barras", "arvore_probabilidade",
]

_SYS = (
    "Você é um professor. Monte uma MINI-AULA sobre o tema, em 3 a 5 passos.\n"
    "Responda SÓ com JSON: {\"tema\":\"...\",\"passos\":[{\"fala\":\"...\",\"holo\":\"...\"}]}\n"
    "Cada 'fala': 2 a 3 frases, português do Brasil, didático, direto, tratando por 'senhor'.\n"
    "'holo': o nome de UM holograma da lista abaixo se ajudar a ilustrar o passo, senão \"\".\n"
    "Lista de hologramas: " + ", ".join(_HOLOS) + "\n"
    "Não repita holograma. O passo 1 apresenta o tema; o último resume."
)


def match(t: str) -> str | None:
    m = re.search(r"\b(me\s+d[aá]|d[aá]|quero|faz|monta|prepara)\s+(uma\s+)?(mini\s*)?"
                  r"aula\s+(sobre|de|do|da|a respeito de)\s+(.+)", t)
    if not m:
        m = re.search(r"\bme\s+ensina\s+(sobre\s+)?(.+?)\s+(do zero|passo a passo|direito|com holograma)", t)
        if m:
            return m.group(2).strip()
        return None
    return m.group(m.lastindex).strip(" ?.")


def start(tema: str, cfg, brain, speak) -> "object":
    import skills
    R = skills.Result
    try:
        out = brain._post(
            [{"role": "system", "content": _SYS},
             {"role": "user", "content": tema}], 700, temperature=0.4)
    except Exception as exc:  # noqa: BLE001
        log(f"aula: LLM falhou ({exc})")
        return R(speak="Não consegui montar a aula agora, senhor.")
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return R(speak="Não consegui montar a aula, senhor.")
    try:
        plano = json.loads(m.group(0))
    except ValueError:
        # salva o que der: extrai as "fala"
        falas = re.findall(r'"fala"\s*:\s*"([^"]{10,})"', m.group(0))
        if not falas:
            return R(speak="Não consegui montar a aula, senhor.")
        plano = {"passos": [{"fala": f, "holo": ""} for f in falas]}
    passos = [p for p in plano.get("passos", []) if p.get("fala")][:5]
    if not passos:
        return R(speak="Não consegui montar a aula, senhor.")

    state = {"i": 0}

    def _passo(_resp: str = ""):
        i = state["i"]
        if i >= len(passos):
            return "Fim da aula, senhor. Espero ter ajudado."
        p = passos[i]
        state["i"] += 1
        holo = norm(p.get("holo", "")).replace(" ", "_")
        if holo and any(holo == norm(h) or holo in norm(h) for h in _HOLOS):
            real = next((h for h in _HOLOS if norm(h) == holo or holo in norm(h)), holo)
            write_control(holo={"action": "add", "shape": real, "n": int(time.time() * 1000)})
        fala = re.sub(r"\s+", " ", p["fala"]).strip()
        if state["i"] < len(passos):
            fala += "  ...  Diga \"continua\" quando estiver pronto, senhor."
        # continua a aula: devolve (fala, próximo_passo)
        return (fala, _passo) if state["i"] < len(passos) else fala

    primeiro = _passo()
    if isinstance(primeiro, tuple):
        return R(speak="Vamos lá, senhor. " + primeiro[0], await_reply=primeiro[1])
    return R(speak=primeiro)
