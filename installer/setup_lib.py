#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
setup_lib.py — lógica do instalador do Jarvis (sem interface).

O jarvis_setup.py (janela) só chama estas funções. Tudo aqui é testável
sozinho:  python setup_lib.py  imprime um diagnóstico da máquina.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import string
import subprocess
import sys
import time
from pathlib import Path

CNW = 0x08000000  # CREATE_NO_WINDOW — não pisca janela de console

# --------------------------------------------------------------------------
# perfis  (profiles/<nome>.toml no payload)
# --------------------------------------------------------------------------
def list_profiles(voice_dir: Path) -> list[dict]:
    """[{name, label}] lendo o cabeçalho '# Perfil: <Nome> | <desc>'."""
    pdir = voice_dir / "profiles"
    out = []
    if pdir.is_dir():
        for p in sorted(pdir.glob("*.toml")):
            label = p.stem.capitalize()
            try:
                m = re.search(r"#\s*Perfil:\s*(.+)", p.read_text(encoding="utf-8")[:400])
                if m:
                    label = m.group(1).strip().rstrip(".")[:80]
            except OSError:
                pass
            out.append({"name": p.stem, "label": label})
    return out


# --------------------------------------------------------------------------
# discos
# --------------------------------------------------------------------------
def list_drives() -> list[dict]:
    """Discos fixos com espaço livre. [{letter, label, free_gb, total_gb}]"""
    out = []
    GetVolumeInformation = ctypes.windll.kernel32.GetVolumeInformationW
    DRIVE_FIXED = 3
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if ctypes.windll.kernel32.GetDriveTypeW(root) != DRIVE_FIXED:
            continue
        try:
            total, _used, free = shutil.disk_usage(root)
        except OSError:
            continue
        if total == 0:
            continue
        buf = ctypes.create_unicode_buffer(261)
        try:
            GetVolumeInformation(root, buf, 261, None, None, None, None, 0)
        except Exception:  # noqa: BLE001
            pass
        out.append({
            "letter": letter,
            "root": root,
            "label": (buf.value or "Disco local"),
            "free_gb": free / 1024**3,
            "total_gb": total / 1024**3,
        })
    return out


def recommended_drive(drives: list[dict], need_gb: float = 6.0) -> dict | None:
    ok = [d for d in drives if d["free_gb"] >= need_gb]
    if not ok:
        return None
    # prefere um disco que não seja o C: (deixa o sistema livre), senão o C:
    non_c = [d for d in ok if d["letter"] != "C"]
    pool = non_c or ok
    return max(pool, key=lambda d: d["free_gb"])


# --------------------------------------------------------------------------
# powershell helper
# --------------------------------------------------------------------------
def _ps(script: str, timeout: float = 20) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=timeout, creationflags=CNW,
        )
        return (r.stdout or "").strip()
    except Exception:  # noqa: BLE001
        return ""


# --------------------------------------------------------------------------
# microfones  (usa sounddevice se disponível; senão powershell)
# --------------------------------------------------------------------------
def list_mics() -> list[dict]:
    """[{index, name}] — entradas de áudio."""
    try:
        import sounddevice as sd

        seen, out = set(), []
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0 and d["name"] not in seen:
                seen.add(d["name"])
                out.append({"index": i, "name": d["name"]})
        if out:
            return out
    except Exception:  # noqa: BLE001
        pass
    raw = _ps("Get-CimInstance Win32_PnPEntity | "
              "Where-Object { $_.PNPClass -eq 'AudioEndpoint' -or $_.Service -eq 'usbaudio' } | "
              "Select-Object -ExpandProperty Name")
    return [{"index": -1, "name": n.strip()} for n in raw.splitlines() if n.strip()]


def mic_peak(device_index: int | None, seconds: float = 2.0) -> float:
    """Grava alguns segundos e devolve o pico (0..1). Pra barra de teste."""
    try:
        import numpy as np
        import sounddevice as sd

        rec = sd.rec(int(seconds * 16000), samplerate=16000, channels=1,
                     dtype="float32", device=device_index)
        sd.wait()
        return float(np.abs(rec).max())
    except Exception:  # noqa: BLE001
        return -1.0


