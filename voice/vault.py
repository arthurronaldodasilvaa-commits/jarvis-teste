#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
vault.py — o "Segundo Cérebro" do Jarvis (3º modo do app).

Um vault de estudo = uma pasta de arquivos .md + .canvas, 100% compatível com o
Obsidian. O senhor edita lá; o Jarvis:
  - indexa as notas, parseia os [[links]] e as #tags
  - CLASSIFICA cada nota (matéria / tópico / ideia / questão / nota) — heurística
    primeiro, LLM só no caso ambíguo, com cache
  - escreve  jarvis-app/brain_graph.json  (o app desenha a "teia" a partir dele)
  - cria / liga / apaga células de "quadro" (.canvas) por voz

Config em  config.toml -> [brain] .
Nada aqui bloqueia o daemon: tudo roda numa thread e loga+segue em erro.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
from difflib import SequenceMatcher
from pathlib import Path

from common import HERE, _atomic_write, log, norm, write_app_state

SEED = HERE / "vault_seed"
GRAPH_OUT = HERE.parent / "jarvis-app" / "brain_graph.json"

_TYPES = ("materia", "topico", "ideia", "questao", "quadro", "nota")
_LINK_RE = re.compile(r"\[\[([^\]|#^]+)")          # [[Nota]] / [[Nota|alias]] / [[Nota#sec]]
_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-zÀ-ÿ0-9_/-]{2,})")
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)

_state: dict = {"dir": None, "msum": -1, "notes": {}, "rev": 0}
_lock = threading.Lock()


# --------------------------------------------------------------------------- dirs
def vault_dir(cfg: dict) -> Path:
    d = str((cfg.get("brain", {}) or {}).get("vault_dir", "")).strip()
    if d:
        return Path(os.path.expandvars(os.path.expanduser(d)))
    return Path.home() / "Documents" / "Jarvis Vault"


def bootstrap(cfg: dict) -> Path:
    """Cria o vault a partir da semente no 1º boot. Idempotente."""
    vd = vault_dir(cfg)
    try:
        if not vd.exists():
            vd.mkdir(parents=True, exist_ok=True)
            if SEED.is_dir():
                for src in SEED.rglob("*"):
                    if src.is_dir() or src.name.startswith("."):
                        continue
                    dst = vd / src.relative_to(SEED)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
            log(f"vault: criado em {vd}")
        obs = vd / ".obsidian"
        obs.mkdir(exist_ok=True)
        appjson = obs / "app.json"
        if not appjson.is_file():
            appjson.write_text(json.dumps(
                {"newFileLocation": "current", "attachmentFolderPath": "Anexos",
                 "alwaysUpdateLinks": True}, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log(f"vault bootstrap: {exc}")
    return vd


# ------------------------------------------------------------------------- parse
def _title(p: Path) -> str:
    return p.stem


def _parse_md(p: Path) -> dict:
    try:
        raw = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    fm: dict = {}
    m = _FM_RE.match(raw)
    body = raw
    if m:
        body = raw[m.end():]
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip().lower()] = v.strip().strip("'\"")
    links = [norm(x) for x in _LINK_RE.findall(body)]
    tags = [t.lower() for t in _TAG_RE.findall(body)]
    if fm.get("tags"):
        tags += [t.strip().lower() for t in re.split(r"[,\s]+", fm["tags"]) if t.strip()]
    return {"fm": fm, "body": body, "links": links, "tags": sorted(set(tags)),
            "excerpt": re.sub(r"\s+", " ", re.sub(r"[#>*_`\[\]]", "", body))[:280].strip()}


def _parse_canvas(p: Path) -> dict:
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, ValueError):
        data = {}
    links = []
    for n in data.get("nodes", []):
        if n.get("type") == "file" and n.get("file"):
            links.append(norm(Path(n["file"]).stem))
    return {"fm": {}, "body": "", "links": links, "tags": [],
            "excerpt": f"{len(data.get('nodes', []))} células", "cells": len(data.get("nodes", []))}


# ---------------------------------------------------------------------- classify
def _heuristic(rec: dict, title: str, rel: str, inbound: int) -> str | None:
    fm_t = norm(rec.get("fm", {}).get("tipo", ""))
    if fm_t in _TYPES:
        return fm_t
    if rec.get("ext") == ".canvas":
        return "quadro"
    tl, body = norm(title), rec.get("body", "")
    tags = rec.get("tags", [])
    if "ideia" in tags or "insight" in tags or tl.startswith("ideia"):
        return "ideia"
    q_marks = body.count("?")
    if (tl.startswith("questa") or tl.startswith("q ") or "questoes" in tl
            or "questões" in title.lower()
            or (q_marks >= 3 and re.search(r"^\s*[a-e]\)", body, re.M))):
        return "questao"
    depth = rel.count("/") + rel.count("\\")
    if depth == 0 and inbound >= 2:
        return "materia"
    if depth >= 1 and len(body) < 1200:
        return "topico"
    return None


