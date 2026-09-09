#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
media.py — "que música é essa?" e controle fino via a sessão de mídia do Windows.
Funciona pra qualquer player (Spotify, YouTube no navegador, etc.).
"""
from __future__ import annotations

from common import log


def _session():
    import asyncio

    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as Mgr,
    )

    async def go():
        mgr = await Mgr.request_async()
        s = mgr.get_current_session()
        if not s:
            return None
        info = await s.try_get_media_properties_async()
        tl = s.get_timeline_properties()
        return s, {
            "title": (info.title or "").strip(),
            "artist": (info.artist or "").strip(),
            "album": (info.album_title or "").strip(),
            "pos": tl.position.total_seconds() if tl.position else 0.0,
            "dur": tl.end_time.total_seconds() if tl.end_time else 0.0,
        }

    return asyncio.new_event_loop().run_until_complete(go())


def now_playing() -> str:
    try:
        r = _session()
    except Exception as exc:  # noqa: BLE001
        log(f"media: {exc}")
        return "Não consegui ver o que está tocando, senhor."
    if not r or not r[1]["title"]:
        return "Não tem nada tocando, senhor."
    d = r[1]
    if d["artist"]:
        return f"{d['title']}, de {d['artist']}, senhor."
    return f"{d['title']}, senhor."


def _do(coro_name: str, *args) -> bool:
    try:
        import asyncio
        r = _session()
        if not r:
            return False
        s = r[0]
        fn = getattr(s, coro_name)
        asyncio.new_event_loop().run_until_complete(fn(*args) if args else fn())
        return True
    except Exception as exc:  # noqa: BLE001
        log(f"media {coro_name}: {exc}")
        return False


def restart_track() -> bool:
    return _do("try_change_playback_position_async", 0)


def seek(delta_s: float) -> bool:
    try:
        r = _session()
        if not r:
            return False
        s, d = r
        import asyncio
        target = max(0.0, d["pos"] + delta_s)
        asyncio.new_event_loop().run_until_complete(
            s.try_change_playback_position_async(int(target * 1e7)))  # 100-ns ticks
        return True
    except Exception as exc:  # noqa: BLE001
        log(f"media seek: {exc}")
        return False
