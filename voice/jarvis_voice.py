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

import base64
import ctypes
import ctypes.wintypes as wt
import os
import queue
import re
import subprocess
import sys
import threading
import time
import webbrowser
import winsound
from collections import deque
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import sounddevice as sd

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from common import log, norm, read_control, rotate_log, write_app_state, write_control
import skills

HERE = Path(__file__).resolve().parent
CFG_PATH = HERE / "config.toml"
SR = 16000
BLOCK = 1600  # ~100 ms
CNW = 0x08000000

AFFIRM = ("sim", "confirma", "confirmo", "confirmado", "pode", "pode sim", "isso",
          "isso mesmo", "claro", "afirmativo", "positivo", "manda", "manda ver",
          "faz", "faca", "vai", "vai la", "ok", "okay", "beleza", "blz", "quero",
          "quero sim", "concordo", "aham", "uhum", "com certeza", "certo", "exato",
          "pode desligar", "pode reiniciar", "pode fechar", "pode suspender",
          "sim senhor", "isso ai", "positivo senhor")
NEGATE = ("nao", "não", "negativo", "cancela", "cancelar", "para", "parar", "deixa",
          "deixa pra la", "esquece", "melhor nao", "nao quero", "para tudo", "aborta")
CONFIRM_TIMEOUT = 18.0

# O roteador escolhe um 'cmd' desta tabela; a frase canônica é montada aqui.
_ROUTER_SHAPES = {"cubo", "esfera", "cone", "cilindro", "piramide", "toro", "octaedro"}
_ROUTER_TEMPLATES = {
    "rota": "como chegar em {arg}",
    "buscar_local": "procura {arg} no mapa",
    "abrir": "abrir {arg}",
    "jogo": "jogar {arg}",
    "musica": "tocar {arg}",
    "google": "pesquisar no google {arg}",
    "forma": "cria um {arg}",
    "triangulo": "cria um triangulo retangulo",
    "tabela_angulos": "mostra a tabela de angulos notaveis",
    "tabela_relacoes": "mostra as relacoes trigonometricas",
    "limpar": "limpar tudo",
    "camera_on": "ativar camera",
    "camera_off": "desativar camera",
    "cerebro": "volta pro cerebro",
    "hora": "que horas sao",
    "data": "que dia e hoje",
    "volume_up": "aumentar volume",
    "volume_down": "abaixar volume",
    "mudo": "mudo",
    "midia_next": "proxima musica",
    "midia_pause": "pausar musica",
    "midia_play": "tocar musica",
    "bloquear": "bloquear a tela",
    "suspender": "suspender",
    "desligar": "desligar o computador",
    "reiniciar": "reiniciar",
    "escrever": "escrever um texto sobre {arg}",
    "digitar": "digitar {arg}",
    "anotar": "anota {arg}",
    "modo_cinema": "modo cinema",
    "fechar": "fechar {arg}",
}

# qual skill precisa estar ligada no perfil pra este cmd valer
_ROUTER_SKILL = {
    "forma": "holograms", "triangulo": "holograms", "tabela_angulos": "holograms",
    "tabela_relacoes": "holograms", "limpar": "holograms",
    "camera_on": "holograms", "camera_off": "holograms", "cerebro": "holograms",
    "rota": "maps", "buscar_local": "maps",
    "musica": "music", "midia_next": "media_keys", "midia_pause": "media_keys",
    "midia_play": "media_keys", "volume_up": "media_keys", "volume_down": "media_keys",
    "mudo": "media_keys",
    "jogo": "games", "google": "web_search", "escrever": "compose",
}

