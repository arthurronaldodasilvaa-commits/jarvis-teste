#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
materials.py — o Jarvis responde a partir dos SEUS materiais de estudo (local).

Config:  [study] materials_dir = "E:/Estudos"

  "o que meu resumo diz sobre fotossíntese"   -> acha os trechos e responde
  "resume o que eu tenho sobre a Revolução Francesa"
  "atualiza meus materiais"                    -> reindexar

Lê .txt / .md / .pdf. Sem embeddings pesados: busca por termos (BM25-lite).
Índice em voice/materials_index.json (só reindexa o que mudou).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from common import HERE, log, norm

IDX = HERE / "materials_index.json"
_STOP = set("de a o e que do da em um para com nao os no se na por mais as dos como "
            "mas ao ele das seu sua ou quando muito ha nos ja esta eu tambem so pelo "
            "pela ate isso ela entre depois sem mesmo aos seus quem nas me esse eles "
            "voce essa num nem suas meu as minha numa pelos elas qual".split())

_cache: dict = {"dir": None, "mtime_sum": -1, "chunks": [], "df": {}, "N": 0}


def _mats_dir(cfg: dict) -> Path | None:
    d = (cfg.get("study", {}) or {}).get("materials_dir", "").strip()
    if not d:
        return None
    p = Path(d)
    return p if p.is_dir() else None


def _toks(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-zà-ÿ0-9]{3,}", norm(text)) if w not in _STOP]


def _read_file(p: Path) -> list[tuple[int, str]]:
    """Devolve [(pagina, texto)]. pagina=0 pra txt/md."""
    try:
        if p.suffix.lower() in (".txt", ".md"):
            return [(0, p.read_text(encoding="utf-8", errors="ignore"))]
        if p.suffix.lower() == ".pdf":
            import pypdf
            out = []
            r = pypdf.PdfReader(str(p))
            for i, pg in enumerate(r.pages[:200], 1):
                t = pg.extract_text() or ""
                if t.strip():
                    out.append((i, t))
            return out
    except Exception as exc:  # noqa: BLE001
        log(f"materials: {p.name} falhou ({exc})")
    return []


def _split(text: str) -> list[str]:
    text = re.sub(r"\s+\n", "\n", text)
    blocos = re.split(r"\n\s*\n|\n(?=#|[A-ZÀ-Ú0-9])", text)
    # junta títulos/linhas curtas ao bloco seguinte (senão "# Revolução Francesa" some)
    merged, buf = [], ""
    for raw in blocos:
        raw = re.sub(r"\s+", " ", raw).strip().lstrip("#").strip()
        if not raw:
            continue
        if len(raw) < 45:
            buf = (buf + " " + raw).strip()
        else:
            merged.append((buf + " " + raw).strip() if buf else raw)
            buf = ""
    if buf:
        merged.append(buf)
    out = []
    for b in merged:
        if len(b) < 25:
            continue
        while len(b) > 700:
            corte = b.rfind(". ", 300, 700)
            corte = corte + 1 if corte > 0 else 700
            out.append(b[:corte].strip())
            b = b[corte:].strip()
        if b:
            out.append(b)
    return out


def index(cfg: dict, force: bool = False) -> int:
    d = _mats_dir(cfg)
    if not d:
        return -1
    files = [p for p in d.rglob("*") if p.suffix.lower() in (".txt", ".md", ".pdf")][:400]
    msum = sum(int(p.stat().st_mtime) for p in files) + len(files)
    if not force and _cache["dir"] == str(d) and _cache["mtime_sum"] == msum and _cache["chunks"]:
        return len(_cache["chunks"])
    # tenta cache em disco
    if not force:
        try:
            saved = json.loads(IDX.read_text(encoding="utf-8"))
            if saved.get("dir") == str(d) and saved.get("msum") == msum:
                _cache.update(dir=str(d), mtime_sum=msum, chunks=saved["chunks"],
                              df=saved["df"], N=len(saved["chunks"]))
                return _cache["N"]
        except Exception:  # noqa: BLE001
            pass

    chunks, df = [], {}
    for p in files:
        for page, raw in _read_file(p):
            for frag in _split(raw):
                tk = _toks(frag)
                if len(tk) < 4:
                    continue
                chunks.append({"f": p.name, "pg": page, "t": frag, "tk": tk})
                for w in set(tk):
                    df[w] = df.get(w, 0) + 1
    _cache.update(dir=str(d), mtime_sum=msum, chunks=chunks, df=df, N=len(chunks))
    try:
        IDX.write_text(json.dumps({"dir": str(d), "msum": msum, "chunks": chunks, "df": df},
                                  ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    log(f"materials: {len(chunks)} trechos de {len(files)} arquivo(s)")
    return len(chunks)


def search(cfg: dict, query: str, k: int = 3) -> list[dict]:
    n = index(cfg)
    if n <= 0:
        return []
    qt = _toks(query)
    if not qt:
        return []
    N = _cache["N"]
    df = _cache["df"]
    scored = []
    for c in _cache["chunks"]:
        tset = c["tk"]
        L = len(tset) or 1
        s = 0.0
        for w in qt:
            tf = tset.count(w)
            if not tf:
                continue
            idf = math.log(1 + N / (1 + df.get(w, 0)))
            s += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * L / 120))
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:k]]


