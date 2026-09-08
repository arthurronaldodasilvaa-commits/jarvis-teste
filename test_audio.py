#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnóstico da camada de voz. Rode cada teste separado:

    python test_audio.py devices    # lista microfones/saídas
    python test_audio.py voice      # testa a voz do Windows (SAPI)
    python test_audio.py llm        # testa a resposta do Jarvis (LLM local)
    python test_audio.py whisper    # grava 5s do mic e transcreve
    python test_audio.py meter      # medidor de volume do mic (12s)
    python test_audio.py clap       # detector de palmas ao vivo (20s)
    python test_audio.py actions    # dispara a rotina de chegada (Steam + Spotify)
    python test_audio.py wake "texto"   # testa se um texto ativaria o Jarvis
"""
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jarvis_voice as jv  # noqa: E402


def _mic(cfg):
    dev = jv.resolve_device(cfg["audio"].get("input_device_match", ""))
    m = jv.Mic(dev)
    m.start()
    return m


def devices():
    print(sd.query_devices())
    print("\npadrão input :", sd.query_devices(kind="input")["name"])
    print("padrão output:", sd.query_devices(kind="output")["name"])


def voice():
    jv.Mouth(jv.load_cfg()).say("Bom dia, senhor. Com o que posso te ajudar?")


def llm():
    cfg = jv.load_cfg()
    b = jv.Brain(cfg)
    b.warmup()
    for q in ["qual e o meu nome?", "me diz uma curiosidade rapida sobre o espaco"]:
        print(f"\n>> {q}")
        t = time.time()
        print("Jarvis:", b.ask(q), f"({time.time()-t:.1f}s)")


def whisper():
    cfg = jv.load_cfg()
    ears = jv.Ears(cfg)
    mic = _mic(cfg)
    print(">> fale algo agora (5 s)...")
    need = 5 * jv.SR
    buf = []
    got = 0
    while got < need:
        b = mic.read(timeout=7)
        buf.append(b)
        got += len(b)
    audio = np.concatenate(buf)[:need]
    print(">> transcrevendo...")
    txt = ears.transcribe(audio)
    print("resultado:", repr(txt))
    print("ativaria?  ", jv.is_wake_phrase(jv.norm(txt), cfg))
    print("comando?   ", jv.strip_wake_word(jv.norm(txt), "jarvis"))


def meter():
    cfg = jv.load_cfg()
    mic = _mic(cfg)
    t0 = time.time()
    while time.time() - t0 < 12:
        lvl = jv.rms(mic.read())
        print(f"{lvl:.4f} |{'#' * min(60, int(lvl * 800))}", flush=True)


def clap():
    cfg = jv.load_cfg()
    mic = _mic(cfg)
    det = jv.ClapDetector(cfg)
    print(">> bata 2 palmas (teste de 20s)...")
    t0 = time.time()
    while time.time() - t0 < 20:
        if det.feed(mic.read()):
            print(f"[{time.time()-t0:5.1f}s] ** 2 PALMAS DETECTADAS **", flush=True)


def actions():
    cfg = jv.load_cfg()
    for a in cfg["arrival"]["sequence"]:
        print("executando:", a)
        jv.run_action(a, cfg)
        time.sleep(1.0)


def wake():
    cfg = jv.load_cfg()
    txt = sys.argv[2] if len(sys.argv) > 2 else "bom dia neném o papai chegou"
    n = jv.norm(txt)
    print("texto normalizado:", repr(n))
    print("ativaria (frase de chegada)?", jv.is_wake_phrase(n, cfg))
    print("é comando 'jarvis ...'?     ", jv.strip_wake_word(n, "jarvis"))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "devices"
    {"devices": devices, "voice": voice, "llm": llm, "whisper": whisper,
     "meter": meter, "clap": clap, "actions": actions, "wake": wake}[cmd]()
