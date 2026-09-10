#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnóstico. Rode cada teste separado:

    python test_audio.py devices
    python test_audio.py voice
    python test_audio.py llm
    python test_audio.py whisper
    python test_audio.py meter
    python test_audio.py clap
    python test_audio.py actions
    python test_audio.py skill "abrir palworld"
    python test_audio.py index
    python test_audio.py safety
"""
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jarvis_voice as jv  # noqa: E402
import skills  # noqa: E402


def _mic(cfg):
    m = jv.Mic(jv.resolve_device(cfg["audio"].get("input_device_match", "")))
    m.start()
    return m


def devices():
    print(sd.query_devices())


def voice():
    jv.Mouth(jv.load_cfg()).say("Bom dia, senhor. Com o que posso te ajudar?")


def llm():
    b = jv.Brain(jv.load_cfg())
    b.warmup()
    for q in ["qual e o meu nome?", "me diz uma curiosidade rapida sobre o oceano"]:
        t = time.time()
        print(f"\n>> {q}\nJarvis: {b.ask(q)} ({time.time()-t:.1f}s)")


def whisper():
    cfg = jv.load_cfg()
    ears = jv.Ears(cfg)
    mic = _mic(cfg)
    print(">> fale 5s...")
    buf, got = [], 0
    while got < 5 * jv.SR:
        b = mic.read(timeout=7); buf.append(b); got += len(b)
    audio = np.concatenate(buf)
    t = time.time(); w = ears.hear_wake(audio); tw = time.time() - t
    t = time.time(); c = ears.hear_command(audio); tc = time.time() - t
    print(f"estágio 1 (tiny, {tw*1000:.0f}ms): {w!r}")
    print(f"estágio 2 (small, {tc*1000:.0f}ms): {c!r}")
    print("é frase de chegada? ", jv.is_arrival_phrase(jv.norm(c), cfg))
    print("é 'jarvis ...'?      ", jv.strip_wake_word(c, jv.norm(c), "jarvis"))


def meter():
    mic = _mic(jv.load_cfg())
    t0 = time.time()
    while time.time() - t0 < 12:
        lvl = jv.rms(mic.read())
        print(f"{lvl:.4f} |{'#' * min(60, int(lvl * 800))}", flush=True)


def clap():
    cfg = jv.load_cfg()
    mic = _mic(cfg)
    det = jv.ClapDetector(cfg)
    print(">> bata 2 palmas (20s)...")
    t0 = time.time()
    while time.time() - t0 < 20:
        if det.feed(mic.read()):
            print(f"[{time.time()-t0:5.1f}s] ** 2 PALMAS **", flush=True)


def actions():
    cfg = jv.load_cfg()
    for a in cfg["arrival"]["sequence"]:
        print("->", a)
        jv._run_action(a, cfg)
        time.sleep(1)


def index():
    skills.build_indexes()
    print("\nJOGOS:")
    for k, v in sorted(skills._games.items()):
        print(f"  {v:>10}  {k}")
    print(f"\n{len(skills._lnks)} atalhos do Menu Iniciar (amostra):")
    for k in list(skills._lnks)[:25]:
        print("  ", k)


def skill():
    cfg = jv.load_cfg()
    skills.build_indexes()
    text = sys.argv[2] if len(sys.argv) > 2 else "que horas sao"

    class FakeBrain:
        def ask(self, q): return f"(LLM responderia: {q})"
        def compose(self, i, num_predict=600): return f"(texto sobre: {i})"

    res = skills.dispatch(text, cfg, print, FakeBrain())
    print("Result:", res)


def safety():
    """Verifica a trava anti-loop de comandos (_guard_command). Não fala nada,
    não abre nada — só exercita a lógica."""
    import collections

    import common
    common.push_note = lambda *a, **k: None          # não mexe no HUD real
    common.write_app_state = lambda **k: None
    common.log = jv.log = lambda m: None             # não polui o jarvis_voice.log
    paused = [False]
    orig = jv.set_paused
    jv.set_paused = lambda p, **k: paused.__setitem__(0, p)
    cfg = jv.load_cfg()

    class M:
        def say(self, t): print(f"   [fala] {t}")

    def run(name, cmds, expect_pause):
        paused[0] = False
        st = {"recent": collections.deque(maxlen=16), "pending": None, "await": None}
        blocked = [jv._guard_command(jv.norm(c), st, M(), cfg) for c in cmds]
        ok = paused[0] == expect_pause
        print(f"  {'OK ' if ok else 'FALHOU '}{name}: bloqueados={blocked} pausou={paused[0]}")
        return ok

    allok = True
    allok &= run("comando idêntico 4x", ["me lembra de tirar o bolo em 20 minutos"] * 4, True)
    allok &= run("variações do Whisper",
                 ["pesquisa gato no google", "pesquisa gatos no google",
                  "pesquise gato no google"], True)
    allok &= run("4 comandos distintos (uso normal)",
                 ["que horas sao", "como esta o tempo", "abre a steam", "qual a fase da lua"], False)
    allok &= run("5 comandos distintos (enxurrada)",
                 ["que horas sao", "como esta o tempo", "abre a steam",
                  "qual a fase da lua", "quanto e dois mais dois"], True)
    jv.set_paused = orig
    print("\n" + ("== TUDO OK ==" if allok else "== ALGO FALHOU =="))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "devices"
    {"devices": devices, "voice": voice, "llm": llm, "whisper": whisper,
     "meter": meter, "clap": clap, "actions": actions, "index": index,
     "skill": skill, "safety": safety}[cmd]()
