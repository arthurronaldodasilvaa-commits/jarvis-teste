#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
translate.py — tradução por voz.

  "traduz bom dia pra inglês"
  "como se diz obrigado em espanhol"
  "o que significa serendipity"     (assume inglês -> português)
"""
from __future__ import annotations

import re

from common import log

_LANGS = {
    "portugues": "pt", "portugues do brasil": "pt", "pt": "pt",
    "ingles": "en", "en": "en",
    "espanhol": "es", "castelhano": "es", "es": "es",
    "frances": "fr", "fr": "fr",
    "alemao": "de", "de": "de",
    "italiano": "it", "it": "it",
    "japones": "ja", "ja": "ja",
    "mandarim": "zh", "chines": "zh", "zh": "zh",
    "russo": "ru", "coreano": "ko", "holandes": "nl",
    "arabe": "ar", "latim": "la",
}
_LANG_NOME = {"pt": "português", "en": "inglês", "es": "espanhol", "fr": "francês",
              "de": "alemão", "it": "italiano", "ja": "japonês", "zh": "mandarim",
              "ru": "russo", "ko": "coreano", "nl": "holandês", "ar": "árabe", "la": "latim"}


def _mymemory(text: str, src: str, dst: str) -> str | None:
    import httpx
    try:
        r = httpx.get("https://api.mymemory.translated.net/get",
                      params={"q": text, "langpair": f"{src}|{dst}"}, timeout=8,
                      headers={"User-Agent": "JarvisVoice/1.0"})
        j = r.json()
        out = (j.get("responseData") or {}).get("translatedText", "")
        if out and "MYMEMORY WARNING" not in out.upper() and "INVALID" not in out.upper():
            return out.strip()
    except Exception as exc:  # noqa: BLE001
        log(f"translate: {exc}")
    return None


def handle(raw: str, brain=None) -> str | None:
    low = raw.strip().lower()
    m = re.search(r"\b(?:traduz(?:a|ir)?|traducao de|como (?:se )?(?:diz|fala)|"
                  r"como (?:e|que e) que (?:se )?(?:diz|fala))\b\s+(.+)", low)
    if not m:
        m2 = re.search(r"\bo que (?:significa|quer dizer)\s+(.+)", low)
        if m2 and re.search(r"[a-z]{3,}", m2.group(1)) and " " not in m2.group(1).strip():
            palavra = re.sub(r"[?.!]+$", "", m2.group(1)).strip()
            out = _mymemory(palavra, "en", "pt")
            if out and out.lower() != palavra.lower():
                return f"\"{palavra}\" em português é {out}, senhor."
        return None

    import unicodedata
    rest = m.group(1)
    flat = unicodedata.normalize("NFKD", rest).encode("ascii", "ignore").decode()
    dst = "en"
    md = re.search(r"\b(?:pra|para|pro|em|ao|no)\s+(?:o\s+|a\s+)?([a-z ]+?)(?:\s*[?.!,]|$)", flat)
    if md and md.group(1).strip() in _LANGS:
        dst = _LANGS[md.group(1).strip()]
        rest = rest[:md.start()].strip()
    src = "pt" if dst != "pt" else "en"
    frase = re.sub(r"^[\"']|[\"'?.!]+$", "", rest).strip()
    if not frase:
        return None

    out = None
    if brain is not None:
        try:
            out = brain._post(
                [{"role": "system", "content":
                  f"Você traduz. Traduza o texto do usuário para {_LANG_NOME.get(dst, dst)}. "
                  f"Responda APENAS com a tradução, nada mais."},
                 {"role": "user", "content": frase}], 60, temperature=0.1).strip()
            out = re.sub(r'^["\']|["\'.]+$', "", out).strip() or None
        except Exception:  # noqa: BLE001
            out = None
    if not out:
        out = _mymemory(frase, src, dst)
    if not out:
        return "Não consegui traduzir agora, senhor."
    return f"Em {_LANG_NOME.get(dst, dst)}: {out}, senhor."