_ROUTER_PROMPT = """Você classifica o pedido de uma pessoa a um assistente de voz.
Responda SÓ com um JSON de uma linha: {"cmd": "<nome>", "arg": "<texto>"}
Se não for um comando (pergunta, papo, dúvida): {"cmd": "conversa"}

cmd possíveis:
 rota (arg=lugar)            buscar_local (arg=lugar/tipo)   abrir (arg=app/site)
 jogo (arg=nome)             musica (arg=nome)               google (arg=termo)
 forma (arg= cubo|esfera|cone|cilindro|piramide|toro|octaedro)
 triangulo (triângulo retângulo 3D)
 tabela_angulos (tabela dos ângulos notáveis 30/45/60 — sen, cos, tan)
 tabela_relacoes (relações trigonométricas — seno=CO/H, cosseno=CA/H, tangente=CO/CA)
 limpar
 camera_on   camera_off   cerebro   hora   data
 volume_up   volume_down   mudo   midia_next   midia_pause   midia_play
 bloquear   suspender   desligar   reiniciar
 escrever (arg=assunto)   digitar (arg=texto)   anotar (arg=nota)
 modo_cinema   fechar (arg=app)

Regras: use o arg com as palavras da pessoa. Na dúvida, {"cmd":"conversa"}.

Obs: 'jogo' é videogame (Steam). 'forma' é um objeto 3D na tela. 'musica' toca no Spotify.

Exemplos:
"quero ir pra padaria" -> {"cmd":"rota","arg":"padaria"}
"tem restaurante bom aqui perto?" -> {"cmd":"buscar_local","arg":"restaurante perto de mim"}
"bora ouvir um som do queen" -> {"cmd":"musica","arg":"queen"}
"me joga uma esfera aí" -> {"cmd":"forma","arg":"esfera"}
"joga um cubo na tela" -> {"cmd":"forma","arg":"cubo"}
"faz um cone" -> {"cmd":"forma","arg":"cone"}
"me vira um triângulo retângulo" -> {"cmd":"triangulo"}
"quero ver a tabela de ângulos notáveis" -> {"cmd":"tabela_angulos"}
"mostra as relações trigonométricas" -> {"cmd":"tabela_relacoes"}
"me vê as relações do seno e cosseno" -> {"cmd":"tabela_relacoes"}
"quero jogar palworld" -> {"cmd":"jogo","arg":"palworld"}
"cadê meu spotify" -> {"cmd":"abrir","arg":"spotify"}
"tá calor, sobe o som" -> {"cmd":"volume_up"}
"apaga essas formas" -> {"cmd":"limpar"}
"qual a capital da França" -> {"cmd":"conversa"}
"me conta uma piada" -> {"cmd":"conversa"}"""


def _is_affirm(n: str) -> bool:
    toks = n.split()
    if not toks:
        return False
    if n in AFFIRM or toks[0] in ("sim", "pode", "claro", "isso", "ok", "okay",
                                  "beleza", "confirmo", "exato", "aham", "uhum", "certo"):
        return True
    return any(a in n for a in ("sim", "confirm", "pode sim", "com certeza",
                                "afirmativo", "positivo", "isso mesmo",
                                "pode desligar", "pode reiniciar", "pode fechar"))


def _is_negate(n: str) -> bool:
    toks = n.split()
    return bool(toks) and (toks[0] in ("nao", "cancela", "cancelar", "para", "aborta",
                                       "deixa", "esquece", "negativo")
                           or n in NEGATE)


def ensure_single_instance() -> None:
    """Evita dois Jarvis ouvindo ao mesmo tempo (ex: autostart + clique manual)."""
    ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\JarvisVozSingleton")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        log("Jarvis Voz já está rodando — encerrando esta instância.")
        sys.exit(0)


SECRETS_PATH = HERE / "secrets.toml"
PROFILES_DIR = HERE / "profiles"


def _deep_merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        elif v not in ("", None):
            base[k] = v
    return base


def _active_profile(cfg: dict) -> str:
    """Prioridade:  --profile X  >  env JARVIS_PROFILE  >  config.toml [profile].active"""
    for i, a in enumerate(sys.argv):
        if a in ("--profile", "-p") and i + 1 < len(sys.argv):
            return sys.argv[i + 1].strip()
        if a.startswith("--profile="):
            return a.split("=", 1)[1].strip()
    if os.environ.get("JARVIS_PROFILE"):
        return os.environ["JARVIS_PROFILE"].strip()
    return str(cfg.get("profile", {}).get("active", "")).strip()


