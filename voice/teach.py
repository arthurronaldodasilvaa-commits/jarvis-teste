#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
teach.py — o Jarvis aprende comandos novos conversando.

  "Jarvis, aprende: quando eu disser 'modo café' você fala 'preparando, senhor'
   e abre o Spotify"
      -> o LLM transforma isso num comando declarativo, o Jarvis confirma
         em voz, e ao 'sim' grava em voice/skills_learned.toml. Já funciona.

  "Jarvis, esquece o comando modo café"     -> apaga
  "Jarvis, quais comandos você aprendeu?"   -> lista

Nada de código executado: só patterns + falar/abrir/redespachar/shell.
Comando com 'run' (shell) sempre pede confirmação ao usar.
"""
from __future__ import annotations

import json
import re

from common import log, norm

_SYS = """Você converte uma instrução falada num COMANDO PERSONALIZADO do assistente Jarvis.
Responda SÓ com um JSON de uma linha. Nada antes, nada depois.

Campos:
  name      curto, minúsculo (2-4 palavras)
  patterns  lista de 2 a 4 frases/regex SIMPLES do que a PESSOA vai falar pra acionar
            (use as palavras dela; sem "jarvis" no começo)
  speak     o que o Jarvis responde falando (curto, trate por "senhor"); "" se não fala nada
  open      1 arquivo, pasta, link http(s):// OU nome de app pra abrir; "" se nenhum
  then      1 comando pro Jarvis executar como se a pessoa tivesse falado; "" se nenhum
  run       1 comando de shell do Windows; "" se nenhum (evite; só se pedirem explicitamente)

Regras:
- Não invente ação que a pessoa não pediu.
- Se ela disser "abre/abrir/mostra <algo>" (app, site, arquivo), ponha o <algo> em "open".
- Se ela disser "faz <comando do jarvis>" ou "ativa <modo>", ponha em "then".
- Se ela só quer uma resposta falada, preencha só name/patterns/speak.
- Português do Brasil. Escreva o "speak" natural, como o Jarvis falaria.

Exemplos:
entrada: quando eu disser modo café você fala preparando senhor e abre o spotify
saída: {"name":"modo cafe","patterns":["modo cafe","cafe mental"],"speak":"Preparando, senhor.","open":"spotify","then":"","run":""}
entrada: se eu perguntar cadê meu chinelo responde que tá embaixo da cama
saída: {"name":"chinelo","patterns":["cade meu chinelo","onde ta o chinelo","cade o chinelo"],"speak":"Embaixo da cama, senhor.","open":"","then":"","run":""}
entrada: se eu falar hora do lanche abre a calculadora e diz aproveite senhor
saída: {"name":"lanche","patterns":["hora do lanche"],"speak":"Aproveite, senhor.","open":"calculadora","then":"","run":""}
entrada: quando eu falar bora revisar abre meu resumo em e dois barra estudos barra resumo ponto pdf
saída: {"name":"revisar","patterns":["bora revisar","hora de revisar"],"speak":"Abrindo seu resumo, senhor.","open":"E:/Estudos/resumo.pdf","then":"","run":""}
entrada: cria um comando modo prova que ativa o modo prova e fala boa sorte
saída: {"name":"atalho modo prova","patterns":["modo prova ja","direto pra prova"],"speak":"Boa sorte, senhor.","open":"","then":"modo prova","run":""}
"""

_ENTER = re.compile(
    r"\b(aprend[ae]|aprenda|memoriz[ae]|decor[ae]|guard[ae]\s+(esse|um)\s+comando|"
    r"cri[ae]\s+um\s+comando|ensin[ae]\s+um\s+comando|(um\s+)?comando\s+novo|"
    r"quando\s+eu\s+(disser|falar|pedir|perguntar))\b")
_FORGET = re.compile(
    r"\b(esquec[ae]|apag[ae]|remov[ae]|deleta|tira)\s+(o\s+)?comando\b|"
    r"\bdesaprend[ae]\b")
_LIST = re.compile(
    r"\b(quais|que)\s+comandos?\s+(voce\s+)?(aprendeu|sabe|criou|tem\s+guardado)|"
    r"\bcomandos?\s+(que\s+voce\s+)?aprend\w+|\bo\s+que\s+voce\s+aprendeu\b")


def match_enter(t: str) -> bool:
    return _ENTER.search(t) is not None


def match_forget(t: str) -> bool:
    return _FORGET.search(t) is not None


def match_list(t: str) -> bool:
    return _LIST.search(t) is not None


def _strip_lead(raw: str) -> str:
    """Tira o 'aprende:' / 'quando eu disser' e devolve só a instrução."""
    s = raw.strip()
    s = re.sub(r"^(jarvis[,:]?\s*)?", "", s, flags=re.I)
    s = re.sub(r"^(aprend\w*|memoriz\w*|decor\w*|ensin\w*\s+um\s+comando|"
               r"cri\w*\s+um\s+comando|guard\w*\s+(esse|um)\s+comando|comando\s+novo)"
               r"[\s:,-]*", "", s, flags=re.I)
    return s.strip() or raw.strip()


def parse(raw: str, brain) -> dict | None:
    """Devolve o spec do comando, ou None se não deu."""
    instr = _strip_lead(raw)
    if len(instr) < 8:
        return None
    try:
        out = brain._post(
            [{"role": "system", "content": _SYS},
             {"role": "user", "content": instr}],
            220, temperature=0.1)
    except Exception as exc:                      # noqa: BLE001
        log(f"teach: LLM falhou ({exc})")
        return None
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        log(f"teach: sem JSON na resposta: {out[:120]!r}")
        return None
    try:
        spec = json.loads(m.group(0))
    except ValueError:
        log(f"teach: JSON inválido: {m.group(0)[:120]!r}")
        return None
    return _sanitize(spec)


def _sanitize(spec: dict) -> dict | None:
    name = str(spec.get("name", "")).strip().lower()[:40]
    pats = spec.get("patterns") or []
    pats = [str(p).strip().lower() for p in pats if str(p).strip()][:5]
    if not name or not pats:
        return None
    # patterns viram regex seguras: escapa metacaracteres, mantém espaços e letras
    safe_pats = []
    for p in pats:
        p = norm(p).strip()
        if len(p) < 3 or p in ("jarvis", "comando", "isso"):
            continue
        safe_pats.append(re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\1", p))
    if not safe_pats:
        return None
    out = {
        "name": name,
        "patterns": safe_pats,
        "speak": str(spec.get("speak", "")).strip()[:200],
        "open": str(spec.get("open", "")).strip()[:200],
        "then": str(spec.get("then", "")).strip()[:120],
        "run": str(spec.get("run", "")).strip()[:300],
    }
    if out["run"]:
        out["confirm"] = True            # shell sempre confirmado
    if not (out["speak"] or out["open"] or out["then"] or out["run"]):
        out["speak"] = "Feito, senhor."
    return out


def confirm_text(spec: dict) -> str:
    gatilho = spec["patterns"][0].replace("\\", "")
    acoes = []
    if spec.get("speak"):
        acoes.append(f"respondo \"{spec['speak']}\"")
    if spec.get("open"):
        acoes.append(f"abro {spec['open']}")
    if spec.get("then"):
        acoes.append(f"executo \"{spec['then']}\"")
    if spec.get("run"):
        acoes.append("rodo um comando no sistema (com confirmação)")
    return (f"Entendi, senhor. Vou criar o comando \"{spec['name']}\": quando você "
            f"disser \"{gatilho}\", eu " + " e ".join(acoes) + ". Confirma?")
