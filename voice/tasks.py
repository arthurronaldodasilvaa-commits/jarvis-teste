#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tasks.py — lista de tarefas por voz.

  "Jarvis, adiciona estudar química na lista"
  "Jarvis, quais minhas tarefas"
  "Jarvis, risca a de química"  /  "marca a primeira como feita"
  "Jarvis, limpa a lista"

Guarda em voice/tasks.json. O HUD mostra as 3 abertas mais antigas.
"""
from __future__ import annotations

import json
import time

from common import HERE, log, norm, write_app_state

FILE = HERE / "tasks.json"


def _load() -> list[dict]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(items: list[dict]) -> None:
    try:
        FILE.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log(f"tasks: não salvou ({exc})")
    _push_hud(items)


def _push_hud(items=None) -> None:
    items = items if items is not None else _load()
    abertas = [it["text"] for it in items if not it.get("done")][:3]
    write_app_state(tasks=abertas)


def add(text: str) -> str:
    text = text.strip().rstrip(".")
    if not text:
        return "O que o senhor quer adicionar?"
    items = _load()
    items.append({"text": text, "done": False, "at": time.time()})
    _save(items)
    return f"Anotado, senhor: {text}."


def listar() -> str:
    items = [it for it in _load() if not it.get("done")]
    if not items:
        return "Sua lista está vazia, senhor."
    linhas = [f"{i + 1}, {it['text']}" for i, it in enumerate(items[:6])]
    return "Suas tarefas, senhor: " + "; ".join(linhas) + "."


def concluir(ref: str) -> str:
    items = _load()
    abertas = [it for it in items if not it.get("done")]
    if not abertas:
        return "Não tem tarefa pra riscar, senhor."
    ref = norm(ref)
    alvo = None
    m = None
    for w, n in {"primeira": 1, "segunda": 2, "terceira": 3, "quarta": 4,
                 "ultima": 99, "última": 99}.items():
        if w in ref:
            m = n
            break
    if m == 99:
        alvo = abertas[-1]
    elif m:
        alvo = abertas[m - 1] if m <= len(abertas) else None
    else:
        digs = "".join(c for c in ref if c.isdigit())
        if digs and int(digs) <= len(abertas):
            alvo = abertas[int(digs) - 1]
        else:
            stop = {"a", "o", "de", "da", "do", "e", "que", "tarefa", "aquela",
                    "essa", "esse", "minha", "coisa", "parte"}
            palavras = [w for w in ref.split() if w not in stop and len(w) > 2]
            best, bn = None, 0
            for it in abertas:
                txt = norm(it["text"])
                hits = sum(1 for w in palavras if w in txt)
                if hits > bn:
                    bn, best = hits, it
            alvo = best
    if not alvo:
        return "Não achei essa tarefa, senhor."
    alvo["done"] = True
    _save(items)
    return f"Feito: {alvo['text']}, senhor."


def limpar(so_feitas: bool = False) -> str:
    items = _load()
    if so_feitas:
        kept = [it for it in items if not it.get("done")]
    else:
        kept = []
    n = len(items) - len(kept)
    _save(kept)
    return f"Limpei {n} tarefa{'s' if n != 1 else ''}, senhor." if n else "Não tinha nada pra limpar, senhor."