def load_cfg() -> dict:
    with open(CFG_PATH, "rb") as fh:
        cfg = tomllib.load(fh)

    prof = _active_profile(cfg)
    if prof:
        ppath = PROFILES_DIR / f"{prof}.toml"
        if ppath.is_file():
            with open(ppath, "rb") as fh:
                pdata = tomllib.load(fh)
            drop = pdata.pop("drop_apps", [])
            _deep_merge(cfg, pdata)
            for k in list(cfg.get("apps", {})):
                if norm(k) in {norm(d) for d in drop}:
                    cfg["apps"].pop(k, None)
            cfg.setdefault("profile", {})["active"] = prof
            log(f"perfil ativo: {prof}")
        else:
            log(f"perfil '{prof}' não existe ({ppath}) — usando config base")

    if SECRETS_PATH.is_file():          # secrets.toml sobrescreve (fora do git)
        with open(SECRETS_PATH, "rb") as fh:
            _deep_merge(cfg, tomllib.load(fh))
    return cfg


def rms(b: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(b, dtype=np.float32))) + 1e-9)


def _collapse_repeats(text: str) -> str:
    """Whisper às vezes trava repetindo a mesma frase — corta na 1ª ocorrência."""
    t = text.strip()
    if not t:
        return t
    # frase inteira repetida ("X. X. X.")
    m = re.match(r"(.{6,80}?[.!?])\s*(?:\1\s*){2,}", t)
    if m:
        return m.group(1).strip()
    # palavra/token repetido 4+ vezes seguidas
    t = re.sub(r"\b(\w{2,})(\s+\1\b){3,}", r"\1", t)
    return t.strip()


# --------------------------------------------------------------------------
class Mic:
    def __init__(self, device):
        self.q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=SR, blocksize=BLOCK, device=device,
            channels=1, dtype="float32", callback=self._cb,
            latency="high",   # buffer maior no driver -> menos "input overflow" sob carga
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
class Ears:
    """STT em 2 estágios: um modelo minúsculo filtra TODA fala; o modelo bom
    só roda quando o pequeno viu 'jarvis' ou a frase de chegada."""

    def __init__(self, cfg: dict):
        from faster_whisper import WhisperModel

        w = cfg["wake"]
        self.lang = w["whisper_language"]
        self.initial_prompt = w.get("whisper_initial_prompt") or None
        self.beam = int(w.get("beam_size", 1))
        dev = w.get("whisper_device", "cpu")
        ct = "int8" if dev == "cpu" else "float16"

        wake_name = w.get("wake_model", w.get("whisper_model", "tiny"))
        cmd_name = w.get("command_model", w.get("whisper_model", "small"))

        def _load(name):
            log(f"carregando Whisper '{name}' ({dev}/{ct})...")
            try:
                return WhisperModel(name, device=dev, compute_type=ct)
            except Exception as exc:  # noqa: BLE001
                log(f"  falha ({exc}); cpu/int8")
                return WhisperModel(name, device="cpu", compute_type="int8")

        self.wake = _load(wake_name)
        self.cmd = self.wake if cmd_name == wake_name else _load(cmd_name)
        log("Whisper pronto (2 estágios).")

    def hear_wake(self, audio: np.ndarray) -> str:
        """1ª passada — rápida. Mantém o initial_prompt (ajuda a captar 'jarvis')."""
        segs, _ = self.wake.transcribe(
            audio, language=self.lang, beam_size=1, vad_filter=False,
            condition_on_previous_text=False, initial_prompt=self.initial_prompt,
            no_repeat_ngram_size=3,
        )
        return _collapse_repeats(" ".join(s.text for s in segs).strip())

    def hear_command(self, audio: np.ndarray) -> str:
        """2ª passada — precisa."""
        segs, _ = self.cmd.transcribe(
            audio, language=self.lang, beam_size=self.beam, vad_filter=True,
            condition_on_previous_text=False, initial_prompt=self.initial_prompt,
            no_repeat_ngram_size=3,
        )
        return _collapse_repeats(" ".join(s.text for s in segs).strip())