def _llm_classify(title: str, excerpt: str, brain) -> str:
    try:
        out = brain._post(
            [{"role": "system",
              "content": "Classifique a nota de estudo em UMA palavra: materia, topico, "
                         "ideia, questao ou nota. Só a palavra."},
             {"role": "user", "content": f"Título: {title}\nTrecho: {excerpt}"}],
            8, 0.0).strip().lower()
        out = re.sub(r"[^a-z]", "", out)
        return out if out in _TYPES else "nota"
    except Exception:  # noqa: BLE001
        return "nota"


# ------------------------------------------------------------------------ reindex
def _scan(vd: Path) -> list[Path]:
    return [p for p in vd.rglob("*")
            if p.suffix.lower() in (".md", ".canvas")
            and ".obsidian" not in p.parts and not p.name.startswith(".")][:800]


def reindex(cfg: dict, brain, force: bool = False) -> int:
    vd = vault_dir(cfg)
    if not vd.is_dir():
        return -1
    files = _scan(vd)
    msum = sum(int(p.stat().st_mtime) for p in files) + len(files)
    with _lock:
        if not force and _state["dir"] == str(vd) and _state["msum"] == msum and _state["notes"]:
            return len(_state["notes"])
        prev = _state["notes"] if _state["dir"] == str(vd) else {}

        recs: dict = {}
        for p in files:
            rel = str(p.relative_to(vd))
            nid = norm(p.stem)
            parsed = _parse_canvas(p) if p.suffix.lower() == ".canvas" else _parse_md(p)
            parsed["ext"] = p.suffix.lower()
            recs[nid] = {"id": nid, "title": _title(p), "rel": rel,
                         "path": str(p), "mtime": int(p.stat().st_mtime), **parsed}

        # arestas: quantos apontam PRA cada nota (pro heurístico de "matéria")
        inbound: dict = {k: 0 for k in recs}
        for r in recs.values():
            for l in r["links"]:
                if l in inbound:
                    inbound[l] += 1

        for nid, r in recs.items():
            old = prev.get(nid)
            if old and old.get("mtime") == r["mtime"] and old.get("type"):
                r["type"] = old["type"]
                continue
            t = _heuristic(r, r["title"], r["rel"], inbound.get(nid, 0))
            if not t:
                t = _llm_classify(r["title"], r.get("excerpt", ""), brain)
            r["type"] = t
            if (cfg.get("brain", {}).get("write_type_frontmatter", True)
                    and r["ext"] == ".md" and not r.get("fm", {}).get("tipo")):
                _write_type_fm(Path(r["path"]), t)

        _state.update(dir=str(vd), msum=msum, notes=recs, rev=_state["rev"] + 1)

    _write_graph(vd)
    return len(recs)


def _write_type_fm(p: Path, tipo: str) -> None:
    try:
        raw = p.read_text(encoding="utf-8", errors="ignore")
        m = _FM_RE.match(raw)
        if m:
            new = raw[:m.start()] + m.group(0).rstrip()[:-3].rstrip() \
                + f"\ntipo: {tipo}\n---\n" + raw[m.end():]
        else:
            new = f"---\ntipo: {tipo}\n---\n\n" + raw
        _atomic_write(p, new)
    except Exception as exc:  # noqa: BLE001
        log(f"vault: frontmatter {p.name} ({exc})")


def _write_graph(vd: Path) -> None:
    notes = _state["notes"]
    out = {"generated": time.time(), "vault": str(vd), "rev": _state["rev"], "notes": []}
    for r in notes.values():
        out["notes"].append({
            "id": r["id"], "title": r["title"], "type": r.get("type", "nota"),
            "rel": r["rel"], "tags": r.get("tags", []), "cells": r.get("cells", 0),
            "excerpt": r.get("excerpt", ""),
            "links": sorted({l for l in r["links"] if l in notes and l != r["id"]}),
        })
    _atomic_write(GRAPH_OUT, json.dumps(out, ensure_ascii=False))
    write_app_state(brain={"graph_rev": _state["rev"]})


# -------------------------------------------------------------------------- watch
def watch(cfg: dict, brain) -> None:
    poll = max(2, int((cfg.get("brain", {}) or {}).get("poll_seconds", 5)))
    bootstrap(cfg)
    try:
        n = reindex(cfg, brain, force=True)
        log(f"vault: {n} notas indexadas ({vault_dir(cfg)})")
    except Exception as exc:  # noqa: BLE001
        log(f"vault reindex inicial: {exc}")
    while True:
        time.sleep(poll)
        try:
            reindex(cfg, brain)
        except Exception as exc:  # noqa: BLE001
            log(f"vault watch: {exc}")


# ------------------------------------------------------------------------ lookup
def resolve(query: str) -> dict | None:
    """Nota/quadro cujo título mais casa com o texto falado."""
    q = norm(query)
    if not q:
        return None
    best, score = None, 0.0
    for r in _state["notes"].values():
        t = norm(r["title"])
        s = 1.0 if q == t else (0.9 if q in t or t in q else
                                SequenceMatcher(None, q, t).ratio())
        if s > score:
            best, score = r, s
    return best if score >= 0.55 else None


def note_text(rec: dict) -> str:
    try:
        return Path(rec["path"]).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def snapshot() -> list[dict]:
    return list(_state["notes"].values())
