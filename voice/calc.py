#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
calc.py — contas, porcentagem e conversão de unidades/moeda por voz.

  "quanto é 15 por cento de 240"
  "quanto é 342 vezes 12"
  "quanto é a raiz de 144"
  "quantos quilômetros são 5 milhas"
  "converte 100 dólares pra real"
  "80 fahrenheit em celsius"
"""
from __future__ import annotations

import ast
import operator
import re
import time

from common import log, norm

# ------------------------------------------------------------------ contas
_WORDS = {
    "mais": "+", "menos": "-", "vezes": "*", "multiplicado por": "*", "x": "*",
    "dividido por": "/", "sobre": "/", "por": "/",
    "ao quadrado": "**2", "ao cubo": "**3", "elevado a": "**",
}
_NUMW = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11,
    "doze": 12, "treze": 13, "quatorze": 14, "catorze": 14, "quinze": 15,
    "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20,
    "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70,
    "oitenta": 80, "noventa": 90, "cem": 100, "cento": 100, "mil": 1000,
    "meio": 0.5, "meia": 0.5, "metade": 0.5,
}
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}


def _safe_eval(expr: str) -> float:
    node = ast.parse(expr, mode="eval").body
    return _ev(node)


def _ev(n):
    if isinstance(n, ast.Constant):
        return n.value
    if isinstance(n, ast.BinOp):
        return _OPS[type(n.op)](_ev(n.left), _ev(n.right))
    if isinstance(n, ast.UnaryOp):
        return _OPS[type(n.op)](_ev(n.operand))
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
        import math
        fn = {"sqrt": math.sqrt, "raiz": math.sqrt, "abs": abs}[n.func.id]
        return fn(*[_ev(a) for a in n.args])
    raise ValueError("expressão não suportada")


def _fmt(v: float) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, float):
        v = round(v, 4)
    s = f"{v:,}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def _words_to_num(s: str) -> str:
    for w, n in sorted(_NUMW.items(), key=lambda kv: -len(kv[0])):
        s = re.sub(rf"\b{w}\b", str(n), s)
    return s


def _percent(t: str) -> str | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|por ?cento)\s*(?:de|do|da|em|no|na)?\s*"
                  r"(\d+(?:[.,]\d+)?)", t)
    if m:
        p = float(m.group(1).replace(",", "."))
        base = float(m.group(2).replace(",", "."))
        return f"{_fmt(p / 100 * base)}, senhor."
    # "quanto X é de Y" -> proporção
    m = re.search(r"quanto\s+(\d+(?:[.,]\d+)?)\s+(?:e|de|representa|em relacao a)\s+"
                  r"(\d+(?:[.,]\d+)?)", t)
    if m:
        a = float(m.group(1).replace(",", "."))
        b = float(m.group(2).replace(",", "."))
        if b:
            return f"{_fmt(a / b * 100)} por cento, senhor."
    return None


def calc(t: str) -> str | None:
    """t normalizado. Retorna fala ou None."""
    if not re.search(r"\b(quanto|calcul\w+|conta|resultado|soma|quant[oa]s)\b|[-+*/%]|"
                     r"\b(mais|menos|vezes|dividido|raiz|quadrado|cubo|dobro|triplo|metade|"
                     r"por ?cento)\b", t):
        return None

    r = _percent(t)
    if r:
        return r

    m = re.search(r"\b(dobro|triplo|metade|raiz)\s+(?:de|do|da)\s+(\d+(?:[.,]\d+)?)", t)
    if m:
        x = float(m.group(2).replace(",", "."))
        k = {"dobro": x * 2, "triplo": x * 3, "metade": x / 2,
             "raiz": x ** 0.5}[m.group(1)]
        return f"{_fmt(k)}, senhor."

    # expressão aritmética
    expr = _words_to_num(t)
    expr = re.sub(r"\b(raiz (?:quadrada )?de|raiz de)\b", "sqrt", expr)
    for w, sym in _WORDS.items():
        expr = expr.replace(w, sym)
    expr = expr.replace("×", "*").replace("÷", "/").replace(",", ".")
    expr = re.sub(r"[^0-9+\-*/(). a-z]", " ", expr)
    expr = re.sub(r"\bsqrt\s+([\d.]+)", r"sqrt(\1)", expr)
    m = re.search(r"[-+]?\d[\d.\s]*(?:\s*[-+*/]+\s*\(*\s*(?:sqrt\(?)?[\d.]+\)*)+|"
                  r"sqrt\([\d.]+\)|\d+\s*\*\*\s*\d+", expr)
    if not m:
        return None
    frag = m.group(0).strip()
    try:
        val = _safe_eval(frag)
    except Exception:  # noqa: BLE001
        return None
    return f"{_fmt(val)}, senhor."


# ------------------------------------------------------------ conversões
# fator para a unidade base (metro / grama / —)
_LEN = {
    "mm": 0.001, "milimetro": 0.001, "milimetros": 0.001,
    "cm": 0.01, "centimetro": 0.01, "centimetros": 0.01,
    "m": 1.0, "metro": 1.0, "metros": 1.0,
    "km": 1000.0, "quilometro": 1000.0, "quilometros": 1000.0, "kilometro": 1000.0,
    "kilometros": 1000.0,
    "milha": 1609.344, "milhas": 1609.344,
    "pe": 0.3048, "pes": 0.3048, "polegada": 0.0254, "polegadas": 0.0254,
    "jarda": 0.9144, "jardas": 0.9144,
}
_MASS = {
    "mg": 0.001, "g": 1.0, "grama": 1.0, "gramas": 1.0,
    "kg": 1000.0, "quilo": 1000.0, "quilos": 1000.0, "kilo": 1000.0, "kilos": 1000.0,
    "quilograma": 1000.0, "quilogramas": 1000.0,
    "tonelada": 1_000_000.0, "toneladas": 1_000_000.0,
    "libra": 453.592, "libras": 453.592, "lb": 453.592,
    "onca": 28.3495, "oncas": 28.3495, "oz": 28.3495,
}
_LEN_NAME = {"m": "metros", "km": "quilômetros", "cm": "centímetros", "mm": "milímetros",
             "milha": "milhas", "pe": "pés", "polegada": "polegadas", "jarda": "jardas"}
_MASS_NAME = {"g": "gramas", "kg": "quilos", "mg": "miligramas", "tonelada": "toneladas",
              "libra": "libras", "onca": "onças"}

_CUR = {
    "real": "BRL", "reais": "BRL", "brl": "BRL",
    "dolar": "USD", "dolares": "USD", "usd": "USD",
    "euro": "EUR", "euros": "EUR", "eur": "EUR",
    "libra esterlina": "GBP", "libras esterlinas": "GBP", "gbp": "GBP",
    "peso": "ARS", "pesos": "ARS", "iene": "JPY", "ienes": "JPY",
    "franco": "CHF", "francos": "CHF", "dolar canadense": "CAD",
}
_CUR_NAME = {"BRL": "reais", "USD": "dólares", "EUR": "euros", "GBP": "libras",
             "ARS": "pesos", "JPY": "ienes", "CHF": "francos", "CAD": "dólares canadenses"}
_FX_CACHE: dict = {}


def _canon(word: str, table: dict) -> str | None:
    w = word.strip()
    if w in table:
        return w
    if w + "s" in table:
        return w + "s"
    if w.endswith("s") and w[:-1] in table:
        return w[:-1]
    return None


def _fx(frm: str, to: str) -> float | None:
    if frm == to:
        return 1.0
    key = f"{frm}{to}"
    hit = _FX_CACHE.get(key)
    if hit and hit[1] > time.time():
        return hit[0]
    import httpx
    for url, parse in (
        ("https://api.frankfurter.dev/v1/latest",
         lambda j: j["rates"][to]),
        ("https://open.er-api.com/v6/latest/" + frm,
         lambda j: j["rates"][to]),
    ):
        try:
            params = {"base": frm, "symbols": to} if "frankfurter" in url else None
            j = httpx.get(url, params=params, timeout=8).json()
            rate = float(parse(j))
            _FX_CACHE[key] = (rate, time.time() + 3600)
            return rate
        except Exception as exc:  # noqa: BLE001
            log(f"calc: câmbio {url.split('/')[2]} falhou ({exc})")
    return None


def convert(t: str) -> str | None:
    if not re.search(r"\b(converte\w*|quantos?|quantas?|em|pra|para|vale\w*)\b", t):
        return None
    t = _words_to_num(t)
    num = re.search(r"(\d+(?:[.,]\d+)?)", t)
    if not num:
        return None
    val = float(num.group(1).replace(",", "."))

    # temperatura
    if re.search(r"\b(celsius|fahrenheit|kelvin|graus?)\b", t):
        has_f = "fahrenheit" in t
        has_c = "celsius" in t
        has_k = "kelvin" in t
        if has_f and ("celsius" in t or "para c" in t or "em c" in t or not has_k):
            c = (val - 32) * 5 / 9
            return f"{_fmt(round(c, 1))} graus Celsius, senhor."
        if has_c and (has_f or "para f" in t or "em f" in t):
            f = val * 9 / 5 + 32
            return f"{_fmt(round(f, 1))} graus Fahrenheit, senhor."
        if has_c and has_k:
            return f"{_fmt(round(val + 273.15, 2))} Kelvin, senhor."
        if has_k:
            return f"{_fmt(round(val - 273.15, 2))} graus Celsius, senhor."

    # moeda — a que está junto do número é a origem; o alvo vem depois
    hits = sorted(((t.index(w), _CUR[w]) for w in _CUR if re.search(rf"\b{re.escape(w)}\b", t)),
                  key=lambda x: x[0])
    # remove códigos repetidos mantendo a 1ª posição
    seen, cur_seq = set(), []
    for pos, code in hits:
        if code not in seen:
            seen.add(code)
            cur_seq.append((pos, code))
    if cur_seq:
        npos = num.start()
        frm = min(cur_seq, key=lambda x: abs(x[0] - npos))[1]
        rest = [c for _, c in cur_seq if c != frm]
        to = rest[0] if rest else ("BRL" if frm != "BRL" else "USD")
        rate = _fx(frm, to)
        if rate:
            return (f"{_fmt(val)} {_CUR_NAME[frm]} são {_fmt(round(val * rate, 2))} "
                    f"{_CUR_NAME[to]}, senhor.")
        return "Não consegui a cotação agora, senhor."

    # comprimento / massa — a unidade GRUDADA no número é a origem;
    # o alvo vem depois de "em/pra/para/quantos/quantas/vale".
    for table, names in ((_LEN, _LEN_NAME), (_MASS, _MASS_NAME)):
        units = sorted((w for w in table if re.search(rf"\b{w}\b", t)),
                       key=lambda w: t.index(w))
        if len(units) < 2:
            continue
        npos = num.start()
        # origem = unidade mais próxima do número (à direita dele, de preferência)
        after = [w for w in units if t.index(w) > npos]
        src = min(after or units, key=lambda w: abs(t.index(w) - npos))
        tgt_zone = re.split(r"\b(?:em|pra|para|quantos|quantas|vale\w*|da|equivale)\b", t)
        dst = next((w for w in reversed(units)
                    if w != src and table[w] != table[src]), None)
        if not dst:
            dst = next((w for w in units if w != src), src)
        base = val * table[src]
        out = base / table[dst]
        return f"{_fmt(val)} {_pretty(src)} são {_fmt(round(out, 4))} {_pretty(dst)}, senhor."
    return None


def _pretty(u: str) -> str:
    return {"pe": "pés", "pes": "pés", "quilometro": "quilômetros",
            "quilometros": "quilômetros", "kilometros": "quilômetros",
            "milimetro": "milímetros", "milimetros": "milímetros",
            "centimetro": "centímetros", "centimetros": "centímetros",
            "onca": "onças", "oncas": "onças", "metro": "metros",
            "quilo": "quilos", "grama": "gramas", "milha": "milhas",
            "libra": "libras", "polegada": "polegadas", "jarda": "jardas"}.get(u, u)


def handle(t: str) -> str | None:
    return convert(t) or calc(t)