# --------------------------------------------------------------------------
class Mouth:
    """Voz do Windows (SAPI). Mantém UM PowerShell vivo com o sintetizador já
    carregado — cada fala vira só um write no stdin (sem gastar ~0,5s subindo
    um processo novo toda vez)."""

    def __init__(self, cfg: dict):
        t = cfg["tts"]
        self.voice = t.get("sapi_voice", "")
        self.rate = int(t.get("sapi_rate", 0))
        self.speaking = False
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._spawn()

    def _spawn(self) -> None:
        sel = f"try{{$s.SelectVoice('{self.voice}')}}catch{{}}" if self.voice else ""
        script = (
            "$ErrorActionPreference='SilentlyContinue';"
            "Add-Type -AssemblyName System.Speech;"
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            f"{sel};$s.Rate={self.rate};"
            "while($true){$l=[Console]::In.ReadLine();"
            "if($null -eq $l -or $l -eq '__QUIT__'){break};"
            "$t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($l));"
            "$s.Speak($t);[Console]::Out.WriteLine('__DONE__');[Console]::Out.Flush()}"
        )
        try:
            self._proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                text=True, encoding="utf-8", creationflags=CNW, bufsize=1,
            )
            log("TTS worker pronto.")
        except Exception as exc:  # noqa: BLE001
            log(f"não subi o TTS worker ({exc}); usando modo lento")
            self._proc = None

    def say(self, text: str) -> None:
        if not text:
            return
        text = re.sub(r"\s+", " ", str(text)).strip()
        log(f"Jarvis: {text}")
        self.speaking = True
        write_app_state(speaking=True, status="FALANDO")
        try:
            self._speak(text)
        except Exception as exc:  # noqa: BLE001
            log(f"falha na fala: {exc}")
        finally:
            self.speaking = False
            write_app_state(speaking=False, status="OUVINDO")

    def _speak(self, text: str) -> None:
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._spawn()
            if self._proc is not None:
                b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
                self._proc.stdin.write(b64 + "\n")
                self._proc.stdin.flush()
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    line = self._proc.stdout.readline()
                    if not line or line.strip() == "__DONE__":
                        return
                return
        # sem worker -> fallback um-tiro
        ps = ("Add-Type -AssemblyName System.Speech;"
              "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
              + (f"try{{$s.SelectVoice('{self.voice}')}}catch{{}};" if self.voice else "")
              + f"$s.Rate={self.rate};$s.Speak([Console]::In.ReadToEnd());")
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       input=text, text=True, timeout=60, creationflags=CNW)

    def close(self) -> None:
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.stdin.write("__QUIT__\n")
                self._proc.stdin.flush()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------
