#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Jarvis Voz — escuta contínua + habilidades (skills.py).

- FRASE DE CHEGADA ("bom dia neném o papai chegou") ou 2 palmas
      -> saudação + abre Steam + toca Highway to Hell.
- "JARVIS" sozinho  -> "Olá senhor, com o que posso ajudar?" (só isso).
- "JARVIS <comando/pergunta>" -> executa ou responde (te trata por "Senhor").
- Qualquer outra fala -> silêncio.
- Ações sensíveis (desligar, reiniciar, suspender, fechar app) pedem
  confirmação falada ("sim" / "confirma" / "pode").
"""

from __future__ import annotations

import ctypes
import queue
import re
import subprocess
import sys
import time
from collections import deque
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import sounddevice as sd

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from common import log, norm
import skills

HERE = Path(__file__).resolve().parent
CFG_PATH = HERE / "config.toml"
SR = 16000
BLOCK = 1600  # ~100 ms
CNW = 0x08000000

AFFIRM = ("sim", "confirma", "confirmado", "pode", "pode sim", "isso", "claro",
          "afirmativo", "positivo", "manda", "faz", "vai", "ok", "beleza", "quero")
NEGATE = ("nao", "negativo", "cancela", "para", "deixa", "esquece", "melhor nao")


def ensure_single_instance() -> None:
    """Evita dois Jarvis ouvindo ao mesmo tempo (ex: autostart + clique manual)."""
    ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\JarvisVozSingleton")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        log("Jarvis Voz já está rodando — encerrando esta instância.")
        sys.exit(0)


def load_cfg() -> dict:
    with open(CFG_PATH, "rb") as fh:
        return tomllib.load(fh)


def rms(b: np.ndarray) -> float:
    return float(np.sqrt(np.mean(b.astype(np.float64) ** 2)) + 1e-9)


# --------------------------------------------------------------------------
class Mic:
    def __init__(self, device):
        self.q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=SR, blocksize=BLOCK, device=device,
            channels=1, dtype="float32", callback=self._cb,
        )

    def _cb(self, indata, frames, time_info, status):  # noqa: ARG002
        if status:
            log(f"audio status: {status}")
        self.q.put(indata[:, 0].copy())

    def start(self):
        self._stream.start()

    def drain(self):
        while True:
            try:
                self.q.get_nowait()
            except queue.Empty:
                return

    def read(self, timeout=None) -> np.ndarray:
        return self.q.get(timeout=timeout)


def resolve_device(match: str):
    if not match:
        return None
    want = match.lower()
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0 and want in dev["name"].lower():
            log(f"microfone: [{idx}] {dev['name']}")
            return idx
    log(f"microfone '{match}' nao encontrado — usando o padrao")
    return None


# --------------------------------------------------------------------------
class ClapDetector:
    def __init__(self, cfg: dict):
        a = cfg["audio"]
        self.on = bool(a.get("clap_enabled", True))
        self.sens = float(a["clap_sensitivity"])
        self.min_level = float(a["clap_min_level"])
        self.window = float(a["clap_window_seconds"])
        self.min_gap = float(a["clap_min_gap_seconds"])
        self.need = int(a["claps_required"])
        self.floor: deque[float] = deque(maxlen=40)
        self.claps: deque[float] = deque()
        self.armed = True

    def feed(self, block: np.ndarray) -> bool:
        if not self.on:
            return False
        lvl = rms(block)
        fl = float(np.median(self.floor)) if self.floor else 0.01
        if lvl <= max(self.min_level, fl * self.sens):
            self.floor.append(lvl)
            self.armed = True
        elif self.armed:
            now = time.monotonic()
            self.armed = False
            if not (self.claps and now - self.claps[-1] < self.min_gap):
                self.claps.append(now)
        cutoff = time.monotonic() - self.window
        while self.claps and self.claps[0] < cutoff:
            self.claps.popleft()
        if len(self.claps) >= self.need:
            self.claps.clear()
            return True
        return False

    def reset(self):
        self.claps.clear()
        self.floor.clear()


# --------------------------------------------------------------------------
class Ears:
    def __init__(self, cfg: dict):
        from faster_whisper import WhisperModel

        w = cfg["wake"]
        self.lang = w["whisper_language"]
        self.initial_prompt = w.get("whisper_initial_prompt") or None
        dev = w.get("whisper_device", "cpu")
        ct = "int8" if dev == "cpu" else "float16"
        log(f"carregando Whisper '{w['whisper_model']}' ({dev}/{ct})...")
        try:
            self.model = WhisperModel(w["whisper_model"], device=dev, compute_type=ct)
        except Exception as exc:  # noqa: BLE001
            log(f"falha no device '{dev}' ({exc}); usando cpu/int8")
            self.model = WhisperModel(w["whisper_model"], device="cpu", compute_type="int8")
        log("Whisper pronto.")

    def transcribe(self, audio: np.ndarray) -> str:
        segs, _ = self.model.transcribe(
            audio, language=self.lang, vad_filter=True,
            condition_on_previous_text=False, initial_prompt=self.initial_prompt,
        )
        return " ".join(s.text for s in segs).strip()


# --------------------------------------------------------------------------
class Mouth:
    def __init__(self, cfg: dict):
        t = cfg["tts"]
        self.voice = t.get("sapi_voice", "")
        self.rate = int(t.get("sapi_rate", 0))
        self.speaking = False

    def say(self, text: str) -> None:
        if not text:
            return
        text = re.sub(r"\s+", " ", str(text)).strip()
        log(f"Jarvis: {text}")
        ps = (
            "$ErrorActionPreference='SilentlyContinue';"
            "Add-Type -AssemblyName System.Speech;"
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            + (f"try{{$s.SelectVoice('{self.voice}')}}catch{{}};" if self.voice else "")
            + f"$s.Rate={self.rate};$s.Speak([Console]::In.ReadToEnd());"
        )
        self.speaking = True
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                input=text, text=True, timeout=60, creationflags=CNW,
            )
        except Exception as exc:  # noqa: BLE001
            log(f"falha na fala: {exc}")
        finally:
            self.speaking = False


# --------------------------------------------------------------------------
class Brain:
    def __init__(self, cfg: dict):
        import httpx

        a = cfg["assistant"]
        self._httpx = httpx
        self.url = a["ollama_url"].rstrip("/") + "/api/chat"
        self.model = a["model"]
        self.system = a["system_prompt"].strip()
        self.num_predict = int(a.get("reply_num_predict", 160))

    def _post(self, messages, num_predict, temperature=0.4):
        r = self._httpx.post(
            self.url,
            json={"model": self.model, "messages": messages, "stream": False,
                  "think": False, "keep_alive": "30m",
                  "options": {"temperature": temperature, "num_predict": num_predict}},
            timeout=90,
        )
        msg = r.json().get("message", {}).get("content", "")
        return re.sub(r"<think>.*?</think>", "", msg, flags=re.S).strip()

    def warmup(self) -> None:
        try:
            self._post([{"role": "user", "content": "oi"}], 8)
            log("LLM aquecido.")
        except Exception as exc:  # noqa: BLE001
            log(f"warmup LLM falhou: {exc}")

    def ask(self, question: str) -> str:
        try:
            return self._post(
                [{"role": "system", "content": self.system},
                 {"role": "user", "content": question}],
                self.num_predict,
            ) or "Perdão, senhor, não consegui elaborar uma resposta."
        except Exception as exc:  # noqa: BLE001
            log(f"erro LLM: {exc}")
            return "Desculpe, senhor, meu raciocínio não respondeu agora."

    def compose(self, instruction: str, num_predict: int = 600) -> str:
        try:
            return self._post(
                [{"role": "system", "content":
                  "Você é um redator. Escreva em português do Brasil, claro e correto. "
                  "Entregue só o texto pedido, sem comentários seus."},
                 {"role": "user", "content": instruction}],
                num_predict, temperature=0.7,
            ) or "(não consegui gerar o texto)"
        except Exception as exc:  # noqa: BLE001
            log(f"erro compose: {exc}")
            return "(erro ao gerar o texto)"


# --------------------------------------------------------------------------
# ativação (frase de chegada)
# --------------------------------------------------------------------------
def is_arrival_phrase(n: str, cfg: dict) -> bool:
    if not n:
        return False
    arr = cfg["arrival"]
    target = norm(arr.get("phrase", "bom dia nenem o papai chegou"))
    if SequenceMatcher(None, n, target).ratio() >= float(arr.get("match_threshold", 0.7)):
        return True
    has_papai = "papai" in n or "pape" in n or "papi" in n
    has_chegou = "chegou" in n or "chego" in n or "chegô" in n or "chego" in n
    has_bomdia = "bom dia" in n
    return (has_papai and has_chegou) or (has_bomdia and has_papai)


def run_arrival(cfg: dict, mouth: Mouth, reason: str) -> None:
    log(f"** CHEGADA ({reason}) **")
    greeting = (cfg.get("arrival", {}).get("greeting")
               or cfg.get("tts", {}).get("greeting")
               or "Bom dia, senhor.")
    mouth.say(greeting)
    for action in cfg["arrival"].get("sequence", []):
        _run_action(action, cfg)
        time.sleep(0.6)


def _run_action(action: str, cfg: dict) -> None:
    import os
    import webbrowser
    try:
        if action.startswith("spotify:track:"):
            was = "spotify.exe" in subprocess.run(
                ["tasklist", "/fi", "imagename eq Spotify.exe"],
                capture_output=True, text=True, creationflags=CNW).stdout.lower()
            os.startfile(action)  # noqa: S606
            if was and cfg["arrival"].get("spotify_force_play", True):
                time.sleep(float(cfg["arrival"].get("spotify_wait_seconds", 4.0)))
                __import__("ctypes").windll.user32.keybd_event(0xB3, 0, 0, 0)
                __import__("ctypes").windll.user32.keybd_event(0xB3, 0, 2, 0)
        else:
            kind, _, rest = action.partition(":")
            if kind == "app":
                skills.open_target(rest.strip(), cfg)
            elif kind == "url":
                webbrowser.open(rest.strip())
            elif kind == "run":
                (webbrowser.open if rest.strip().startswith("http") else os.startfile)(rest.strip())  # noqa: S606
    except Exception as exc:  # noqa: BLE001
        log(f"erro na acao de chegada '{action}': {exc}")


# --------------------------------------------------------------------------
def strip_wake_word(raw: str, n: str, wake: str) -> str | None:
    toks = n.split()
    if not toks:
        return None
    first = toks[0]
    hit = (first == wake or SequenceMatcher(None, first, wake).ratio() >= 0.6
           or first.startswith(wake[:4]))
    if not hit:
        return None
    return re.sub(rf"(?i)^\s*{wake[:4]}\w*[\s,.:;!?-]*", "", raw).strip()


def capture_utterance(mic: Mic, cfg: dict, pre_roll) -> np.ndarray | None:
    a = cfg["audio"]
    thr = float(a["speech_level"])
    sil_need = float(a["silence_timeout"])
    max_len = float(a["max_utterance_seconds"])
    chunks = list(pre_roll)
    last_voice = time.monotonic()
    start = time.monotonic()
    while True:
        try:
            b = mic.read(timeout=2.0)
        except queue.Empty:
            return None
        chunks.append(b)
        if rms(b) > thr:
            last_voice = time.monotonic()
        if time.monotonic() - last_voice > sil_need or time.monotonic() - start > max_len:
            break
    return np.concatenate(chunks)


# --------------------------------------------------------------------------
def main() -> None:
    ensure_single_instance()
    cfg = load_cfg()
    log("=" * 50)
    log("Jarvis Voz iniciando (escuta contínua + skills)")

    device = resolve_device(cfg["audio"].get("input_device_match", ""))
    ears = Ears(cfg)
    mouth = Mouth(cfg)
    brain = Brain(cfg)
    mic = Mic(device)
    mic.start()
    clap = ClapDetector(cfg)
    skills.build_indexes()
    brain.warmup()

    wake_word = norm(cfg["assistant"].get("wake_word", "jarvis"))
    pre_n = max(1, int(float(cfg["audio"].get("pre_roll_seconds", 0.5)) * SR / BLOCK))
    speech_thr = float(cfg["audio"]["speech_level"])
    cooldown = float(cfg["arrival"].get("reactivate_cooldown_seconds", 30))

    if cfg["tts"].get("ready_line"):
        mouth.say(cfg["tts"]["ready_line"])
    log(f'pronto — frase de chegada, "{wake_word} ..." ou 2 palmas')

    st = {"last_arrival": 0.0, "pending": None}   # pending = (pergunta, do, deadline)

    ring: deque[np.ndarray] = deque(maxlen=pre_n)
    while True:
        try:
            block = mic.read(timeout=2.0)
        except queue.Empty:
            p = st["pending"]
            if p and time.monotonic() > p[2]:
                log("confirmação expirou"); st["pending"] = None
            continue
        try:
            _handle_block(block, ring, mic, ears, mouth, brain, clap, cfg,
                          wake_word, speech_thr, cooldown, st)
        except Exception as exc:  # noqa: BLE001
            log(f"erro no loop (ignorado): {exc!r}")
            try:
                mic.drain()
            except Exception:  # noqa: BLE001
                pass
            ring.clear()


def _handle_block(block, ring, mic, ears, mouth, brain, clap, cfg, wake_word,
                  speech_thr, cooldown, st) -> None:
    if mouth.speaking:
        ring.clear(); clap.reset(); return

    ring.append(block)

    if clap.feed(block) and cfg["audio"].get("clap_instant_activate", True):
        if time.monotonic() - st["last_arrival"] > cooldown:
            run_arrival(cfg, mouth, "palmas")
            st["last_arrival"] = time.monotonic()
        mic.drain(); ring.clear(); return

    if rms(block) <= speech_thr:
        return

    audio = capture_utterance(mic, cfg, list(ring))
    ring.clear()
    if audio is None or len(audio) < SR * 0.3:
        return
    raw = ears.transcribe(audio)
    n = norm(raw)
    if not n:
        return
    log(f"ouvi: {raw!r}")

    # -------- resposta a uma confirmação pendente --------
    if st["pending"]:
        _question, do, _dl = st["pending"]
        if any(w in n for w in NEGATE):
            mouth.say("Cancelado, senhor."); st["pending"] = None; mic.drain(); return
        if any(n == w or n.startswith(w + " ") or w in n.split() for w in AFFIRM):
            st["pending"] = None
            try:
                followup = do()
            except Exception as exc:  # noqa: BLE001
                log(f"erro na ação confirmada: {exc}"); followup = "Deu erro, senhor."
            mouth.say(followup or "Feito, senhor.")
            mic.drain(); return
        mic.drain(); return   # fala não relacionada durante a confirmação

    # -------- frase de chegada --------
    if is_arrival_phrase(n, cfg):
        if time.monotonic() - st["last_arrival"] > cooldown:
            run_arrival(cfg, mouth, "frase")
            st["last_arrival"] = time.monotonic()
        else:
            log("  (cooldown — ignorado)")
        mic.drain(); return

    # -------- comando "jarvis ..." --------
    payload = strip_wake_word(raw, n, wake_word)
    if payload is None:
        mic.drain(); return          # fala não endereçada -> silêncio

    if not norm(payload):
        mouth.say(cfg["assistant"].get("attention_reply", "Olá senhor, com o que posso ajudar?"))
        mic.drain(); return

    log(f"  comando: {payload!r}")
    try:
        res = skills.dispatch(payload, cfg, mouth.say, brain)
    except Exception as exc:  # noqa: BLE001
        log(f"erro no dispatch: {exc!r}")
        mouth.say("Tive um erro ao executar isso, senhor.")
        mic.drain(); return

    if res.to_llm:
        mouth.say(brain.ask(res.to_llm))
    elif res.confirm:
        question, do = res.confirm
        mouth.say(question)
        st["pending"] = (question, do, time.monotonic() + 20)
    elif res.speak:
        mouth.say(res.speak)
    mic.drain()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("encerrado pelo usuario")
    except Exception as exc:  # noqa: BLE001
        log(f"ERRO FATAL: {exc!r}")
        raise
