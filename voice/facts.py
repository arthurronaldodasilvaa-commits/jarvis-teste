#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
facts.py — consultas rápidas via APIs SEM CHAVE (grátis).

  "quanto tá a Petrobras / a ação da Vale"     -> brapi.dev (B3)
  "que endereço é o CEP 01001-000"             -> ViaCEP
  "quando é o próximo feriado"                 -> BrasilAPI
  "como tá a qualidade do ar"                  -> Open-Meteo air-quality
  "que horas o sol nasce / se põe"             -> Open-Meteo daily
  "qual a fase da lua"                         -> Open-Meteo (código) + tabela
  "o que aconteceu num dia como hoje"          -> Wikipedia "on this day" (pt)
  "resume esse site: <url>"                    -> baixa, extrai texto, LLM resume
  "me dá uma frase / citação"                  -> ZenQuotes / local
"""
from __future__ import annotations

import re
from datetime import date, datetime

from common import log, norm

_UA = {"User-Agent": "JarvisVoice/1.0 (https://github.com/open-jarvis/OpenJarvis; assistente de voz local)"}


def _get(url, params=None, timeout=8, headers=None):
    import httpx
    r = httpx.get(url, params=params, timeout=timeout,
                  headers={**_UA, **(headers or {})}, follow_redirects=True)
    r.raise_for_status()
    return r


# --------------------------------------------------------------------------
_TICKERS = {
    "petrobras": "PETR4", "petrobrás": "PETR4", "petro": "PETR4",
    "vale": "VALE3", "itau": "ITUB4", "itaú": "ITUB4", "bradesco": "BBDC4",
    "ambev": "ABEV3", "magazine luiza": "MGLU3", "magalu": "MGLU3",
    "b3": "B3SA3", "weg": "WEGE3", "banco do brasil": "BBAS3",
    "eletrobras": "ELET3", "gerdau": "GGBR4", "natura": "NTCO3",
    "ibovespa": "^BVSP", "ibov": "^BVSP",
}


def _acao(t: str):
    m = re.search(r"\b(a[cç][aã]o d[ao]|quanto (ta|esta|vale)|cota[cç][aã]o d[ao]|"
                  r"pre[cç]o d[ao])\s+([a-z0-9 ]+?)(\?|$| hoje| agora)", t)
    alvo = None
    if m:
        alvo = m.group(3).strip()
    else:
        for k in _TICKERS:
            if re.search(rf"\b{re.escape(k)}\b", t) and re.search(r"\ba[cç][aã]o\b|\bbolsa\b|\bibov", t):
                alvo = k
                break
    if not alvo:
        return None
    tk = _TICKERS.get(alvo) or _TICKERS.get(norm(alvo))
    if not tk:
        for k, v in _TICKERS.items():
            if k in alvo:
                tk = v
                break
    if not tk:
        return None
    try:
        d = _get(f"https://brapi.dev/api/quote/{tk}").json()
        r = (d.get("results") or [None])[0]
        if not r:
            return "Não achei essa ação, senhor."
        preco = r.get("regularMarketPrice")
        var = r.get("regularMarketChangePercent")
        nome = r.get("shortName") or tk
        seta = "subindo" if (var or 0) >= 0 else "caindo"
        return (f"{nome}, senhor: {preco:.2f} reais, {seta} {abs(var):.2f}% hoje."
                if preco is not None else "A cotação veio incompleta, senhor.")
    except Exception as exc:  # noqa: BLE001
        log(f"facts/ação: {exc}")
        return "Não consegui a cotação agora, senhor."


# --------------------------------------------------------------------------
def _cep(t: str):
    m = re.search(r"\bcep\s*:?\s*(\d{5})[-\s]?(\d{3})\b", t)
    if not m:
        return None
    cep = m.group(1) + m.group(2)
    try:
        d = _get(f"https://viacep.com.br/ws/{cep}/json/").json()
        if d.get("erro"):
            return "Esse CEP não existe, senhor."
        return (f"CEP {cep[:5]}-{cep[5:]}, senhor: {d.get('logradouro','')}, "
                f"{d.get('bairro','')}, {d.get('localidade','')} - {d.get('uf','')}.")
    except Exception as exc:  # noqa: BLE001
        log(f"facts/cep: {exc}")
        return "Não consegui consultar o CEP, senhor."


# --------------------------------------------------------------------------
def _feriado(t: str):
    if not re.search(r"\bferiad", t):
        return None
    ano = datetime.now().year
    m = re.search(r"\b(20\d\d)\b", t)
    if m:
        ano = int(m.group(1))
    try:
        d = _get(f"https://brasilapi.com.br/api/feriados/v1/{ano}").json()
    except Exception as exc:  # noqa: BLE001
        log(f"facts/feriado: {exc}")
        return "Não consegui a lista de feriados, senhor."
    hoje = date.today()
    fut = sorted((datetime.strptime(f["date"], "%Y-%m-%d").date(), f["name"]) for f in d)
    if re.search(r"\bpr[oó]ximo\b|\bque vem\b|\bqual (o|é o)\b", t):
        prox = next(((dt, nm) for dt, nm in fut if dt >= hoje), None)
        if not prox:
            return f"Não há mais feriados nacionais em {ano}, senhor."
        dias = (prox[0] - hoje).days
        quando = "hoje" if dias == 0 else ("amanhã" if dias == 1 else f"em {dias} dias")
        return f"O próximo feriado é {prox[1]}, {quando} ({prox[0]:%d/%m}), senhor."
    prox3 = [f"{nm} ({dt:%d/%m})" for dt, nm in fut if dt >= hoje][:3]
    return "Próximos feriados, senhor: " + "; ".join(prox3) + "." if prox3 else \
           f"Acabaram os feriados de {ano}, senhor."


# --------------------------------------------------------------------------
def _coords(cfg):
    try:
        import weather
        return weather._resolve(cfg, None)
    except Exception:  # noqa: BLE001
        return None


def _ar(t: str, cfg):
    if not re.search(r"qualidade do ar|poluic|\bar (ta|esta|está) (bom|ruim|limpo)|"
                     r"\bíndice.*\bar\b|\bar\b.*respirar", t):
        return None
    loc = _coords(cfg)
    if not loc:
        return "Não sei a localização pra checar o ar, senhor."
    lat, lon, nome = loc
    try:
        d = _get("https://air-quality-api.open-meteo.com/v1/air-quality",
                 {"latitude": lat, "longitude": lon,
                  "current": "european_aqi,pm2_5,pm10"}).json()
        c = d.get("current", {})
        aqi = c.get("european_aqi")
        nivel = ("boa" if aqi <= 20 else "razoável" if aqi <= 40 else "moderada"
                 if aqi <= 60 else "ruim" if aqi <= 80 else "muito ruim") if aqi is not None else "?"
        return (f"Qualidade do ar em {nome}, senhor: {nivel} (índice {aqi:.0f}, "
                f"partículas finas {c.get('pm2_5','?')}).")
    except Exception as exc:  # noqa: BLE001
        log(f"facts/ar: {exc}")
        return "Não consegui os dados do ar, senhor."


def _sol_lua(t: str, cfg):
    quer_sol = re.search(r"\bsol\b.*(nasce|nascer|p[õo]e|por do sol|amanhece|anoitece)|"
                         r"que horas.*(amanhece|anoitece|escurece)|nascer do sol|por do sol", t)
    quer_lua = re.search(r"\bfase da lua\b|\blua\b.*(cheia|nova|crescente|minguante|hoje)", t)
    if not (quer_sol or quer_lua):
        return None
    loc = _coords(cfg)
    if not loc:
        return "Não sei a localização, senhor."
    lat, lon, nome = loc
    try:
        d = _get("https://api.open-meteo.com/v1/forecast",
                 {"latitude": lat, "longitude": lon, "timezone": "auto",
                  "daily": "sunrise,sunset"}).json()
        dl = d.get("daily", {})
        nasce = dl.get("sunrise", ["?"])[0][-5:]
        poe = dl.get("sunset", ["?"])[0][-5:]
    except Exception as exc:  # noqa: BLE001
        log(f"facts/sol: {exc}")
        return "Não consegui os horários do sol, senhor."
    if quer_sol and not quer_lua:
        return f"Em {nome}, senhor: o sol nasce às {nasce} e se põe às {poe}."
    fase = _fase_lua()
    if quer_lua and not quer_sol:
        return f"A lua está {fase}, senhor."
    return f"Sol das {nasce} às {poe}; a lua está {fase}, senhor."


def _fase_lua():
    # aproximação: ciclo de 29,53 dias a partir de uma lua nova conhecida
    conhecida = datetime(2000, 1, 6, 18, 14)
    dias = (datetime.now() - conhecida).total_seconds() / 86400
    f = (dias % 29.53059) / 29.53059
    if f < 0.03 or f > 0.97:
        return "nova"
    if f < 0.22:
        return "crescente côncava"
    if f < 0.28:
        return "quarto crescente"
    if f < 0.47:
        return "crescente gibosa"
    if f < 0.53:
        return "cheia"
    if f < 0.72:
        return "minguante gibosa"
    if f < 0.78:
        return "quarto minguante"
    return "minguante côncava"


# --------------------------------------------------------------------------
def _hoje_historia(t: str):
    if not re.search(r"(hoje na hist[oó]ria|dia como hoje|aconteceu.*\b(hoje|nesta data|neste dia)\b|"
                     r"efem[ée]rides?)", t):
        return None
    n = datetime.now()
    try:
        d = _get(f"https://pt.wikipedia.org/api/rest_v1/feed/onthisday/events/"
                 f"{n.month}/{n.day}").json()
        ev = sorted(d.get("events", []), key=lambda e: -int(e.get("year", 0)))[:3]
        if not ev:
            return "Não achei nada pra hoje, senhor."
        linhas = [f"em {e.get('year','?')}, {e.get('text','')}" for e in ev]
        return f"Num dia como hoje, senhor: " + "; ".join(linhas) + "."
    except Exception as exc:  # noqa: BLE001
        log(f"facts/história: {exc}")
        return "Não consegui as efemérides, senhor."


# --------------------------------------------------------------------------
def _resumo_link(t: str, raw: str, brain):
    m = re.search(r"https?://\S+", raw)
    if not m or not re.search(r"\bresum\w+\b|\bo que (diz|tem)\b.*http|\bmе conta esse\b", norm(t) + " http"):
        if not (m and re.search(r"\bresum", t)):
            return None
    url = m.group(0).rstrip(").,")
    try:
        html = _get(url, timeout=12).text
    except Exception as exc:  # noqa: BLE001
        log(f"facts/link: {exc}")
        return "Não consegui abrir esse link, senhor."
    txt = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()[:4000]
    if len(txt) < 120:
        return "Essa página não tem texto que dê pra resumir, senhor."
    if brain is None:
        return txt[:300] + "…"
    try:
        return brain._post(
            [{"role": "system", "content": "Resuma em 2-3 frases, português do Brasil, "
              "só o essencial. Sem 'este artigo fala sobre'."},
             {"role": "user", "content": txt}], 160, temperature=0.3).strip()
    except Exception as exc:  # noqa: BLE001
        log(f"facts/resumo LLM: {exc}")
        return "Não consegui resumir agora, senhor."


# --------------------------------------------------------------------------
_FRASES = [
    "A persistência realiza o impossível. — provérbio chinês",
    "O que sabemos é uma gota; o que ignoramos é um oceano. — Isaac Newton",
    "Disciplina é a ponte entre metas e realizações. — Jim Rohn",
    "Não é sobre ter tempo, é sobre fazer tempo.",
    "O sucesso é a soma de pequenos esforços repetidos dia após dia.",
    "Faça o que é necessário, depois o possível; e de repente você faz o impossível. — São Francisco",
]


def _frase(t: str):
    if not re.search(r"\b(frase|cita[cç][aã]o|pensamento|motiva[cç][aã]o)\b.*\b(do dia|motiv|inspir|legal|boa)\b|"
                     r"\bme (d[aá]|manda) uma frase\b|\bframe motivacional\b", t):
        return None
    try:
        d = _get("https://zenquotes.io/api/today", timeout=6).json()
        q = d[0]
        return f"{q['q']} — {q['a']}, senhor."
    except Exception:  # noqa: BLE001
        import random
        return random.choice(_FRASES) + ", senhor."


# --------------------------------------------------------------------------
def handle(raw: str, cfg: dict, brain) -> "object | None":
    """Devolve um skills.Result ou None."""
    import skills
    R = skills.Result
    t = norm(raw)
    for fn in (
        lambda: _acao(t),
        lambda: _cep(t),
        lambda: _feriado(t),
        lambda: _ar(t, cfg),
        lambda: _sol_lua(t, cfg),
        lambda: _hoje_historia(t),
        lambda: _frase(t),
        lambda: _resumo_link(t, raw, brain),
    ):
        try:
            out = fn()
        except Exception as exc:  # noqa: BLE001
            log(f"facts handle: {exc}")
            out = None
        if out:
            return R(speak=out)
    return None
