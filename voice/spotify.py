#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
spotify.py — tocar música de verdade.

Usa a busca pública do Spotify (client credentials, SEM login de usuário) pra
achar a faixa pelo nome e abre `spotify:track:<id>`, que toca no app já aberto.

Config em voice/config.toml:

    [spotify]
    client_id = "..."       # de https://developer.spotify.com/dashboard
    client_secret = "..."
    market = "BR"
    force_play = true        # manda um "play" se o Spotify já estava aberto
    wait_seconds = 3.5

Sem client_id/secret → cai no modo antigo (abre a busca, você clica).
"""

from __future__ import annotations

import base64
import os
import re
import subprocess
import time

from common import log, norm

_CNW = 0x08000000
_token = {"value": "", "exp": 0.0}


def _cfg(cfg: dict) -> dict:
    return cfg.get("spotify", {}) or {}


def configured(cfg: dict) -> bool:
    s = _cfg(cfg)
    return bool(s.get("client_id") and s.get("client_secret"))


def _get_token(cfg: dict):
    import httpx

    if _token["value"] and time.time() < _token["exp"] - 60:
        return _token["value"]
    s = _cfg(cfg)
    auth = base64.b64encode(f"{s['client_id']}:{s['client_secret']}".encode()).decode()
    r = httpx.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    r.raise_for_status()
    j = r.json()
    _token["value"] = j["access_token"]
    _token["exp"] = time.time() + int(j.get("expires_in", 3600))
    return _token["value"]


_STOP = {"do", "da", "de", "dos", "das", "no", "na", "e", "a", "o", "the",
         "musica", "música", "song", "por", "favor"}


def _fetch(query: str, cfg: dict, tok: str) -> list[dict]:
    import httpx

    r = httpx.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {tok}"},
        params={"q": query, "type": "track", "limit": 8,
                "market": _cfg(cfg).get("market", "BR")},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("tracks", {}).get("items", [])


def search_track(query: str, cfg: dict) -> tuple[str, str] | None:
    """Busca várias faixas e devolve a que MAIS combina com o que foi pedido."""
    tok = _get_token(cfg)
    items = _fetch(query, cfg, tok)
    if not items:
        # 2ª tentativa sem conectores ("333 do matue" -> "333 matue")
        alt = " ".join(w for w in norm(query).split() if w not in _STOP)
        if alt and alt != norm(query):
            items = _fetch(alt, cfg, tok)
    if not items:
        return None

    qwords = [w for w in norm(query).split() if w not in _STOP]

    def score(it: dict) -> tuple:
        hay = norm(it["name"] + " " + " ".join(a["name"] for a in it.get("artists", [])))
        hits = sum(1 for w in qwords if w and w in hay)
        return (hits, it.get("popularity", 0))

    it = max(items, key=score)
    who = ", ".join(a["name"] for a in it.get("artists", []))
    return it["uri"], f"{it['name']} — {who}"


def _running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/fi", "imagename eq Spotify.exe"],
            capture_output=True, text=True, timeout=10, creationflags=_CNW,
        ).stdout.lower()
        return "spotify.exe" in out
    except Exception:  # noqa: BLE001
        return False


def play_uri(uri: str, cfg: dict) -> None:
    """Abre spotify:track:<id> (ou playlist/album) e garante o play."""
    was = _running()
    os.startfile(uri)  # noqa: S606
    s = _cfg(cfg)
    if was and s.get("force_play", True):
        time.sleep(float(s.get("wait_seconds", 3.5)))
        import ctypes
        ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)       # VK_MEDIA_PLAY_PAUSE
        ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)


def _clean_query(q: str) -> str:
    q = q.strip().strip(".").strip()
    # tira preenchimento no fim que o Whisper cola quando a fala é cortada
    q = re.sub(r"[\s,]+(mas|entao|então|ai|aí|por favor|pra mim|agora|la|lá)\s*$", "", q, flags=re.I)
    # "3 3 3" / "3, 3, 3" -> "333" (números falados soltos)
    q = re.sub(r"\b(\d)[\s,]+(?=\d\b)", r"\1", q)
    return q.strip(" ,.").strip()


def play(query: str, cfg: dict) -> tuple[bool, str]:
    """Toca a música pelo nome. Retorna (ok, fala). Em caso de sucesso a fala
    fica vazia (toca calado), a menos que [spotify].announce = true."""
    from urllib.parse import quote_plus

    query = _clean_query(query)
    if not configured(cfg):
        os.startfile("spotify:search:" + quote_plus(query))  # noqa: S606
        return False, f"Abri a busca por {query}, senhor. Falta a chave do Spotify no secrets.toml."
    try:
        hit = search_track(query, cfg)
    except Exception as exc:  # noqa: BLE001
        os.startfile("spotify:search:" + quote_plus(query))  # noqa: S606
        return False, f"Não consegui buscar no Spotify agora, senhor. ({exc.__class__.__name__})"
    if not hit:
        log(f"Spotify: nada pra {query!r}")
        return False, f"Não achei {query} no Spotify, senhor."
    uri, label = hit
    log(f"Spotify: tocando {label}  (busca: {query!r})")
    play_uri(uri, cfg)
    fala = f"Tocando {label}, senhor." if _cfg(cfg).get("announce", False) else ""
    return True, fala