class Brain:
    def __init__(self, cfg: dict):
        import httpx

        a = cfg["assistant"]
        self._httpx = httpx
        self.url = a["ollama_url"].rstrip("/") + "/api/chat"
        self.model = a["model"]
        self.system = a["system_prompt"].strip()
        self.num_predict = int(a.get("reply_num_predict", 110))
        self.keep_alive = a.get("keep_alive", "1h")
        self.keepwarm_minutes = float(a.get("keepwarm_minutes", 10))
        self.skills = cfg.get("skills", {})

    def _post(self, messages, num_predict, temperature=0.4):
        r = self._httpx.post(
            self.url,
            json={"model": self.model, "messages": messages, "stream": False,
                  "think": False, "keep_alive": self.keep_alive,
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

    def start_keepwarm(self) -> None:
        if self.keepwarm_minutes <= 0:
            return

        def loop():
            while True:
                time.sleep(self.keepwarm_minutes * 60)
                try:
                    self._httpx.post(self.url, json={
                        "model": self.model, "messages": [{"role": "user", "content": "."}],
                        "stream": False, "think": False, "keep_alive": self.keep_alive,
                        "options": {"num_predict": 1},
                    }, timeout=30)
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=loop, daemon=True).start()
        log(f"keep-warm do LLM a cada {self.keepwarm_minutes:g} min")

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

    def route(self, text: str) -> str:
        """Classifica o pedido e devolve a frase de COMANDO canônica.
        Retorna "" se for conversa/pergunta."""
        try:
            out = self._post(
                [{"role": "system", "content": _ROUTER_PROMPT},
                 {"role": "user", "content": text.strip()}],
                48, temperature=0.0,
            ) or ""
        except Exception as exc:  # noqa: BLE001
            log(f"erro route: {exc}")
            return ""
        mc = re.search(r'"cmd"\s*:\s*"([a-z_]+)"', out)
        if not mc:
            return ""
        cmd = mc.group(1)
        tpl = _ROUTER_TEMPLATES.get(cmd)
        if not tpl:
            return ""     # conversa / cmd desconhecido
        need = _ROUTER_SKILL.get(cmd)
        if need and not self.skills.get(need, True):
            return ""     # skill desligada neste perfil
        ma = re.search(r'"arg"\s*:\s*"([^"]*)"', out)
        arg = (ma.group(1).strip() if ma else "")
        if "{arg}" in tpl:
            if not arg:
                return ""
            if cmd == "forma" and norm(arg) not in _ROUTER_SHAPES:
                return ""   # não inventa forma
            return tpl.format(arg=arg)
        return tpl

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
    if not arr.get("enabled", True):
        return False
    target = norm(arr.get("phrase", "acorda crianca o papai chegou"))
    if SequenceMatcher(None, n, target).ratio() >= float(arr.get("match_threshold", 0.62)):
        return True
    has_papai = "papai" in n or "pape" in n or "papi" in n
    has_chegou = "chegou" in n or "chego" in n
    has_acorda = "acorda" in n or "acordo" in n or "corda" in n
    has_crianca = "crianca" in n or "criança" in n
    return (has_acorda and (has_crianca or has_papai)) or (has_crianca and has_chegou)


def set_paused(paused: bool, *, beep: bool = True) -> None:
    write_control(paused=bool(paused))
    write_app_state(status="PAUSADO" if paused else "OUVINDO", speaking=False)
    log(f"** escuta {'PAUSADA' if paused else 'ATIVA'} **")
    if beep:
        try:
            if paused:
                winsound.Beep(760, 90); winsound.Beep(420, 140)
            else:
                winsound.Beep(520, 90); winsound.Beep(900, 140)
        except RuntimeError:
            pass


def hotkey_listener() -> None:
    """Ctrl+Alt+J e Ctrl+Shift+J (global) pausam/ativam a escuta."""
    u32 = ctypes.windll.user32
    MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x0001, 0x0002, 0x0004, 0x4000
    combos = [(1, MOD_ALT | MOD_CONTROL, "Ctrl+Alt+J"),
              (2, MOD_SHIFT | MOD_CONTROL, "Ctrl+Shift+J")]
    ok = [name for i, mods, name in combos
          if u32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, 0x4A)]
    if not ok:
        log("não consegui registrar nenhum atalho global (Ctrl+Alt+J / Ctrl+Shift+J)")
        return
    log(f"atalho global ativo: {' ou '.join(ok)} pausa/ativa a escuta")
    msg = wt.MSG()
    while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == 0x0312:  # WM_HOTKEY
            try:
                set_paused(not read_control().get("paused", False))
            except Exception as exc:  # noqa: BLE001
                log(f"erro no atalho: {exc}")


