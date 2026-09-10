#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
face.py — reação ao reconhecimento facial do app.

O app (ui/face.js) reconhece quem está na câmera e grava jarvis-app/face.json:
  {"name": "arthur" | "desconhecido" | "__enrolled__" | "", "n": <ms>}

Aqui um thread do daemon vê isso e:
  - cumprimenta pelo nome (1x por aparição)
  - se o rosto for de um PERFIL diferente do ativo -> troca de perfil
  - se for "desconhecido" -> avisa no HUD (1x)
  - "__enrolled__" -> confirma o cadastro em voz

Cadastro: "Jarvis, aprende meu rosto" -> write_control(face_enroll=<perfil ativo>).
"""
from __future__ import annotations

import json
import time

from common import _SHARED, log, norm, push_note

FILE = _SHARED / "face.json"


def _profiles() -> set[str]:
    try:
        import skills
        return {p["name"].lower() for p in skills.list_profiles()}
    except Exception:                             # noqa: BLE001
        return set()


def watch(mouth, cfg: dict, active_profile: str, relaunch) -> None:
    """Thread: fica de olho no face.json."""
    time.sleep(10)
    last_n = 0
    greeted: set[str] = set()
    warned_unknown = 0.0
    gone_since = time.time()
    switch_cooldown = 0.0
    addr = cfg.get("assistant", {}).get("address", "senhor")
    profiles = _profiles()

    while True:
        time.sleep(2.5)
        try:
            if not FILE.is_file():
                continue
            d = json.loads(FILE.read_text(encoding="utf-8"))
            n = int(d.get("n", 0))
            if n <= last_n:
                # ninguém há um tempão -> esquece quem já cumprimentou
                if time.time() - gone_since > 90 and greeted:
                    greeted.clear()
                continue
            last_n = n
            name = str(d.get("name", "")).strip().lower()

            if not name:                          # rosto sumiu / câmera fechou
                gone_since = time.time()
                continue
            gone_since = time.time()

            if name.startswith("__enrolled__"):
                _nm = name.split("|", 1)[1].strip() if "|" in name else ""
                quem = _nm.split()[0].capitalize() if _nm else addr
                mouth.say(f"Pronto, {quem}. Aprendi o seu rosto. "
                          "Agora eu reconheço o senhor pela câmera.")
                continue

            if name == "desconhecido":
                if time.time() - warned_unknown > 120:
                    warned_unknown = time.time()
                    push_note("rosto não reconhecido na câmera", "info")
                continue

            # rosto conhecido
            if name not in greeted:
                greeted.add(name)
                nome_bonito = name.capitalize()
                mouth.say(f"Olá, {nome_bonito}.")

            # é um perfil diferente do ativo? troca.
            if (name in profiles and name != (active_profile or "").lower()
                    and time.time() - switch_cooldown > 60):
                switch_cooldown = time.time()
                try:
                    import skills
                    if skills._write_active_profile(name):
                        mouth.say(f"Reconheci o perfil {name.capitalize()}, {addr}. "
                                  "Trocando agora.")
                        time.sleep(1.0)
                        relaunch()
                except Exception as exc:          # noqa: BLE001
                    log(f"face: troca de perfil falhou ({exc})")
        except Exception as exc:                  # noqa: BLE001
            log(f"face watch: {exc}")


# --------------------------------------------------------------------------
# usado pelo skills.dispatch
# --------------------------------------------------------------------------
import re  # noqa: E402


def match_enroll(t: str) -> bool:
    return bool(re.search(r"\b(aprend[ae]|memoriz[ae]|decor[ae]|grav[ae]|guard[ae]|"
                          r"cadastr[ae]|registr[ae])\s+(o\s+)?(meu|o meu)\s+rosto\b|"
                          r"\besse\s+sou\s+eu\b|\bsou\s+eu\b.*\bcamera\b|"
                          r"\breconhece\s+meu\s+rosto\b", t))


def match_forget(t: str) -> bool:
    return bool(re.search(r"\b(esquec[ae]|apag[ae]|remov[ae])\s+(o\s+)?(meu\s+)?rosto\b", t))


def match_query(t: str) -> bool:
    return bool(re.search(r"\b(voce\s+me\s+reconhece|quem\s+(esta|ta)\s+(ai|na camera|te vendo)|"
                          r"sabe\s+quem\s+(eu\s+)?sou|me\s+reconhece)\b", t))


_NAME_STOP = {"o", "a", "e", "meu", "nome", "eh", "e", "me", "chamo", "chama", "chame",
              "de", "pode", "sou", "aqui", "senhor", "por", "favor", "que", "esse",
              "rosto", "esta", "falando", "quem", "voce"}


def clean_name(raw: str) -> str:
    """Extrai um nome do que a pessoa falou: 'Arthur', 'meu nome é Arthur',
    'pode me chamar de Arthur', 'aqui é o Arthur' -> 'arthur'."""
    s = norm(raw)
    s = re.sub(r".*\b(nome (eh|e)|chamar? de|me chamo|sou (o|a)?|aqui (eh|e)( o| a)?)\b", "", s).strip()
    toks = [w for w in s.split() if w not in _NAME_STOP and len(w) >= 2]
    toks = toks[:2]                        # nome + sobrenome no máximo
    nome = " ".join(toks).strip()
    nome = re.sub(r"[^a-z ]", "", nome).strip()
    return nome[:30]
