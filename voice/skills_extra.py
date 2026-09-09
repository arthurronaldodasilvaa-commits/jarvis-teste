#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
skills_extra.py — catálogo de skills DECLARATIVO (ideia do agent-spec do kimi-cli).

O Senhor (ou o Robson) adiciona comandos editando `voice/skills_extra.toml`,
sem escrever Python. Cada entrada:

  [[skill]]
  name = "chinelo"
  patterns = ["cad[eê] (o )?(meu )?chinelo", "onde (esta|tá) o chinelo"]
  speak = "Debaixo da cama, senhor. Sempre."

  [[skill]]
  name = "edital"
  patterns = ["abre (o )?(meu )?edital", "mostra o edital"]
  open  = "E:/Estudos/edital.pdf"          # arquivo, pasta, http(s):// ou nome de app
  speak = "Abrindo o edital, senhor."

  [[skill]]
  name = "foco"
  patterns = ["modo foco", "hora de estudar"]
  then  = "modo cinema"                     # re-despacha esse comando
  speak = "Modo foco ativado, senhor."

  [[skill]]
  name = "limpar downloads"
  patterns = ["limpa (a pasta )?downloads"]
  run = "powershell -c \"Remove-Item $env:USERPROFILE\\Downloads\\* -Recurse\""
  confirm = true                            # pede 'sim' antes
  speak = "Downloads limpos, senhor."

As entradas são checadas ANTES da torre de regex principal — o que o usuário
adiciona tem prioridade. Padrões são regex, casados no texto normalizado
(minúsculo, sem acento). Fail-open: arquivo inválido = catálogo vazio + log.
"""
from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from pathlib import Path

from common import HERE, log, norm

try:
    import tomllib
except ModuleNotFoundError:                       # py < 3.11
    import tomli as tomllib                        # type: ignore

FILE = HERE / "skills_extra.toml"
CNW = 0x08000000

_cache: dict = {"mtime": -1.0, "skills": []}


def _load() -> list[dict]:
    try:
        mt = FILE.stat().st_mtime
    except OSError:
        if _cache["mtime"] != 0:
            _cache.update(mtime=0, skills=[])
        return []
    if mt == _cache["mtime"]:
        return _cache["skills"]
    out = []
    try:
        data = tomllib.loads(FILE.read_text(encoding="utf-8"))
        for s in (data.get("skill", []) or []):
            pats = s.get("patterns") or ([s["pattern"]] if s.get("pattern") else [])
            if not pats:
                continue
            try:
                rx = [re.compile(p) for p in pats]
            except re.error as exc:
                log(f"skills_extra: regex inválida em {s.get('name','?')!r} ({exc})")
                continue
            out.append({
                "name": s.get("name", pats[0]),
                "rx": rx,
                "speak": s.get("speak", ""),
                "open": s.get("open", ""),
                "run": s.get("run", ""),
                "then": s.get("then", ""),
                "confirm": bool(s.get("confirm", False)),
            })
        log(f"skills_extra: {len(out)} skill(s) do catálogo")
    except Exception as exc:                      # noqa: BLE001
        log(f"skills_extra: skills_extra.toml inválido ({exc}) — ignorando")
    _cache.update(mtime=mt, skills=out)
    return out


def _do_open(target: str) -> None:
    t = target.strip()
    if re.match(r"https?://", t):
        webbrowser.open(t)
        return
    p = Path(t)
    if p.exists():
        os.startfile(str(p))                      # noqa: S606
        return
    # nome de app / comando do sistema
    try:
        os.startfile(t)                           # noqa: S606
    except OSError:
        subprocess.Popen(t, shell=True, creationflags=CNW,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)


def _run_shell(cmd: str) -> None:
    subprocess.Popen(cmd, shell=True, creationflags=CNW,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)


def match(t: str, raw: str, make_result, redispatch=None):
    """t = texto normalizado. `make_result` = a classe Result de skills.py.
    `redispatch(phrase)` re-despacha um comando (pro campo 'then').
    Devolve um Result ou None."""
    for s in _load():
        if not any(rx.search(t) for rx in s["rx"]):
            continue
        log(f"  skill do catálogo: {s['name']}")

        def _act(_s=s):
            if _s["open"]:
                _do_open(_s["open"])
            if _s["run"]:
                _run_shell(_s["run"])
            if _s["then"] and redispatch:
                redispatch(_s["then"])
            return _s["speak"] or "Feito, senhor."

        if s["confirm"]:
            return make_result(confirm=(f"Confirma: {s['name']}, senhor?",
                                        lambda _s=s: _act(_s)))
        say = _act()
        return make_result(speak=say if (s["speak"] or s["open"] or s["run"] or s["then"]) else "")
    return None
