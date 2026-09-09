#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
hooks.py — ganchos de ciclo de vida do Jarvis (ideia tirada do kimi-cli).

Deixa o Senhor (ou o Robson) automatizar comportamento SEM escrever Python:
edita `voice/hooks.toml` e pronto.

Eventos:
  on_startup         o daemon subiu e está ouvindo
  on_wake            alguém chamou "Jarvis ..." (ou disse a frase de chegada)
  on_command         um comando foi entendido      (ctx.text = o comando)
  on_command_done    o comando terminou            (ctx.text, ctx.reply)
  on_error           deu erro ao executar um comando
  on_idle            ninguém fala há N segundos     (after_seconds obrigatório)
  on_reminder_due    um lembrete venceu             (ctx.text = o lembrete)
  on_profile_switch  trocou de perfil               (ctx.text = novo perfil)

Cada hook em hooks.toml é uma entrada de [[hooks]]:

  [[hooks]]
  event = "on_wake"
  when = "06:00-09:30"        # opcional — só dispara nessa janela
  matcher = "bom dia"         # opcional — regex no ctx.text (on_command/on_wake)
  after_seconds = 1800        # obrigatório só pro on_idle
  speak = "Bom dia, senhor."  # Jarvis fala isso
  then = "qual a previsão"    # …e despacha isso como se fosse um comando
  run = "nircmd.exe ..."      # …e/ou roda esse comando no shell (ctx vai por JSON no stdin)
  once_per_day = true         # opcional — no máx. 1x/dia

Política: fail-open. Hook que quebra é logado e ignorado, nunca derruba o Jarvis.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from datetime import datetime, date

from common import HERE, log

CNW = 0x08000000                                  # CREATE_NO_WINDOW

try:
    import tomllib
except ModuleNotFoundError:                       # py < 3.11
    import tomli as tomllib                        # type: ignore

FILE = HERE / "hooks.toml"

_EVENTS = {
    "on_startup", "on_wake", "on_command", "on_command_done",
    "on_error", "on_idle", "on_reminder_due", "on_profile_switch",
}
_MATCHED_EVENTS = ("on_command", "on_wake", "on_command_done")

_cache: dict = {"mtime": 0.0, "hooks": []}
_fired_today: dict[int, str] = {}                 # id(hook) -> "YYYY-MM-DD"
_lock = threading.Lock()


def _load() -> list[dict]:
    try:
        mt = FILE.stat().st_mtime
    except OSError:
        return []
    if mt == _cache["mtime"]:
        return _cache["hooks"]
    try:
        data = tomllib.loads(FILE.read_text(encoding="utf-8"))
        good = []
        for h in (data.get("hooks", []) or []):
            ev = str(h.get("event", "")).strip()
            if ev not in _EVENTS:
                log(f"hooks: evento desconhecido {ev!r} — ignorado")
                continue
            good.append(h)
        _cache.update(mtime=mt, hooks=good)
        log(f"hooks: {len(good)} carregado(s)")
    except Exception as exc:                      # noqa: BLE001
        log(f"hooks: hooks.toml inválido ({exc}) — ignorando")
        _cache.update(mtime=mt, hooks=[])
    return _cache["hooks"]


def _in_window(spec: str) -> bool:
    """'06:00-09:30' -> True se agora está na janela. Cruza meia-noite ok."""
    try:
        a, b = spec.split("-")
        now = datetime.now().time()
        ta = datetime.strptime(a.strip(), "%H:%M").time()
        tb = datetime.strptime(b.strip(), "%H:%M").time()
        return ta <= now <= tb if ta <= tb else (now >= ta or now <= tb)
    except Exception:                             # noqa: BLE001
        return True


def _matches(hook: dict, text: str) -> bool:
    pat = hook.get("matcher")
    if not pat:
        return True
    try:
        import re
        from common import norm
        return re.search(pat, norm(text)) is not None
    except Exception:                             # noqa: BLE001
        return True


def _run_shell(cmd: str, ctx: dict, timeout: float) -> None:
    try:
        subprocess.run(cmd, shell=True, timeout=timeout, creationflags=CNW,
                       input=json.dumps(ctx, ensure_ascii=False).encode("utf-8"),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:                      # noqa: BLE001
        log(f"hooks: run falhou ({exc})")


def _exec(h: dict, ctx: dict, speak, dispatch) -> None:
    try:
        if h.get("when") and not _in_window(str(h["when"])):
            return
        if ctx["event"] in _MATCHED_EVENTS and not _matches(h, ctx.get("text", "")):
            return
        if h.get("once_per_day"):
            today = date.today().isoformat()
            if _fired_today.get(id(h)) == today:
                return
            _fired_today[id(h)] = today
        log(f"hook: {ctx['event']}" + (f" ({h['matcher']})" if h.get("matcher") else ""))
        if h.get("speak") and speak:
            speak(str(h["speak"]))
        if h.get("run"):
            _run_shell(str(h["run"]), ctx, float(h.get("timeout", 15)))
        if h.get("then") and dispatch:
            dispatch(str(h["then"]))
    except Exception as exc:                      # noqa: BLE001
        log(f"hooks: hook de {ctx['event']} falhou ({exc}) — seguindo")


def fire(event: str, *, text: str = "", cfg: dict | None = None,
         speak=None, dispatch=None, extra: dict | None = None) -> None:
    """Dispara todos os hooks de `event`.

    speak(str)     -> como o Jarvis fala (ex: mouth.say)
    dispatch(str)  -> despacha um comando (ex: lambda p: skills.dispatch(...))
    """
    with _lock:
        hooks = [h for h in _load() if h.get("event") == event]
    if not hooks:
        return
    ctx = {"event": event, "text": text,
           "time": datetime.now().isoformat(timespec="seconds")}
    if extra:
        ctx.update(extra)
    for h in hooks:
        _exec(h, ctx, speak, dispatch)


# ---- on_idle: relógio que o daemon alimenta --------------------------------
_last_activity = time.monotonic()
_idle_done: set = set()


def mark_activity() -> None:
    """O daemon chama toda vez que ouve/responde algo."""
    global _last_activity
    _last_activity = time.monotonic()
    _idle_done.clear()


def check_idle(*, cfg: dict | None = None, speak=None, dispatch=None) -> None:
    """Chame periodicamente (branch de silêncio do loop principal)."""
    idle_hooks = [h for h in _load() if h.get("event") == "on_idle"]
    if not idle_hooks:
        return
    quiet = time.monotonic() - _last_activity
    ctx = {"event": "on_idle", "text": f"{int(quiet)}s",
           "time": datetime.now().isoformat(timespec="seconds")}
    for h in idle_hooks:
        secs = float(h.get("after_seconds", 0) or 0)
        if secs <= 0 or quiet < secs or id(h) in _idle_done:
            continue
        _idle_done.add(id(h))
        _exec(h, ctx, speak, dispatch)
