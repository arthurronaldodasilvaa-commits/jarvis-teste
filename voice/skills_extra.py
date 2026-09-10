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

import json
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

FILE = HERE / "skills_extra.toml"                 # manual (com os exemplos do Arthur)
LEARNED = HERE / "skills_learned.toml"            # o Jarvis grava aqui ("Jarvis, aprende: ...")
CNW = 0x08000000

_cache: dict = {"key": None, "skills": []}


def _mtimes() -> tuple:
    def _m(p):
        try:
            return p.stat().st_mtime
        except OSError:
            return 0
    return (_m(FILE), _m(LEARNED))


def _parse_one(s: dict, origem: str) -> dict | None:
    pats = s.get("patterns") or ([s["pattern"]] if s.get("pattern") else [])
    if not pats:
        return None
    try:
        rx = [re.compile(p) for p in pats]
    except re.error as exc:
        log(f"skills_extra: regex inválida em {s.get('name','?')!r} ({exc})")
        return None
    return {
        "name": s.get("name", pats[0]),
        "rx": rx,
        "patterns": pats,
        "speak": s.get("speak", ""),
        "open": s.get("open", ""),
        "run": s.get("run", ""),
        "then": s.get("then", ""),
        "confirm": bool(s.get("confirm", False)),
        "origem": origem,
    }


def _load() -> list[dict]:
    key = _mtimes()
    if key == _cache["key"]:
        return _cache["skills"]
    out = []
    for path, origem in ((FILE, "manual"), (LEARNED, "aprendido")):
        if not path.is_file():
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            for s in (data.get("skill", []) or []):
                one = _parse_one(s, origem)
                if one:
                    out.append(one)
        except Exception as exc:                  # noqa: BLE001
            log(f"skills_extra: {path.name} inválido ({exc}) — ignorando")
    log(f"skills_extra: {len(out)} skill(s) no catálogo")
    _cache.update(key=key, skills=out)
    return out


# --------------------------------------------------------------------------
# gravação (usado pelo teach.py — "Jarvis, aprende ...")
# --------------------------------------------------------------------------
def _load_learned_raw() -> list[dict]:
    if not LEARNED.is_file():
        return []
    try:
        return tomllib.loads(LEARNED.read_text(encoding="utf-8")).get("skill", []) or []
    except Exception:                             # noqa: BLE001
        return []


def _dump_learned(skills: list[dict]) -> None:
    lines = ["# skills_learned.toml — comandos que o Jarvis aprendeu por voz.",
             "# NÃO edite à mão: use \"Jarvis, aprende ...\" e \"Jarvis, esquece o comando ...\".",
             ""]
    for s in skills:
        lines.append("[[skill]]")
        for k in ("name", "speak", "open", "then", "run"):
            if s.get(k):
                lines.append(f"{k} = {json.dumps(str(s[k]), ensure_ascii=False)}")
        pats = s.get("patterns") or []
        lines.append("patterns = [" + ", ".join(json.dumps(p, ensure_ascii=False) for p in pats) + "]")
        if s.get("confirm"):
            lines.append("confirm = true")
        lines.append("")
    LEARNED.write_text("\n".join(lines), encoding="utf-8")
    _cache["key"] = None


def add_learned(spec: dict) -> None:
    """spec: {name, patterns[], speak?, open?, then?, run?, confirm?}."""
    skills = [s for s in _load_learned_raw()
              if norm(s.get("name", "")) != norm(spec.get("name", ""))]
    skills.append({k: spec[k] for k in ("name", "patterns", "speak", "open", "then", "run", "confirm")
                   if spec.get(k)})
    _dump_learned(skills)
    log(f"skills_extra: aprendeu {spec.get('name')!r}")


def remove_learned(name: str) -> bool:
    n = norm(name)
    skills = _load_learned_raw()
    kept = [s for s in skills if n not in norm(s.get("name", ""))
            and not any(n in norm(p) for p in (s.get("patterns") or []))]
    if len(kept) == len(skills):
        return False
    _dump_learned(kept)
    log(f"skills_extra: esqueceu {name!r}")
    return True


def learned_names() -> list[str]:
    return [s.get("name", "?") for s in _load_learned_raw()]


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