# --------------------------------------------------------------------------
# câmeras
# --------------------------------------------------------------------------
def list_cameras() -> list[str]:
    raw = _ps("Get-CimInstance Win32_PnPEntity | "
              "Where-Object { $_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image' -or "
              "$_.Service -eq 'usbvideo' } | Select-Object -ExpandProperty Name")
    cams = [n.strip() for n in raw.splitlines() if n.strip()]
    # remove duplicatas mantendo ordem
    return list(dict.fromkeys(cams))


# --------------------------------------------------------------------------
# vozes (SAPI)
# --------------------------------------------------------------------------
def list_voices() -> list[dict]:
    """[{name, culture, pt}] — vozes instaladas, pt-BR primeiro."""
    raw = _ps(
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.GetInstalledVoices() | ForEach-Object { "
        "  $i = $_.VoiceInfo; "
        "  [pscustomobject]@{ name=$i.Name; culture=$i.Culture.Name } } | ConvertTo-Json -Compress"
    )
    try:
        data = json.loads(raw) if raw else []
    except ValueError:
        data = []
    if isinstance(data, dict):
        data = [data]
    out = []
    for v in data:
        cult = (v.get("culture") or "")
        out.append({"name": v.get("name", ""), "culture": cult,
                    "pt": cult.lower().startswith("pt")})
    out.sort(key=lambda v: (not v["pt"], v["name"]))
    return out


def speak_sample(voice_name: str,
                 text: str = "Bom dia, senhor. Aqui é o Jarvis. Assim que eu vou falar com o senhor.") -> None:
    safe = voice_name.replace("'", "''")
    body = text.replace("'", "''")
    _ps(f"Add-Type -AssemblyName System.Speech; "
        f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"try {{ $s.SelectVoice('{safe}') }} catch {{}}; "
        f"$s.Rate = 0; $s.Speak('{body}')", timeout=15)


# --------------------------------------------------------------------------
# Ollama (o "cérebro")
# --------------------------------------------------------------------------
def find_ollama() -> str | None:
    cand = [
        shutil.which("ollama"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
    ]
    for c in cand:
        if c and Path(c).is_file():
            return c
    return None


def ollama_running() -> bool:
    exe = find_ollama()
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "list"], capture_output=True, text=True,
                           timeout=8, creationflags=CNW)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def run_ollama_installer(installer_path: str) -> subprocess.Popen | None:
    """Abre o instalador oficial do Ollama. O usuário clica 'Install'."""
    p = Path(installer_path)
    if not p.is_file():
        return None
    try:
        return subprocess.Popen([str(p)])
    except Exception:  # noqa: BLE001
        return None


def has_model(model: str) -> bool:
    exe = find_ollama()
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "list"], capture_output=True, text=True,
                           timeout=10, creationflags=CNW)
        base = model.split(":")[0]
        return base in (r.stdout or "")
    except Exception:  # noqa: BLE001
        return False


def ollama_pull(model: str, on_line=None) -> bool:
    """Baixa o modelo. on_line(str) recebe cada linha de progresso."""
    exe = find_ollama()
    if not exe:
        return False
    try:
        proc = subprocess.Popen([exe, "pull", model], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1,
                                creationflags=CNW)
    except Exception as exc:  # noqa: BLE001
        if on_line:
            on_line(f"erro: {exc}")
        return False
    for line in proc.stdout:  # type: ignore[union-attr]
        line = line.rstrip()
        if line and on_line:
            on_line(line)
    proc.wait()
    return proc.returncode == 0


def start_ollama_serve() -> None:
    exe = find_ollama()
    if exe:
        try:
            subprocess.Popen([exe, "serve"], creationflags=CNW)
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------
# instalação dos arquivos
# --------------------------------------------------------------------------
def copy_payload(src: Path, dest: Path, on_progress=None) -> None:
    """Copia src/* -> dest/ com callback de progresso (0..1)."""
    files = [p for p in src.rglob("*") if p.is_file()]
    total = len(files) or 1
    for i, f in enumerate(files, 1):
        rel = f.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        if on_progress:
            on_progress(i / total, str(rel))