def focus_jarvis_app() -> None:
    """Traz a janela JARVIS pra frente (rouba o foco de outro app)."""
    u = ctypes.windll.user32
    hwnd = u.FindWindowW(None, "JARVIS")
    if not hwnd:
        return
    try:
        u.AllowSetForegroundWindow(-1)  # ASFW_ANY
    except Exception:  # noqa: BLE001
        pass
    try:
        fg = u.GetForegroundWindow()
        cur = ctypes.windll.kernel32.GetCurrentThreadId()
        other = u.GetWindowThreadProcessId(fg, 0)
        u.AttachThreadInput(cur, other, True)
        u.ShowWindow(hwnd, 9)                              # SW_RESTORE
        u.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0003)       # HWND_TOPMOST
        u.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0003)       # HWND_NOTOPMOST (não prende)
        u.BringWindowToTop(hwnd)
        u.SetForegroundWindow(hwnd)
        u.AttachThreadInput(cur, other, False)
    except Exception as exc:  # noqa: BLE001
        log(f"focus_jarvis_app: {exc}")


def open_jarvis_app(cfg: dict, *, focus_after: float = 0.0) -> None:
    """Abre o Jarvis App (cérebro holográfico). O .exe tem trava de instância única."""
    ap = cfg.get("app", {})
    if not ap.get("enabled", False):
        return
    exe = ap.get("exe_path", "")
    try:
        if exe and Path(exe).is_file():
            try:
                ctypes.windll.user32.AllowSetForegroundWindow(-1)
            except Exception:  # noqa: BLE001
                pass
            subprocess.Popen([exe], creationflags=0x00000008)  # DETACHED_PROCESS
        else:
            log(f"Jarvis App: exe_path inválido ({exe!r})")
            return
    except Exception as exc:  # noqa: BLE001
        log(f"falha ao abrir o Jarvis App: {exc}")
        return

    def _bring():
        time.sleep(focus_after)
        focus_jarvis_app()

    threading.Thread(target=_bring, daemon=True).start()


def run_arrival(cfg: dict, mouth: Mouth, reason: str) -> None:
    """Frase de chegada, na ordem:
       1) toca a música   2) diz a saudação   3) traz o app pra frente."""
    log(f"** CHEGADA ({reason}) **")
    arr = cfg.get("arrival", {})

    # 1) música (antes de tudo)
    try:
        import spotify
        uri = arr.get("spotify", "")
        if uri:
            spotify.play_uri(uri, cfg)
            log(f"  música: {uri}")
        elif arr.get("spotify_search"):
            spotify.play(arr["spotify_search"], cfg)
    except Exception as exc:  # noqa: BLE001
        log(f"  erro na música da chegada: {exc}")

    time.sleep(float(arr.get("greeting_delay", 1.2)))   # deixa a música começar

    # 2) saudação
    mouth.say(arr.get("greeting") or "Bem-vindo, senhor!")

    # 3) app em primeiro plano
    if cfg.get("app", {}).get("open_on_arrival", True):
        open_jarvis_app(cfg, focus_after=1.0)


def _run_action(action: str, cfg: dict) -> None:
    try:
        if action.startswith(("spotify:track:", "spotify:playlist:", "spotify:album:")):
            import spotify
            spotify.play_uri(action, cfg)
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
    rotate_log(int(cfg.get("perf", {}).get("log_max_kb", 512)))
    log("=" * 50)
    log("Jarvis Voz iniciando (escuta contínua + skills)")

    device = resolve_device(cfg["audio"].get("input_device_match", ""))
    ears = Ears(cfg)
    mouth = Mouth(cfg)
    brain = Brain(cfg)
    mic = Mic(device)
    mic.start()
    skills.build_indexes(cfg)
    brain.warmup()
    brain.start_keepwarm()

    set_paused(False, beep=False)   # começa sempre ouvindo
    write_control(view="brain")     # começa no cérebro (não gruda entre reinícios)
    write_app_state(
        camera_match=cfg.get("app", {}).get("camera_match", "Brio"),
        hand_skeleton=bool(cfg.get("camera", {}).get("hand_skeleton", True)),
    )
    threading.Thread(target=hotkey_listener, daemon=True).start()

    wake_word = norm(cfg["assistant"].get("wake_word", "jarvis"))
    pre_n = max(1, int(float(cfg["audio"].get("pre_roll_seconds", 0.5)) * SR / BLOCK))
    speech_thr = float(cfg["audio"]["speech_level"])
    cooldown = float(cfg["arrival"].get("reactivate_cooldown_seconds", 30))

    if cfg["tts"].get("ready_line"):
        mouth.say(cfg["tts"]["ready_line"])
    log(f'pronto — diga a frase de chegada ou "{wake_word} ..."')

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
            _handle_block(block, ring, mic, ears, mouth, brain, cfg,
                          wake_word, speech_thr, cooldown, st)
        except Exception as exc:  # noqa: BLE001
            log(f"erro no loop (ignorado): {exc!r}")
            try:
                mic.drain()
            except Exception:  # noqa: BLE001
                pass
            ring.clear()


