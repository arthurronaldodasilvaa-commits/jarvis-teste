#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
study.py — sessão de estudo ("modo Enem / redação / prova").

"Jarvis, modo Enem"  ->  carrega uma configuração inteira:
  - persona de PROFESSOR no LLM (explica passo a passo, incentiva, puxa assunto)
  - cronômetro da sessão (conta pra cima; "prova" conta pra trás e avisa)
  - HUD do app mostra: modo, tempo, matéria, nº de questões
  - atalhos só desse modo: "próxima questão", "me explica melhor", "uma dica",
    "quanto tempo", "muda pra química", "como tô indo"
"Jarvis, sair do modo estudo" (ou "modo normal")  ->  volta ao normal.

Modos em  voice/study/<nome>.toml . Fácil de adicionar mais.
"""
from __future__ import annotations

import re
import time

from common import HERE, log, norm, write_app_state

try:
    import tomllib
except ModuleNotFoundError:                       # py < 3.11
    import tomli as tomllib                        # type: ignore

DIR = HERE / "study"

_S: dict = {                                       # estado da sessão atual
    "mode": "", "name": "", "started": 0.0, "subject": "", "subjects": [],
    "q": 0, "hits": 0, "limit_min": 0, "warned": False,
}


# --------------------------------------------------------------------------
def _load_mode(mode: str) -> dict | None:
    f = DIR / f"{mode}.toml"
    if not f.is_file():
        return None
    try:
        return tomllib.loads(f.read_text(encoding="utf-8"))
    except Exception as exc:                       # noqa: BLE001
        log(f"study: {f.name} inválido ({exc})")
        return None


def list_modes() -> list[str]:
    return sorted(p.stem for p in DIR.glob("*.toml")) if DIR.is_dir() else []


def active() -> bool:
    return bool(_S["mode"])


def elapsed_min() -> float:
    return (time.time() - _S["started"]) / 60 if _S["started"] else 0.0


# --------------------------------------------------------------------------
_ALIASES = {
    "redacao": "redacao", "redação": "redacao", "escrita": "redacao",
    "prova": "prova", "simulado": "prova", "teste": "prova",
    "estudo": "estudo", "estudos": "estudo", "foco": "estudo", "aula": "estudo",
    "vestibular": "estudo",
}


def match_enter(t: str) -> str | None:
    """t normalizado. Devolve o nome do modo se a fala for 'modo <x>', senão None."""
    # não confundir com "adiciona estudar X na lista" etc.
    if re.search(r"\b(adiciona|anota|risca|marca|lista|tarefa|lembrete|na lista)\b", t):
        return None
    m = re.search(r"\bmod[eo]\s+(?:de\s+)?(redacao|redação|escrita|"
                  r"prova|simulado|teste|estudo|estudos|foco|aula|vestibular)\b", t)
    if not m:
        # "bora estudar pra prova", "vamos treinar redação", "quero estudar agora"
        m2 = re.search(r"\b(vamos|bora|quero|vou|preciso)\s+(estudar|treinar|revisar|"
                       r"praticar)\b(?:\s+(?:pra|para|pro|a|o))?\s*(redacao|redação|"
                       r"prova|vestibular|matematica|fisica|quimica|historia|agora|"
                       r"um pouco)?\b", t)
        if m2:
            return _ALIASES.get(m2.group(3) or "", "estudo")
        return None
    return _ALIASES.get(m.group(1), "estudo")


def match_exit(t: str) -> bool:
    return bool(re.search(r"\b(sa[ií]r?\s+d[oe]\s+(modo\s+)?(estudo|prova|redacao|redação|aula)|"
                          r"encerra\w*\s+(a\s+)?(sess[ãa]o|aula|prova|estudo)|"
                          r"acab\w*\s+(a\s+)?(prova|aula|sess[ãa]o|estudo)|"
                          r"terminei\s+de\s+estudar|modo\s+normal|volta\w*\s+ao\s+normal|"
                          r"para\w*\s+de\s+estudar)\b", t))


# --------------------------------------------------------------------------
def enter(mode: str, cfg: dict, brain) -> str:
    """Ativa a sessão. Devolve a fala de abertura."""
    md = _load_mode(mode) or {}
    _S.update(
        mode=mode,
        name=md.get("name", mode.capitalize()),
        started=time.time(),
        subjects=[s.strip() for s in md.get("subjects", [])],
        subject=(md.get("subjects") or [""])[0],
        q=0, hits=0,
        limit_min=int(md.get("timer_minutes", 0)),
        warned=False,
        _tutor=md.get("tutor_prompt", "").strip(),
        _shortcuts=md.get("shortcuts", {}) or {},
        _greeting=md.get("greeting", "").strip(),
    )
    if brain is not None:
        brain.extra_system = _S["_tutor"] or (
            "MODO ESTUDO: você é um professor paciente. Explique passo a passo, "
            "com exemplos, e no fim faça UMA pergunta curta pra checar se a pessoa "
            "entendeu. Seja breve e encorajador. Continue tratando por 'senhor'.")
        brain.forget()
    _push_hud()
    log(f"** modo estudo: {_S['name']} **")
    g = _S["_greeting"] or f"Modo {_S['name']} ativado, senhor. Vamos nessa."
    if _S["limit_min"]:
        g += f" Você tem {_S['limit_min']} minutos."
    return g


def exit_session(brain) -> str:
    if not active():
        return "Não estamos em modo estudo, senhor."
    mins = round(elapsed_min())
    q, hits = _S["q"], _S["hits"]
    _S.update(mode="", name="", started=0.0, subject="", subjects=[], q=0, hits=0,
              limit_min=0, warned=False)
    if brain is not None:
        brain.extra_system = ""
        brain.forget()
    write_app_state(study={"active": False})
    resumo = f"Sessão encerrada, senhor. {mins} minuto" + ("s" if mins != 1 else "")
    if q:
        resumo += f", {hits} de {q} questões certas"
    return resumo + "."


# --------------------------------------------------------------------------
def _push_hud() -> None:
    write_app_state(study={
        "active": True, "mode": _S["mode"], "name": _S["name"],
        "subject": _S["subject"], "q": _S["q"], "hits": _S["hits"],
        "elapsed": round(elapsed_min() * 60),
        "limit": _S["limit_min"] * 60,
    })


def tick(mouth) -> None:
    """Chamado ~a cada 15 s pelo daemon: atualiza o HUD e avisa do tempo."""
    if not active():
        return
    _push_hud()
    if _S["limit_min"] and not _S["warned"] and elapsed_min() >= _S["limit_min"]:
        _S["warned"] = True
        try:
            mouth.say(f"Senhor, o tempo da {_S['name']} acabou.")
        except Exception:                          # noqa: BLE001
            pass


# --------------------------------------------------------------------------
def handle(raw: str, cfg: dict, speak, brain) -> "object | None":
    """Atalhos que só existem no modo estudo. Devolve um Result ou None.
    Import tardio de skills pra não criar ciclo."""
    if not active():
        return None
    import skills
    R = skills.Result
    t = norm(raw)

    # quanto tempo já passou / falta
    if re.search(r"\bquanto\s+tempo\b|\bque\s+horas?\b.*prova|\btempo\b.*(passou|falta|resta)", t):
        e = round(elapsed_min())
        if _S["limit_min"]:
            rest = max(0, _S["limit_min"] - e)
            return R(speak=f"{e} minutos de sessão, senhor. Faltam {rest}.")
        return R(speak=f"{e} minuto" + ("s" if e != 1 else "") + " de estudo, senhor.")

    # como estou indo / placar
    if re.search(r"\bcomo\s+(t[oô]|estou|vou)\s+indo\b|\bmeu\s+(placar|desempenho|score)\b|"
                 r"\bquantas?\s+acertei\b", t):
        if not _S["q"]:
            return R(speak="Ainda não respondeu nenhuma questão, senhor.")
        return R(speak=f"{_S['hits']} de {_S['q']} certas, senhor. "
                       f"{round(elapsed_min())} minutos de sessão.")

    # trocar de matéria
    m = re.search(r"\b(muda|troca|vamos?\s+pra?|agora)\s+(pra?\s+|para\s+)?"
                  r"(matematica|português|portugues|fisica|quimica|biologia|historia|"
                  r"geografia|filosofia|sociologia|redacao|redação|ingles|literatura|"
                  r"atualidades|logica)\b", t)
    if m:
        _S["subject"] = m.group(3).capitalize()
        _push_hud()
        return R(speak=f"Mudando para {_S['subject']}, senhor.")

    # me explica melhor / mais simples
    if re.search(r"\b(explica|explique)\s+(isso\s+)?(melhor|de\s+novo|mais\s+simples|"
                 r"mais\s+devagar|de\s+outro\s+jeito)\b|\bn[ãa]o\s+entendi\b|"
                 r"\bpode\s+repetir\s+mais\s+devagar\b", t):
        prev = getattr(brain, "last_reply", "")
        base = prev or _S.get("_lastq", "")
        if not base:
            return R(speak="O que o senhor quer que eu explique?", to_llm=None)
        return R(to_llm=f"Explique de novo, MUITO mais simples e devagar, com uma "
                        f"analogia do dia a dia: {base}")

    # uma dica (sem entregar a resposta)
    if re.search(r"\b(uma\s+dica|me\s+d[aá]\s+um\s+empurr|d[aá]\s+uma\s+pista|"
                 r"me\s+ajuda\s+a\s+pensar)\b", t):
        q = _S.get("_lastq", "")
        if not q:
            return R(speak="Peça uma questão primeiro, senhor: \"próxima questão\".")
        return R(to_llm=f"Dê só uma DICA para esta pergunta, sem entregar a resposta: {q}")

    # próxima questão / me pergunta
    if re.search(r"\b(pr[oó]xima\s+(quest[ãa]o|pergunta)|outra\s+(quest[ãa]o|pergunta)|"
                 r"me\s+(pergunta|questiona|testa)|manda\s+(uma\s+)?(quest[ãa]o|pergunta)|"
                 r"bora\s+(a\s+)?pr[oó]xima|mais\s+uma)\b", t):
        return _next_question(brain)

    # atalhos declarados no toml do modo (frase -> comando canônico)
    for phrase, canon in (_S.get("_shortcuts") or {}).items():
        if norm(phrase) in t:
            return skills.dispatch(canon, cfg, speak, brain, _depth=1)

    return None


def _next_question(brain) -> "object":
    import skills
    R = skills.Result
    tema = _S["subject"] or _S["name"]
    try:
        q = brain._post(
            [{"role": "system", "content":
              "Você é um professor de cursinho. Faça UMA questão de múltipla escolha "
              "curta (enunciado + alternativas A a D) sobre o tema, nível Enem. "
              "Não revele a resposta. Português do Brasil."},
             {"role": "user", "content": f"Tema: {tema}"}],
            180, temperature=0.6).strip()
    except Exception as exc:                       # noqa: BLE001
        log(f"study: questão falhou ({exc})")
        return R(speak="Não consegui gerar a questão agora, senhor.")
    if not q:
        return R(speak="Não consegui gerar a questão agora, senhor.")
    _S["_lastq"] = q
    _S["q"] += 1
    _push_hud()

    def _grade(resposta: str):
        import skills as _sk
        try:
            verdict = brain._post(
                [{"role": "system", "content":
                  "O aluno respondeu uma questão. Diga se acertou. Responda começando "
                  "com 'Correto' ou 'Errado', depois a resposta certa e 1 frase de "
                  "explicação. Curto. Português do Brasil."},
                 {"role": "user", "content": f"QUESTÃO:\n{_S['_lastq']}\n\nRESPOSTA DO ALUNO: {resposta}"}],
                120, temperature=0.2).strip()
        except Exception:                          # noqa: BLE001
            return "Não consegui corrigir agora, senhor."
        if re.match(r"\s*correto", verdict, re.I):
            _S["hits"] += 1
        _push_hud()
        nxt = " Diga \"próxima\" pra continuar, senhor." if _S["q"] < 30 else ""
        return verdict + nxt

    return R(speak=q + "\n\nPode responder, senhor.", await_reply=_grade)