_TOML_KEYS = {
    "input_device_match": "audio",
    "camera_match": ("app", "camera"),   # aparece em [app] e [camera]? só [app]
    "sapi_voice": "tts",
    "active": "profile",
}


def patch_config(text: str, changes: dict[str, str]) -> str:
    """Substitui  chave = "..."  no config.toml, preservando o resto.
    changes: {"input_device_match": "Brio", "sapi_voice": "...", ...}"""
    for key, val in changes.items():
        if val is None:
            continue
        v = str(val).replace("\\", "\\\\").replace('"', '\\"')
        pat = re.compile(rf'^(\s*{re.escape(key)}\s*=\s*)".*?"(\s*(?:#.*)?)$', re.M)
        # replacement como função: re.sub NÃO processa as barras invertidas de v
        text = pat.sub(lambda m, v=v: f'{m.group(1)}"{v}"{m.group(2)}', text, count=1)
    return text


def set_whisper_paths(text: str, models_dir: Path) -> str:
    tiny = (models_dir / "faster-whisper-tiny").as_posix()
    small = (models_dir / "faster-whisper-small").as_posix()
    if (models_dir / "faster-whisper-tiny").is_dir():
        text = patch_config(text, {"wake_model": tiny})
    if (models_dir / "faster-whisper-small").is_dir():
        text = patch_config(text, {"command_model": small})
    return text


def make_shortcut(lnk_path: Path, target: str, *, args: str = "",
                  workdir: str = "", icon: str = "") -> bool:
    lnk_path.parent.mkdir(parents=True, exist_ok=True)
    ps = (
        f"$w = New-Object -ComObject WScript.Shell; "
        f"$s = $w.CreateShortcut('{lnk_path}'); "
        f"$s.TargetPath = '{target}'; "
        f"$s.Arguments = '{args}'; "
        f"$s.WorkingDirectory = '{workdir or Path(target).parent}'; "
        + (f"$s.IconLocation = '{icon}'; " if icon else "")
        + "$s.Save()"
    )
    _ps(ps, timeout=15)
    return lnk_path.is_file()


def startup_dir() -> Path:
    return Path(os.path.expandvars(
        r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))


def start_menu_dir() -> Path:
    return Path(os.path.expandvars(
        r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"))


LAUNCHER_VBS = r'''' Inicia o Jarvis (voz oculta + aplicativo). Gerado pelo instalador.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Q = Chr(34)
base = "__BASE__"
voiceExe = base & "\voice\JarvisVoice.exe"
If fso.FileExists(voiceExe) Then
  sh.Run Q & voiceExe & Q, 0, False
End If
WScript.Sleep 1500
appExe = base & "\jarvis-app\JarvisApp.exe"
If fso.FileExists(appExe) Then
  sh.Run Q & appExe & Q, 1, False
End If
'''


def write_launcher(base: Path) -> Path:
    vbs = base / "iniciar_jarvis.vbs"
    vbs.write_text(LAUNCHER_VBS.replace("__BASE__", str(base)), encoding="utf-8")
    return vbs


# --------------------------------------------------------------------------
def machine_report() -> str:
    L = []
    L.append("=== DISCOS ===")
    for d in list_drives():
        L.append(f"  {d['letter']}:  {d['label']:<20}  livre {d['free_gb']:.0f} GB / {d['total_gb']:.0f} GB")
    rec = recommended_drive(list_drives())
    L.append(f"  -> recomendado: {rec['letter'] if rec else '(nenhum com espaço)'}")
    L.append("=== MICROFONES ===")
    for m in list_mics():
        L.append(f"  [{m['index']}] {m['name']}")
    L.append("=== CÂMERAS ===")
    for c in list_cameras() or ["(nenhuma)"]:
        L.append(f"  {c}")
    L.append("=== VOZES ===")
    for v in list_voices():
        L.append(f"  {'*' if v['pt'] else ' '} {v['name']}  ({v['culture']})")
    L.append("=== OLLAMA ===")
    L.append(f"  instalado: {find_ollama() or 'NÃO'}")
    L.append(f"  rodando:   {ollama_running()}")
    return "\n".join(L)


if __name__ == "__main__":
    print(machine_report())