def _handle_block(block, ring, mic, ears, mouth, brain, cfg, wake_word,
                  speech_thr, cooldown, st) -> None:
    if mouth.speaking:
        ring.clear(); return

    # escuta pausada (botão do app ou Ctrl+Alt+J) -> ignora tudo
    if read_control().get("paused", False):
        mic.drain(); ring.clear(); st["pending"] = None
        return

    # confirmação pendente expirou sem resposta?
    p = st["pending"]
    if p and time.monotonic() > p[2]:
        log("confirmação expirou (sem resposta)")
        st["pending"] = None

    ring.append(block)

    if rms(block) <= speech_thr:
        return

    audio = capture_utterance(mic, cfg, list(ring))
    ring.clear()
    min_len = float(cfg["audio"].get("min_utterance_seconds", 0.35))
    if audio is None or len(audio) < SR * min_len:
        return

    # estágio 1: modelo minúsculo filtra TODA fala (barato)
    raw_w = ears.hear_wake(audio)
    n_w = norm(raw_w)
    if not n_w:
        return

    triggered = (st["pending"] is not None
                 or is_arrival_phrase(n_w, cfg)
                 or strip_wake_word(raw_w, n_w, wake_word) is not None)
    if not triggered:
        mic.drain()
        return

    # estágio 2: só agora roda o modelo bom
    raw = ears.hear_command(audio)
    n = norm(raw)
    if not n:
        raw, n = raw_w, n_w
    log(f"ouvi: {raw!r}")

    # -------- resposta a uma confirmação pendente --------
    # É SEMPRE consumida pela próxima fala: sim -> executa; qualquer outra
    # coisa -> cancela. Nunca fica presa.
    if st["pending"]:
        _question, do, _dl = st["pending"]
        st["pending"] = None
        ans = strip_wake_word(raw, n, wake_word)          # "jarvis não" -> "não"
        ans = norm(ans) if ans else n
        if _is_affirm(ans) and not _is_negate(ans):
            log("  confirmado")
            try:
                followup = do()
            except Exception as exc:  # noqa: BLE001
                log(f"erro na ação confirmada: {exc}"); followup = "Deu erro, senhor."
            mouth.say(followup or "Feito, senhor.")
        else:
            log(f"  confirmação não foi 'sim' ({ans!r}) — cancelado")
            mouth.say("Cancelado, senhor.")
        mic.drain()
        return

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

    # Whisper às vezes alucina uma cauda ("... Jarvis. Jaris, cia um cubão...").
    # Um comando real é UMA frase curta — corta na 1ª pontuação forte se
    # aparecer "jarvis" de novo ou várias frases.
    if norm(payload).count(" jarvis") >= 1 or payload.count(".") >= 2:
        payload = re.split(r"[.!?]", payload, 1)[0].strip() or payload

    if not norm(payload):
        if cfg.get("app", {}).get("open_on_wake_word", False):
            open_jarvis_app(cfg, focus_after=1.6)
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
        st["pending"] = (question, do, time.monotonic() + CONFIRM_TIMEOUT)
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
