#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Jarvis Voz — escuta contínua.

- Fala a FRASE DE ATIVACAO (ou bate 2 palmas) -> saudacao + rotina de chegada.
- Diga "JARVIS ..." no inicio da fala -> ele executa o comando ou responde
  a pergunta (LLM local via Ollama). Ele te trata sempre por "Senhor".
- Qualquer outra fala é ignorada em silêncio (nunca diz "não entendi").

Roda em cima do que o OpenJarvis instalou (faster-whisper, sounddevice, numpy,
httpx). Nenhuma dependência nova.
"""

from __future__ import annotations

import ctypes
import os
import queue
import re
import subprocess
import time
import unicodedata
import webbrowser
from collections import deque
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote_plus

import numpy as np
import sounddevice as sd

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

HERE = Path(__file__).resolve().parent
CFG_PATH = HERE / "config.toml"
SR = 16000
BLOCK = 1600  # ~100 ms


# --------------------------------------------------------------------------
def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(HERE / "jarvis_voice.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def load_cfg() -> dict:
    with open(CFG_PATH, "rb") as fh:
        return tomllib.load(fh)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(block.astype(np.float64) ** 2)) + 1e-9)


# --------------------------------------------------------------------------
# microfone
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
# palmas
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
        self.floor = deque(maxlen=40)
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
# ouvidos (Whisper)
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
            condition_on_previous_text=False,
            initial_prompt=self.initial_prompt,
        )
        return " ".join(s.text for s in segs).strip()


# --------------------------------------------------------------------------
# boca (voz do Windows)
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
        text = re.sub(r"\s+", " ", text).strip()
        log(f"Jarvis: {text}")
        ps = (
            "$ErrorActionPreference='SilentlyContinue';"
            "Add-Type -AssemblyName System.Speech;"
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            + (f"try{{$s.SelectVoice('{self.voice}')}}catch{{}};" if self.voice else "")
            + f"$s.Rate={self.rate};"
            "$s.Speak([Console]::In.ReadToEnd());"
        )
        self.speaking = True
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                input=text, text=True, timeout=45,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as exc:  # noqa: BLE001
            log(f"falha na fala: {exc}")
        finally:
            self.speaking = False


# --------------------------------------------------------------------------
# cérebro (LLM local via Ollama)
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

    def warmup(self) -> None:
        try:
            self._httpx.post(
                self.url,
                json={"model": self.model, "messages": [{"role": "user", "content": "oi"}],
                      "stream": False, "think": False, "keep_alive": "30m",
                      "options": {"num_predict": 8}},
                timeout=120,
            )
            log("LLM aquecido.")
        except Exception as exc:  # noqa: BLE001
            log(f"warmup LLM falhou (segue mesmo assim): {exc}")

    def ask(self, question: str) -> str:
        try:
            r = self._httpx.post(
                self.url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.system},
                        {"role": "user", "content": question},
                    ],
                    "stream": False,
                    "think": False,
                    "keep_alive": "30m",
                    "options": {"temperature": 0.4, "num_predict": self.num_predict},
                },
                timeout=60,
            )
            msg = r.json().get("message", {}).get("content", "")
            msg = re.sub(r"<think>.*?</think>", "", msg, flags=re.S).strip()
            return msg or "Perdão, senhor, não consegui elaborar uma resposta agora."
        except Exception as exc:  # noqa: BLE001
            log(f"erro LLM: {exc}")
            return "Desculpe, senhor, meu assistente de raciocínio não respondeu."


# --------------------------------------------------------------------------
# ações
# --------------------------------------------------------------------------
VK_MEDIA_PLAY_PAUSE = 0xB3


def media_key(vk: int) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


def _spotify_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/fi", "imagename eq Spotify.exe"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout.lower()
        return "spotify.exe" in out
    except Exception:  # noqa: BLE001
        return False


def open_spec(spec: str) -> None:
    spec = spec.strip()
    if spec.startswith(("http://", "https://")):
        webbrowser.open(spec)
    else:
        os.startfile(spec)  # noqa: S606


def _run_app_value(value: str) -> None:
    kind, _, rest = value.partition(":")
    if kind.lower() in ("url", "run"):
        open_spec(rest.strip())
    else:
        open_spec(value.strip())


def best_app_key(spoken: str, cfg: dict) -> str | None:
    target = norm(spoken)
    if not target:
        return None
    best, best_score = None, 0.0
    for key in cfg["apps"]:
        k = norm(key)
        if k and (k in target or target in k):
            return key
        score = SequenceMatcher(None, target, k).ratio()
        if score > best_score:
            best, best_score = key, score
    return best if best_score >= 0.6 else None


def _play_spotify_track(uri: str, cfg: dict) -> None:
    was_running = _spotify_running()
    log(f"abrindo {uri} (spotify {'aberto' if was_running else 'fechado'})")
    os.startfile(uri)  # noqa: S606
    arr = cfg["arrival"]
    if was_running and arr.get("spotify_force_play", True):
        time.sleep(float(arr.get("spotify_wait_seconds", 4.0)))
        media_key(VK_MEDIA_PLAY_PAUSE)


def run_action(action: str, cfg: dict) -> None:
    kind, _, rest = action.partition(":")
    kind, rest = kind.strip().lower(), rest.strip()
    try:
        if action.startswith("spotify:track:"):
            _play_spotify_track(action.strip(), cfg)
        elif kind == "app":
            key = best_app_key(rest, cfg)
            if key:
                _run_app_value(cfg["apps"][key])
            else:
                log(f"app desconhecido: {rest}")
        elif kind == "url":
            webbrowser.open(rest)
        elif kind == "run":
            open_spec(rest)
        else:
            open_spec(action.strip())
    except Exception as exc:  # noqa: BLE001
        log(f"erro executando '{action}': {exc}")


# --------------------------------------------------------------------------
# interpretação de comandos (só entra aqui se começou com "jarvis")
# --------------------------------------------------------------------------
STOP_WORDS = {"para", "parar", "chega", "obrigado", "obrigada", "valeu",
              "tchau", "pode ir", "encerra", "silencio", "cala a boca"}


def strip_wake_word(n: str, wake: str) -> str | None:
    """Retorna o texto após 'jarvis' (tolera erros), ou None se não foi chamado."""
    toks = n.split()
    if not toks:
        return None
    variants = {wake, "jarves", "jarvez", "javis", "jarv", "charves", "harvest",
                "jarvis", "darveis", "jarvis", "jasmis"}
    if toks[0] in variants or SequenceMatcher(None, toks[0], wake).ratio() >= 0.6:
        return " ".join(toks[1:]).strip()
    # às vezes o Whisper cola: "jarvisabrir" / vírgula etc — pega prefixo
    m = re.match(rf"{wake[:4]}\w*[, ]+(.+)", n)
    if m:
        return m.group(1).strip()
    return None


def handle_command(payload: str, cfg: dict, mouth: Mouth, brain: Brain) -> str:
    t = norm(payload)
    if not t:
        mouth.say(cfg["assistant"].get("attention_reply", "Pois não, senhor?"))
        return "CONT"

    if t in STOP_WORDS or (len(t.split()) <= 3 and any(w in t for w in STOP_WORDS)):
        mouth.say("Às ordens, senhor.")
        return "STOP"

    m = re.search(r"(?:pesquis\w+|busca\w*|procur\w+|googl\w+)"
                  r"(?:\s+(?:no|na|por|pelo|pela|sobre|o|a))*\s+(.+)", t)
    if m:
        q = m.group(1).strip()
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(q))
        mouth.say(f"Pesquisando {q}, senhor.")
        return "CONT"

    m = re.search(r"(?:abr\w+|abre|inicia\w*|liga\w*|roda\w*|executa\w*|chama\w*|poe|abrir)\s+"
                  r"(?:o\s+|a\s+|os\s+|as\s+|um\s+|uma\s+)?(.+)", t)
    if m:
        target = m.group(1).strip()
        key = best_app_key(target, cfg)
        if key:
            _run_app_value(cfg["apps"][key])
            mouth.say(f"Abrindo {key}, senhor.")
        else:
            webbrowser.open("https://www.google.com/search?q=" + quote_plus(target))
            mouth.say(f"Não tenho {target} na lista, senhor. Procurei na web.")
        return "CONT"

    m = re.search(r"(?:toc\w+|coloc\w+|bota\w*)\s+(?:a\s+musica\s+|a\s+|o\s+)?(.+?)"
                  r"(?:\s+no\s+spotify)?$", t)
    if m:
        song = m.group(1).strip()
        os.startfile("spotify:search:" + quote_plus(song))  # noqa: S606
        mouth.say(f"Abri a busca por {song} no Spotify, senhor.")
        return "CONT"

    # pergunta aberta -> LLM
    if cfg.get("behavior", {}).get("answer_open_questions", True):
        mouth.say(brain.ask(payload))
    return "CONT"


# --------------------------------------------------------------------------
# ativação (frase de chegada ou 2 palmas)
# --------------------------------------------------------------------------
def is_wake_phrase(n: str, cfg: dict) -> bool:
    if not n:
        return False
    w = cfg["wake"]
    thr = float(w["match_threshold"])
    for p in w["phrases"]:
        pt = norm(p)
        if SequenceMatcher(None, n, pt).ratio() >= thr:
            return True
        tset, nset = set(pt.split()), set(n.split())
        if tset and len(tset & nset) / len(tset) >= 0.55:
            return True
    if "bom dia" in n and any(k in n for k in w.get("keywords_with_bomdia", [])):
        return True
    if "papai chegou" in n or "papai chego" in n:
        return True
    return False


def activate(cfg: dict, mouth: Mouth, reason: str) -> None:
    log(f"** ATIVADO ({reason}) **")
    mouth.say(cfg["tts"]["greeting"])
    for action in cfg["arrival"].get("sequence", []):
        run_action(action, cfg)
        time.sleep(0.6)


# --------------------------------------------------------------------------
# captura de uma fala (VAD)
# --------------------------------------------------------------------------
def capture_utterance(mic: Mic, cfg: dict, pre_roll: list[np.ndarray]) -> np.ndarray | None:
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
        if time.monotonic() - last_voice > sil_need:
            break
        if time.monotonic() - start > max_len:
            break
    return np.concatenate(chunks)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> None:
    cfg = load_cfg()
    log("=" * 50)
    log("Jarvis Voz iniciando (escuta contínua)")

    device = resolve_device(cfg["audio"].get("input_device_match", ""))
    ears = Ears(cfg)
    mouth = Mouth(cfg)
    brain = Brain(cfg)
    mic = Mic(device)
    mic.start()
    clap = ClapDetector(cfg)
    brain.warmup()

    wake_word = norm(cfg["assistant"].get("wake_word", "jarvis"))
    pre_roll_n = max(1, int(float(cfg["audio"].get("pre_roll_seconds", 0.5)) * SR / BLOCK))
    speech_thr = float(cfg["audio"]["speech_level"])
    cooldown = float(cfg["wake"].get("reactivate_cooldown_seconds", 45))
    last_activation = 0.0

    if cfg["tts"].get("ready_line"):
        mouth.say(cfg["tts"]["ready_line"])
    log(f'pronto — diga a frase de ativação, "{wake_word} ..." ou bata 2 palmas')

    ring: deque[np.ndarray] = deque(maxlen=pre_roll_n)
    while True:
        try:
            block = mic.read(timeout=2.0)
        except queue.Empty:
            continue

        # ignora o próprio áudio enquanto/logo após o Jarvis falar
        if mouth.speaking:
            ring.clear()
            clap.reset()
            continue

        ring.append(block)

        # 2 palmas -> ativa na hora
        if clap.feed(block) and cfg["audio"].get("clap_instant_activate", True):
            if time.monotonic() - last_activation > cooldown:
                activate(cfg, mouth, "palmas")
                last_activation = time.monotonic()
            mic.drain()
            ring.clear()
            continue

        # começou a falar? captura a frase inteira
        if rms(block) > speech_thr:
            audio = capture_utterance(mic, cfg, list(ring))
            ring.clear()
            if audio is None or len(audio) < SR * 0.3:
                continue
            text = ears.transcribe(audio)
            n = norm(text)
            if not n:
                continue
            log(f"ouvi: {text!r}")

            if is_wake_phrase(n, cfg):
                if time.monotonic() - last_activation > cooldown:
                    activate(cfg, mouth, "frase")
                    last_activation = time.monotonic()
                else:
                    log("  (em cooldown — ignorado)")
                mic.drain()
                continue

            payload = strip_wake_word(n, wake_word)
            if payload is not None:
                # recupera a versão não-normalizada após a wake word p/ o LLM
                raw = re.sub(r"(?i)^\s*jarv\w*[\s,]*", "", text).strip() or payload
                log(f"  comando: {raw!r}")
                handle_command(raw, cfg, mouth, brain)
            # senão: fala não endereçada -> silêncio
            mic.drain()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("encerrado pelo usuario")
    except Exception as exc:  # noqa: BLE001
        log(f"ERRO FATAL: {exc!r}")
        raise