def ask(cfg: dict, query: str, brain) -> str | None:
    hits = search(cfg, query, 3)
    if not hits:
        n = index(cfg)
        if n == -1:
            return ("Não sei onde estão seus materiais, senhor. Ponha a pasta em "
                    "config: [study] materials_dir.")
        return "Não achei nada sobre isso nos seus materiais, senhor."
    contexto = "\n\n".join(f"[{h['f']}{', pág ' + str(h['pg']) if h['pg'] else ''}]\n{h['t']}"
                           for h in hits)
    fontes = ", ".join(sorted({h["f"] for h in hits}))
    if brain is None:
        return f"Do seu material ({fontes}), senhor: {hits[0]['t'][:280]}"
    try:
        resp = brain._post(
            [{"role": "system", "content":
              "Responda a pergunta do usuário SÓ com base nos trechos fornecidos. "
              "Se os trechos não responderem, diga que não achou. Curto, português do "
              "Brasil, sem 'segundo o texto'."},
             {"role": "user", "content": f"TRECHOS:\n{contexto}\n\nPERGUNTA: {query}"}],
            200, temperature=0.2).strip()
    except Exception as exc:  # noqa: BLE001
        log(f"materials/ask LLM: {exc}")
        return f"Do seu material ({fontes}), senhor: {hits[0]['t'][:280]}"
    return f"{resp} (do seu material: {fontes}, senhor)"


def resume(cfg: dict, topico: str, brain) -> str | None:
    hits = search(cfg, topico, 4)
    if not hits:
        return "Não achei nada sobre isso nos seus materiais, senhor."
    contexto = "\n\n".join(h["t"] for h in hits)
    fontes = ", ".join(sorted({h["f"] for h in hits}))
    if brain is None:
        return contexto[:400]
    try:
        return brain._post(
            [{"role": "system", "content": "Resuma em 3-4 frases o que os trechos dizem "
              "sobre o tema. Português do Brasil, direto."},
             {"role": "user", "content": f"TEMA: {topico}\n\nTRECHOS:\n{contexto}"}],
            220, temperature=0.3).strip() + f" (de {fontes}, senhor)"
    except Exception as exc:  # noqa: BLE001
        log(f"materials/resume: {exc}")
        return "Não consegui resumir agora, senhor."


# --------------------------------------------------------------------------
def handle(raw: str, cfg: dict, brain) -> "object | None":
    import skills
    R = skills.Result
    t = norm(raw)

    if re.search(r"\b(atualiz\w+|reindex\w+|recarreg\w+|le de novo)\s+(os\s+|meus\s+)?"
                 r"(materiais|resumos?|estudos?|apostilas?|pdfs?)\b|\bindexar? (os )?materiais\b", t):
        n = index(cfg, force=True)
        if n == -1:
            return R(speak="Configure a pasta primeiro, senhor: [study] materials_dir no config.")
        return R(speak=f"Pronto, senhor. {n} trechos indexados dos seus materiais.")

    m = re.search(r"\b(o que|que|onde)\b.*\b(meu|meus|minha|minhas|nos?\s+meus?)\s+"
                  r"(resumo|resumos|material|materiais|anota\w+|apostila|caderno|pdf|estudo)s?\b"
                  r".*\b(diz\w*|fala\w*|tem|explica\w*|sobre|a respeito)\b\s*(.*)", t)
    if not m:
        m = re.search(r"\bconsulta\w*\s+(?:nos?\s+)?meus?\s+materiais?\s+(?:sobre\s+)?(.+)", t)
        if m:
            return R(speak=ask(cfg, m.group(1), brain) or "Nada encontrado, senhor.")
    if m:
        alvo = (m.group(m.lastindex) or raw).strip(" ?.")
        alvo = re.sub(r"^(sobre|a respeito de|de|do|da)\s+", "", alvo)
        if len(alvo) < 3:
            alvo = raw
        return R(speak=ask(cfg, alvo, brain) or "Nada encontrado, senhor.")

    mr = re.search(r"\bresum\w+\s+(?:o que (?:eu )?(?:tenho|sei)\s+)?(?:sobre|de|do|da|dos|das)?\s*"
                   r"(.+?)(?:\s+(?:nos?\s+)?meus?\s+(?:materiais?|resumos?|anota\w+))?$", t)
    if mr and re.search(r"\bmeus?\s+(materiais?|resumos?|anota\w+|apostila|caderno)\b", t):
        return R(speak=resume(cfg, mr.group(1).strip(), brain) or "Nada, senhor.")

    return None
