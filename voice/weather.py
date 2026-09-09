#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
weather.py — clima por voz, via Open-Meteo (grátis, sem chave).

  "como está o tempo?"          -> agora + máxima/mínima + chuva hoje
  "vai chover amanhã?"          -> previsão de amanhã
  "qual a temperatura em Recife?"

Localização: cidade do config ([location].city) ou, na falta, pelo IP.
"""
from __future__ import annotations

import time

from common import log, norm

_CACHE: dict = {}          # {"key": (payload, expires_ts)}
_COORD_CACHE: dict = {}

_WMO = {
    0: "céu limpo", 1: "quase limpo", 2: "parcialmente nublado", 3: "nublado",
    45: "névoa", 48: "névoa gelada",
    51: "garoa fraca", 53: "garoa", 55: "garoa forte",
    56: "garoa congelante", 57: "garoa congelante forte",
    61: "chuva fraca", 63: "chuva", 65: "chuva forte",
    66: "chuva congelante", 67: "chuva congelante forte",
    71: "neve fraca", 73: "neve", 75: "neve forte", 77: "grãos de neve",
    80: "pancadas de chuva", 81: "pancadas de chuva", 82: "pancadas fortes de chuva",
    85: "pancadas de neve", 86: "pancadas fortes de neve",
    95: "tempestade", 96: "tempestade com granizo", 99: "tempestade com granizo",
}


def _get_json(url: str, params: dict | None = None, timeout: float = 8):
    import httpx
    r = httpx.get(url, params=params, timeout=timeout,
                  headers={"User-Agent": "JarvisVoice/1.0"})
    r.raise_for_status()
    return r.json()


def _coords_from_ip() -> tuple[float, float, str] | None:
    try:
        d = _get_json("http://ip-api.com/json/", {"fields": "lat,lon,city,status"})
        if d.get("status") == "success":
            return d["lat"], d["lon"], d.get("city", "sua região")
    except Exception as exc:  # noqa: BLE001
        log(f"weather: ip falhou ({exc})")
    return None


def _coords_from_city(city: str) -> tuple[float, float, str] | None:
    key = norm(city)
    if key in _COORD_CACHE:
        return _COORD_CACHE[key]
    try:
        d = _get_json("https://geocoding-api.open-meteo.com/v1/search",
                      {"name": city, "count": 1, "language": "pt", "format": "json"})
        res = (d.get("results") or [])
        if res:
            r = res[0]
            out = (r["latitude"], r["longitude"], r.get("name", city))
            _COORD_CACHE[key] = out
            return out
    except Exception as exc:  # noqa: BLE001
        log(f"weather: geocode falhou ({exc})")
    return None


def _resolve(cfg: dict, city: str | None) -> tuple[float, float, str] | None:
    if city:
        return _coords_from_city(city)
    cfgcity = (cfg.get("location", {}) or {}).get("city", "")
    if cfgcity:
        c = _coords_from_city(cfgcity)
        if c:
            return c
    return _coords_from_ip()


def _forecast(lat: float, lon: float) -> dict:
    key = f"{lat:.2f},{lon:.2f}"
    hit = _CACHE.get(key)
    if hit and hit[1] > time.time():
        return hit[0]
    d = _get_json("https://api.open-meteo.com/v1/forecast", {
        "latitude": lat, "longitude": lon, "timezone": "auto",
        "current": "temperature_2m,apparent_temperature,weather_code,relative_humidity_2m",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max",
        "forecast_days": 2,
    })
    _CACHE[key] = (d, time.time() + 900)   # 15 min
    return d


def _desc(code) -> str:
    try:
        return _WMO.get(int(code), "tempo variável")
    except (TypeError, ValueError):
        return "tempo variável"


def report(cfg: dict, city: str | None = None, day: str = "hoje") -> str:
    loc = _resolve(cfg, city)
    if not loc:
        return "Não consegui descobrir a localização, senhor."
    lat, lon, name = loc
    try:
        d = _forecast(lat, lon)
    except Exception as exc:  # noqa: BLE001
        log(f"weather: forecast falhou ({exc})")
        return "Não consegui o clima agora, senhor."

    cur = d.get("current", {})
    dl = d.get("daily", {})
    idx = 1 if day == "amanhã" else 0

    def _r(v):
        try:
            return round(float(v))
        except (TypeError, ValueError):
            return "?"

    try:
        tmax = _r(dl["temperature_2m_max"][idx])
        tmin = _r(dl["temperature_2m_min"][idx])
        pchuva = _r(dl["precipitation_probability_max"][idx])
        cod_dia = _desc(dl["weather_code"][idx])
    except (KeyError, IndexError):
        return "A previsão veio incompleta, senhor."

    chuva = (f" {pchuva}% de chance de chuva." if isinstance(pchuva, int) and pchuva >= 10
             else " Sem chuva à vista." if isinstance(pchuva, int) else "")

    if day == "amanhã":
        return (f"Amanhã em {name}, senhor: {cod_dia}, máxima de {tmax} e mínima de {tmin} graus."
                + chuva)

    t = _r(cur.get("temperature_2m"))
    sens = _r(cur.get("apparent_temperature"))
    agora = _desc(cur.get("weather_code"))
    sens_txt = f" Sensação de {sens}." if sens != t and isinstance(sens, int) else ""
    return (f"Agora em {name}, senhor: {t} graus, {agora}.{sens_txt} "
            f"Hoje a máxima é {tmax} e a mínima {tmin}.{chuva}")
