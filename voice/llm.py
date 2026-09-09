#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
llm.py — abstração de provedor de LLM (ideia do `kosong`, do kimi-cli).

O `Brain` não fala mais direto com o Ollama: fala com um Provider. Assim dá pra
trocar o backend sem tocar no resto do Jarvis, e ter fallback.

Provedores:
  ollama   (padrão)  — /api/chat, 100% local. É o que sempre foi.
  openai             — /v1/chat/completions. Serve LM Studio, llama.cpp server,
                       vLLM, OpenRouter, Groq… qualquer coisa compatível OpenAI.
  anthropic          — API da Anthropic (precisa de chave; é o "escape" pra um
                       modelo grande quando o local não dá conta).

config.toml:
  [assistant]
  provider = "ollama"                 # ollama | openai | anthropic
  ollama_url = "http://localhost:11434"
  model = "qwen2.5:3b"
  fallback_provider = ""              # ex "openai" — usado se o principal falhar
  # openai / compatível:
  openai_url = "http://localhost:1234/v1"
  openai_model = "qwen2.5-7b-instruct"
  openai_api_key = ""                 # de preferência em secrets.toml
  # anthropic:
  anthropic_model = "claude-3-5-haiku-latest"
  anthropic_api_key = ""              # de preferência em secrets.toml

Tudo é fail-safe: erro de provedor vira exceção que o Brain já trata, e se tiver
fallback configurado ele tenta o fallback antes de desistir.
"""
from __future__ import annotations

import re

from common import log

_THINK = re.compile(r"<think>.*?</think>", re.S)


def _clean(msg: str) -> str:
    return _THINK.sub("", msg or "").strip()


class OllamaProvider:
    name = "ollama"

    def __init__(self, a: dict):
        import httpx
        self._httpx = httpx
        self.url = a.get("ollama_url", "http://localhost:11434").rstrip("/") + "/api/chat"
        self.model = a["model"]
        self.keep_alive = a.get("keep_alive", "1h")

    def chat(self, messages, num_predict: int, temperature: float = 0.4,
             timeout: float = 90) -> str:
        r = self._httpx.post(self.url, timeout=timeout, json={
            "model": self.model, "messages": messages, "stream": False,
            "think": False, "keep_alive": self.keep_alive,
            "options": {"temperature": temperature, "num_predict": num_predict},
        })
        r.raise_for_status()
        return _clean(r.json().get("message", {}).get("content", ""))

    def ping(self, timeout: float = 30) -> None:
        self._httpx.post(self.url, timeout=timeout, json={
            "model": self.model, "messages": [{"role": "user", "content": "."}],
            "stream": False, "think": False, "keep_alive": self.keep_alive,
            "options": {"num_predict": 1},
        })


class OpenAICompatProvider:
    name = "openai"

    def __init__(self, a: dict):
        import httpx
        self._httpx = httpx
        self.url = a.get("openai_url", "http://localhost:1234/v1").rstrip("/") + "/chat/completions"
        self.model = a.get("openai_model") or a["model"]
        self.key = a.get("openai_api_key", "")

    def chat(self, messages, num_predict: int, temperature: float = 0.4,
             timeout: float = 90) -> str:
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        r = self._httpx.post(self.url, timeout=timeout, headers=headers, json={
            "model": self.model, "messages": messages,
            "temperature": temperature, "max_tokens": max(16, num_predict),
            "stream": False,
        })
        r.raise_for_status()
        return _clean(r.json()["choices"][0]["message"]["content"])

    def ping(self, timeout: float = 30) -> None:
        self.chat([{"role": "user", "content": "."}], 1, timeout=timeout)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, a: dict):
        import httpx
        self._httpx = httpx
        self.url = a.get("anthropic_url", "https://api.anthropic.com/v1/messages")
        self.model = a.get("anthropic_model", "claude-3-5-haiku-latest")
        self.key = a.get("anthropic_api_key", "")
        if not self.key:
            raise RuntimeError("anthropic_api_key vazio")

    def chat(self, messages, num_predict: int, temperature: float = 0.4,
             timeout: float = 90) -> str:
        system = " ".join(m["content"] for m in messages if m["role"] == "system")
        conv = [m for m in messages if m["role"] in ("user", "assistant")]
        r = self._httpx.post(self.url, timeout=timeout, headers={
            "x-api-key": self.key, "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }, json={
            "model": self.model, "system": system, "messages": conv,
            "max_tokens": max(16, num_predict), "temperature": temperature,
        })
        r.raise_for_status()
        parts = r.json().get("content", [])
        return _clean("".join(p.get("text", "") for p in parts))

    def ping(self, timeout: float = 30) -> None:
        self.chat([{"role": "user", "content": "."}], 1, timeout=timeout)


_REGISTRY = {
    "ollama": OllamaProvider,
    "openai": OpenAICompatProvider,
    "openai_compat": OpenAICompatProvider,
    "anthropic": AnthropicProvider,
}


def make_provider(a: dict, which: str | None = None):
    which = (which or a.get("provider") or "ollama").strip().lower()
    cls = _REGISTRY.get(which)
    if not cls:
        log(f"llm: provedor {which!r} desconhecido — usando ollama")
        cls = OllamaProvider
    return cls(a)


class Router:
    """Um provedor + (opcional) fallback. É isso que o Brain usa."""

    def __init__(self, a: dict):
        self.primary = make_provider(a)
        self.model = getattr(self.primary, "model", a.get("model", "?"))
        self.fallback = None
        fb = (a.get("fallback_provider") or "").strip().lower()
        if fb and fb != self.primary.name:
            try:
                self.fallback = make_provider(a, fb)
            except Exception as exc:  # noqa: BLE001
                log(f"llm: fallback {fb!r} não subiu ({exc})")
        log(f"llm: provedor '{self.primary.name}' ({self.model})"
            + (f" + fallback '{self.fallback.name}'" if self.fallback else ""))

    def chat(self, messages, num_predict: int, temperature: float = 0.4,
             timeout: float = 90) -> str:
        try:
            return self.primary.chat(messages, num_predict, temperature, timeout)
        except Exception as exc:  # noqa: BLE001
            if not self.fallback:
                raise
            log(f"llm: primário falhou ({exc}) — tentando fallback '{self.fallback.name}'")
            return self.fallback.chat(messages, num_predict, temperature, timeout)

    def ping(self, timeout: float = 30) -> None:
        self.primary.ping(timeout)
