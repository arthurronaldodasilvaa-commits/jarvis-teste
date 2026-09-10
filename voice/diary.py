#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
diary.py — "diário de bordo" do Jarvis.

Não escreve nada novo: lê o próprio `jarvis_voice.log` e monta um resumo do
que rolou no dia (comandos usados, tempo de estudo, lembretes que venceram).

  "Jarvis, o que eu fiz hoje?"
  "Jarvis, resumo do dia"
  "Jarvis, o que eu fiz ontem?"
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta

from common import LOG_PATH, log, norm

# categorias amigáveis a partir do começo do comando normalizado
_CATS = [
    (r"\b(toca|tocar|bota|poe|coloca|ponha|som|musica|playlist|spotify)\b", "música"),
    (r"\b(cria|faz|desenha|mostra|plota|holograma|molecula|circulo|grafico|"
     r"lancamento|pendulo|onda|vetor|derivada|integral|circuito)\b", "hologramas"),
    (r"\b(estuda\w*|modo estudo|modo prova|modo redacao|proxima questao|"
     r"me explica|uma dica|aula sobre)\b", "estudo"),
    (r"\b(lembr\w+|timer|pomodoro|cronometr\w+|alarme|despertador)\b", "lembretes"),
    (r"\b(tarefa|lista|adiciona|risca)\b", "tarefas"),
    (r"\b(abre|abrir|joga|jogar|steam)\b", "abrir programas"),
    (r"\b(pesquisa|procura|google|busca|como chegar|mapa)\b", "buscas"),
    (r"\b(clima|tempo|previs\w+|vai chover)\b", "clima"),
    (r"\b(quem foi|o que e|o que significa|resume|noticias|quanto ta|acao da|"
     r"feriado|cep|qualidade do ar|fase da lua)\b", "consultas"),
    (r"\b(que horas|que dia|quantos dias)\b", "hora e data"),
    (r"\b(digita|escreve|anota|memo|print|area de transferencia)\b", "escrita"),
    (r"\b(camera|desativa a camera|volta pro cerebro|modo desenho|modo medida)\b", "câmera"),
    (r"\b(volume|mudo|pausa|proxima musica|aumenta|diminui)\b", "controle de mídia"),
]


def _junta(xs: list[str]) -> str:
    if len(xs) == 1:
        return xs[0]
    return ", ".join(xs[:-1]) + " e " + xs[-1]


def _cat(cmd_norm: str) -> str:
    for pat, name in _CATS:
        if re.search(pat, cmd_norm):
            return name
    return "outros"


def match(t: str) -> str | None:
    """Devolve 'hoje' / 'ontem' se a fala pedir o diário, senão None."""
    if not re.search(r"\b(o que eu fiz|resumo do dia|meu dia|diario de bordo|"
                     r"o que fiz|minhas atividades|o que rolou)\b", t):
        return None
    return "ontem" if "ontem" in t else "hoje"


def _lines_for(day) -> list[str]:
    """Linhas do log com prefixo [MM-DD ...] daquele dia."""
    try:
        raw = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    pre = f"[{day:%m-%d} "
    return [ln for ln in raw if ln.startswith(pre)]


def resumo(quando: str, brain=None) -> str:
    alvo = datetime.now().date() if quando == "hoje" else (datetime.now().date() - timedelta(days=1))
    linhas = _lines_for(alvo)
    if not linhas and quando != "hoje":
        return ("Não achei registro de ontem, senhor — o log pode ter rotacionado.")

    cmds = re.findall(r"comando:\s*'([^']+)'", "\n".join(linhas))
    cmds = [c for c in cmds if norm(c)]
    fires = len(re.findall(r"lembrete:\s*'[^']+'\s*para", "\n".join(linhas)))
    venc = len(re.findall(r"Senhor, lembrete:", "\n".join(linhas)))

    if not cmds and not venc:
        return "Hoje ainda não teve muita coisa, senhor."

    cats = Counter(_cat(norm(c)) for c in cmds)
    nomes = [nome for nome, _ in cats.most_common(3) if nome != "outros"]
    dia = "Hoje" if quando == "hoje" else "Ontem"
    frase = f"{dia} o senhor usou o Jarvis {len(cmds)} vez" + ("es" if len(cmds) != 1 else "")
    if nomes:
        frase += ", principalmente para " + _junta(nomes)
    frase += "."
    if fires:
        frase += f" Criou {fires} lembrete" + ("s" if fires != 1 else "") + "."
    if venc:
        v = "venceu" if venc == 1 else "venceram"
        frase += f" {venc} lembrete" + ("s" if venc != 1 else "") + f" {v}."

    log(f"diário: {len(cmds)} comandos, cats={dict(cats)}")
    return frase
