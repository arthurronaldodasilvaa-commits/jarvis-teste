#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
remote.py — controle do Jarvis pelo celular, na rede local (Onda 1).

O celular vira um microfone + fone + telinha. O PC continua sendo o cérebro.
  - o daemon sobe um servidor HTTPS local (só na rede de casa)
  - o celular abre a página, aperta pra falar, o áudio vai pro PC
  - o PC transcreve (Whisper que já está carregado), executa (skills.dispatch),
    responde com o Piper e devolve o áudio pro fone do senhor

Config em  config.toml  ->  [remote]
    enabled = true
    port    = 8765
    token   = ""        # vazio = gera um e salva em voice/remote_token.txt
    bind    = "lan"      # "lan" (rede de casa) | "localhost" (só este PC)

Segurança: só rede local, token obrigatório em toda requisição, comandos
destrutivos (desligar/reiniciar/bloquear) recusados pelo celular.
"""
from __future__ import annotations

import io
import json
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from common import HERE, log, norm

CNW = 0x08000000
_TTS_DIR = HERE / "_remote_tts"
_PAGE = HERE / "remote_page.html"
_CERT = HERE / "remote_cert.pem"
_KEY = HERE / "remote_key.pem"
_CERTIP = HERE / "remote_cert.ip"
_TOKENF = HERE / "remote_token.txt"

_CTX: dict = {}          # {ears, mouth, brain, cfg, dispatch, token}
_recent: deque = deque(maxlen=12)
_lock = threading.Lock()
_BLOCK = re.compile(r"\b(deslig\w*|desligar|reinici\w*|reiniciar|suspend\w*|hibern\w*|"
                    r"bloqueia?r?\s+a\s+tela|travar?\s+a\s+tela|formata\w*)\b")


# ---------------------------------------------------------------- rede / cert
def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


def _openssl() -> str | None:
    for c in (shutil.which("openssl"),
              r"C:\Program Files\Git\usr\bin\openssl.exe",
              r"C:\Program Files\Git\mingw64\bin\openssl.exe",
              r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe"):
        if c and Path(c).is_file():
            return c
    return None


def _ensure_cert(ip: str) -> bool:
    """Gera um certificado autoassinado pro IP atual (self-signed). Devolve
    True se HTTPS está disponível."""
    if _CERT.is_file() and _KEY.is_file() and _CERTIP.is_file():
        try:
            if _CERTIP.read_text().strip() == ip:
                return True
        except OSError:
            pass
    ossl = _openssl()
    if not ossl:
        log("remote: openssl não encontrado — vai subir em HTTP (use a flag do Chrome no celular)")
        return False
    try:
        subprocess.run(
            [ossl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(_KEY), "-out", str(_CERT), "-days", "3650",
             "-subj", "/CN=Jarvis",
             "-addext", f"subjectAltName=IP:{ip},IP:127.0.0.1,DNS:localhost"],
            timeout=30, creationflags=CNW,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        _CERTIP.write_text(ip, encoding="utf-8")
        log(f"remote: certificado gerado para {ip}")
        return True
    except Exception as exc:  # noqa: BLE001
        log(f"remote: falha ao gerar certificado ({exc}) — HTTP")
        return False


def _token(cfg: dict) -> str:
    t = str(cfg.get("remote", {}).get("token", "")).strip()
    if t:
        return t
    try:
        if _TOKENF.is_file():
            t = _TOKENF.read_text(encoding="utf-8").strip()
            if t:
                return t
    except OSError:
        pass
    t = secrets.token_hex(3)          # 6 hex chars, fácil de digitar
    try:
        _TOKENF.write_text(t, encoding="utf-8")
    except OSError:
        pass
    return t


# ---------------------------------------------------------------- áudio
def _decode_audio(blob: bytes):
    """webm/opus (ou ogg/wav) do celular -> numpy float32 mono 16 kHz."""
    import av
    import numpy as np
    try:
        cont = av.open(io.BytesIO(blob))
        rs = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=16000)
        parts = []
        for frame in cont.decode(audio=0):
            for rf in rs.resample(frame):
                parts.append(rf.to_ndarray().reshape(-1))
        cont.close()
        if not parts:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(parts).astype(np.float32) / 32768.0
    except Exception as exc:  # noqa: BLE001
        log(f"remote: decode falhou ({exc})")
        import numpy as np
        return np.zeros(0, dtype=np.float32)


# ---------------------------------------------------------------- comando
def _flooding() -> bool:
    now = time.monotonic()
    n = sum(1 for t in _recent if now - t < 20)
    _recent.append(now)
    return n >= 6


def _run(text: str) -> tuple[str, str]:
    """Roda o comando. Devolve (fala_de_resposta, id_do_wav|'')."""
    text = (text or "").strip()
    if not text:
        return "Não entendi, senhor.", ""
    if _BLOCK.search(norm(text)):
        return "Isso eu não faço pelo celular, senhor. Só aqui no PC.", ""

    ctx = _CTX
    said: list[str] = []
    try:
        res = ctx["dispatch"](text, ctx["cfg"], lambda s: s and said.append(str(s)), ctx["brain"])
    except Exception as exc:  # noqa: BLE001
        log(f"remote dispatch: {exc!r}")
        return "Tive um erro ao executar isso, senhor.", ""

    if getattr(res, "to_llm", ""):
        try:
            reply = ctx["brain"].ask(res.to_llm)
        except Exception:  # noqa: BLE001
            reply = "Meu raciocínio não respondeu agora, senhor."
    elif getattr(res, "confirm", None):
        reply = "Isso precisa de confirmação, senhor — faça pelo PC."
    elif getattr(res, "speak", ""):
        reply = res.speak
    else:
        reply = ""
    full = " ".join([s for s in said if s and s != reply] + ([reply] if reply else [])).strip()
    full = full or "Feito, senhor."

    wav_id = ""
    try:
        _TTS_DIR.mkdir(exist_ok=True)
        for old in sorted(_TTS_DIR.glob("*.wav"))[:-6]:
            old.unlink(missing_ok=True)
        wid = secrets.token_hex(4)
        if ctx["mouth"].synth_file(full, _TTS_DIR / f"{wid}.wav"):
            wav_id = wid
    except Exception as exc:  # noqa: BLE001
        log(f"remote synth: {exc}")
    return full, wav_id


# ---------------------------------------------------------------- HTTP
class _H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # noqa: ARG002
        pass

    def _ok(self):
        q = self.path.split("?", 1)[1] if "?" in self.path else ""
        tok = dict(p.split("=", 1) for p in q.split("&") if "=" in p).get("k", "")
        tok = tok or self.headers.get("X-Jarvis-Token", "")
        return secrets.compare_digest(tok, _CTX.get("token", "\0"))

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:  # noqa: BLE001
            pass

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route == "/health":
            return self._json(200, {"ok": True, "name": "Jarvis"})
        if not self._ok():
            return self._send(403, b"<h1>Chave errada</h1>", "text/html; charset=utf-8")
        if route == "/" or route == "/index.html":
            try:
                html = _PAGE.read_bytes()
            except OSError:
                html = b"<h1>Jarvis</h1><p>remote_page.html nao encontrado.</p>"
            return self._send(200, html, "text/html; charset=utf-8")
        if route == "/state":
            try:
                from common import APP_STATE_FILE
                st = json.loads(APP_STATE_FILE.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                st = {}
            return self._json(200, {"status": st.get("status", ""), "phase": st.get("phase", ""),
                                    "speaking": st.get("speaking", False),
                                    "track": st.get("track", {}), "weather": st.get("weather", "")})
        if route.startswith("/tts/") and route.endswith(".wav"):
            wid = re.sub(r"[^0-9a-f]", "", route[5:-4])
            p = _TTS_DIR / f"{wid}.wav"
            if p.is_file():
                return self._send(200, p.read_bytes(), "audio/wav")
            return self._send(404, b"", "audio/wav")
        return self._send(404, b"nao existe")

    def do_POST(self):
        route = self.path.split("?", 1)[0]
        if not self._ok():
            return self._json(403, {"error": "chave errada"})
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            n = 0
        body = self.rfile.read(n) if n else b""

        if _flooding():
            return self._json(429, {"error": "muitos pedidos seguidos"})
        if not _lock.acquire(timeout=0.1):
            return self._json(429, {"error": "ocupado, tente de novo"})
        try:
            if route == "/listen":
                if len(body) < 800:
                    return self._json(200, {"heard": "", "reply": "Não ouvi nada, senhor.", "audio": ""})
                pcm = _decode_audio(body)
                import numpy as np
                if pcm.size < 16000 * 0.4:
                    return self._json(200, {"heard": "", "reply": "Ficou curto, senhor.", "audio": ""})
                try:
                    heard = _CTX["ears"].hear_command(np.ascontiguousarray(pcm)).strip()
                except Exception as exc:  # noqa: BLE001
                    log(f"remote hear: {exc}")
                    heard = ""
                heard = re.sub(r"(?i)^\s*jarvis[\s,.:;!?-]*", "", heard).strip()
                if not heard:
                    return self._json(200, {"heard": "", "reply": "Não entendi, senhor.", "audio": ""})
                log(f"remote: ouviu {heard!r}")
                reply, wid = _run(heard)
                return self._json(200, {"heard": heard, "reply": reply,
                                        "audio": f"/tts/{wid}.wav?k={_CTX['token']}" if wid else ""})
            if route == "/say":
                try:
                    txt = json.loads(body or b"{}").get("text", "")
                except ValueError:
                    txt = ""
                reply, wid = _run(txt)
                return self._json(200, {"heard": txt, "reply": reply,
                                        "audio": f"/tts/{wid}.wav?k={_CTX['token']}" if wid else ""})
            return self._json(404, {"error": "nao existe"})
        finally:
            _lock.release()


# ---------------------------------------------------------------- start
_server = None
_pair_url = ""


def pairing_url() -> str:
    return _pair_url


def pairing_qr_datauri() -> str:
    """QR do link de pareamento como data: URI de SVG (pra mostrar no app)."""
    if not _pair_url:
        return ""
    try:
        import base64

        import qrcode
        from qrcode.image.svg import SvgPathImage
        img = qrcode.make(_pair_url, image_factory=SvgPathImage, box_size=1, border=1,
                          error_correction=qrcode.constants.ERROR_CORRECT_M)
        buf = io.BytesIO()
        img.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return "data:image/svg+xml;base64," + b64
    except Exception as exc:  # noqa: BLE001
        log(f"remote: QR falhou ({exc})")
        return ""


def start(cfg: dict, ears, mouth, brain, dispatch) -> None:
    global _pair_url
    rc = cfg.get("remote", {})
    if not rc.get("enabled", False):
        return
    port = int(rc.get("port", 8765))
    bind_lan = str(rc.get("bind", "lan")).lower() != "localhost"
    ip = lan_ip() if bind_lan else "127.0.0.1"
    host = "0.0.0.0" if bind_lan else "127.0.0.1"
    tok = _token(cfg)
    _CTX.update(ears=ears, mouth=mouth, brain=brain, cfg=cfg, dispatch=dispatch, token=tok)
    _TTS_DIR.mkdir(exist_ok=True)

    https = _ensure_cert(ip) if bind_lan else False
    scheme = "https" if https else "http"
    _pair_url = f"{scheme}://{ip}:{port}/?k={tok}"

    def _serve():
        global _server
        try:
            _server = ThreadingHTTPServer((host, port), _H)
            if https:
                sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                sctx.load_cert_chain(str(_CERT), str(_KEY))
                _server.socket = sctx.wrap_socket(_server.socket, server_side=True)
            log(f"** controle remoto: {_pair_url} **")
            _server.serve_forever()
        except Exception as exc:  # noqa: BLE001
            log(f"remote: servidor caiu ({exc})")

    threading.Thread(target=_serve, daemon=True).start()
