#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
hud.py — alimenta o "cérebro" (jarvis-app) com dados de HUD via state.json:
  weather  -> "23° nublado  ↑23 ↓14"
  track    -> {title, artist, pos, dur, playing}   (sessão de mídia do Windows)
  sys      -> {cpu, ram, gpu}   (0..100)
Roda um thread só; o daemon chama hud.start(cfg).
"""
from __future__ import annotations

import re
import threading
import time

from common import log, write_app_state

_started = False


# ---------------------------------------------------------------- mídia
def _media_snapshot() -> dict | None:
    try:
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
            pb = s.get_playback_info()
            playing = int(getattr(pb, "playback_status", 0)) == 4
            pos = tl.position.total_seconds() if tl.position else 0.0
            dur = tl.end_time.total_seconds() if tl.end_time else 0.0
            title = (info.title or "").strip()
            if not title:
                return None
            return {"title": title, "artist": (info.artist or "").strip(),
                    "pos": round(pos, 1), "dur": round(dur, 1), "playing": playing}

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(go())
        finally:
            loop.close()                    # sem isto vaza um loop a cada 2 s
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- sistema
_nvml = {"ok": None}


def _gpu() -> tuple[float | None, float | None]:
    """(uso %, temperatura °C) da GPU 0, via NVML."""
    if _nvml["ok"] is False:
        return None, None
    try:
        import pynvml
        if _nvml["ok"] is None:
            pynvml.nvmlInit()
            _nvml["ok"] = True
            _nvml["h"] = pynvml.nvmlDeviceGetHandleByIndex(0)
        h = _nvml["h"]
        uso = float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
        try:
            temp = float(pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU))
        except Exception:  # noqa: BLE001
            temp = None
        return uso, temp
    except Exception:  # noqa: BLE001
        _nvml["ok"] = False
        return None, None


_cpu_temp = {"ok": None, "src": None}


def _cpu_temperature() -> float | None:
    """Temperatura da CPU. Tenta psutil, depois WMI (MSAcpi). Nem sempre dá no
    Windows sem admin — se não der, devolve None e para de tentar."""
    if _cpu_temp["ok"] is False:
        return None
    try:
        import psutil
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures() or {}
            for key in ("coretemp", "k10temp", "acpitz", "cpu_thermal"):
                if temps.get(key):
                    _cpu_temp["ok"] = True
                    return round(sum(x.current for x in temps[key]) / len(temps[key]), 1)
    except Exception:  # noqa: BLE001
        pass
    try:
        import subprocess
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
             "-ErrorAction SilentlyContinue | Select-Object -First 1 -Expand CurrentTemperature)"],
            capture_output=True, text=True, timeout=6, creationflags=0x08000000)
        v = (r.stdout or "").strip()
        if v.isdigit():
            _cpu_temp["ok"] = True
            return round(int(v) / 10 - 273.15, 1)
    except Exception:  # noqa: BLE001
        pass
    _cpu_temp["ok"] = False
    return None


def _sys_snapshot() -> dict:
    out = {}
    try:
        import psutil
        out["cpu"] = round(psutil.cpu_percent(interval=None))
        out["ram"] = round(psutil.virtual_memory().percent)
    except Exception:  # noqa: BLE001
        pass
    uso, temp = _gpu()
    if uso is not None:
        out["gpu"] = round(uso)
    if temp is not None:
        out["gpu_t"] = round(temp)
    ct = _cpu_temperature()
    if ct is not None:
        out["cpu_t"] = round(ct)
    return out


# ---------------------------------------------------------------- clima
def _weather_short(cfg: dict) -> str:
    try:
        import weather
        full = weather.report(cfg)
        t = re.search(r"(\d+) graus,\s*([^.]+?)\.", full)
        mx = re.search(r"máxima (?:é |de )?(\d+)", full)
        mn = re.search(r"mínima (?:é |de )?(\d+)", full)
        if t:
            s = f"{t.group(1)}° {t.group(2).strip()}"
            if mx and mn:
                s += f"  ↑{mx.group(1)} ↓{mn.group(1)}"
            return s
    except Exception as exc:  # noqa: BLE001
        log(f"hud/clima: {exc}")
    return ""


# ---------------------------------------------------------------- lembretes
def _upcoming() -> list:
    try:
        import reminders
        from datetime import datetime
        out = []
        for r in reminders.pending()[:3]:
            dt = datetime.fromtimestamp(r["at"])
            when = dt.strftime("%H:%M") if dt.date() == datetime.now().date() else dt.strftime("%d/%m %Hh")
            out.append({"t": r.get("text", ""), "w": when})
        return out
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------- loop
def start(cfg: dict) -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, args=(cfg,), daemon=True).start()


def _loop(cfg: dict) -> None:
    try:
        import psutil
        psutil.cpu_percent(interval=None)   # 1ª leitura "aquece"
    except Exception:  # noqa: BLE001
        pass

    last_weather = 0.0
    tick = 0
    while True:
        tick += 1
        try:
            payload = {"sys": _sys_snapshot()}
            payload["track"] = _media_snapshot() or {}
            payload["reminders"] = _upcoming()
            if time.time() - last_weather > 900:          # 15 min
                w = _weather_short(cfg)
                if w:
                    payload["weather"] = w
                last_weather = time.time()
            write_app_state(**payload)
        except Exception as exc:  # noqa: BLE001
            log(f"hud loop: {exc}")
        time.sleep(2.0)
