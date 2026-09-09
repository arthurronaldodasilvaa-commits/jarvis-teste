#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
skills.py — tudo que o Jarvis sabe fazer.

O loop principal (jarvis_voice.py) chama `dispatch(raw_text, cfg, speak, brain)`
quando você fala "jarvis <alguma coisa>". Retorna um Result.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote_plus

import spotify
from common import HERE, combo, log, norm, paste_text, tap, VK, write_app_state, write_control

CNW = 0x08000000  # CREATE_NO_WINDOW


# --------------------------------------------------------------------------
@dataclass
class Result:
    speak: str = ""
    confirm: tuple | None = None          # (pergunta:str, do:callable-> str|None)
    to_llm: str = ""                      # se preenchido, o loop manda pro LLM
    stop: bool = False


# --------------------------------------------------------------------------
# índices (jogos da Steam + atalhos do Menu Iniciar)
# --------------------------------------------------------------------------
_STEAM_LIBS = [
    r"C:\Program Files (x86)\Steam\steamapps",
    r"F:\SteamLibrary\steamapps",
    r"E:\SteamLibrary\steamapps",
    r"D:\SteamLibrary\steamapps",
]
_SKIP_GAMES = {"steamworks common redistributables", "steam linux runtime"}

# formas holográficas que a câmera sabe criar
_SHAPES = {
    "cubo": "cube", "quadrado": "cube", "caixa": "cube", "bloco": "cube",
    "esfera": "sphere", "bola": "sphere", "globo": "sphere", "circulo": "sphere",
    "piramide": "pyramid", "pirâmide": "pyramid",
    "cone": "cone", "sorvete": "cone",
    "cilindro": "cylinder", "tubo": "cylinder", "lata": "cylinder",
    "toro": "torus", "toroide": "torus", "donut": "torus", "rosquinha": "torus",
    "rosca": "torus", "anel": "torus", "argola": "torus",
    "octaedro": "octahedron", "diamante": "octahedron", "losango": "octahedron",
    "prisma": "prism", "hexagono": "prism", "hexágono": "prism",
}

_games: dict[str, str] = {}      # nome_normalizado -> appid
_lnks: dict[str, str] = {}       # nome_normalizado -> caminho .lnk


def build_indexes() -> None:
    _games.clear()
    _lnks.clear()
    for lib in _STEAM_LIBS:
        p = Path(lib)
        if not p.is_dir():
            continue
        for acf in p.glob("appmanifest_*.acf"):
            try:
                txt = acf.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            mid = re.search(r'"appid"\s+"(\d+)"', txt)
            mnm = re.search(r'"name"\s+"([^"]+)"', txt)
            if mid and mnm:
                name = mnm.group(1)
                if norm(name) in _SKIP_GAMES:
                    continue
                _games[norm(name)] = mid.group(1)
    menus = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    ]
    for m in menus:
        mp = Path(m)
        if not mp.is_dir():
            continue
        for lnk in mp.rglob("*.lnk"):
            key = norm(lnk.stem)
            if key and key not in _lnks:
                _lnks[key] = str(lnk)
    log(f"índices: {len(_games)} jogos Steam, {len(_lnks)} atalhos do Menu Iniciar")


def _fuzzy_pick(spoken: str, table: dict[str, str]) -> tuple[str, str, float] | None:
    t = norm(spoken)
    if not t:
        return None
    best_key, best_val, best_score = None, None, 0.0
    for key, val in table.items():
        if t in key or key in t:
            return key, val, 1.0
        sc = SequenceMatcher(None, t, key).ratio()
        # bônus se todas as palavras faladas aparecem na chave
        if all(w in key for w in t.split()):
            sc = max(sc, 0.85)
        if sc > best_score:
            best_key, best_val, best_score = key, val, sc
    if best_score >= 0.6:
        return best_key, best_val, best_score
    return None


# --------------------------------------------------------------------------
# resolução de "abrir <alvo>"
# --------------------------------------------------------------------------
def _open_app_value(value: str) -> None:
    kind, _, rest = value.partition(":")
    if kind.lower() in ("url", "run"):
        rest = rest.strip()
        if rest.startswith(("http://", "https://")):
            webbrowser.open(rest)
        else:
            os.startfile(rest)  # noqa: S606
    elif value.startswith(("http://", "https://")):
        webbrowser.open(value)
    else:
        os.startfile(value)  # noqa: S606


def open_target(spoken: str, cfg: dict, *, prefer_game: bool = False) -> Result:
    apps = {norm(k): v for k, v in cfg.get("apps", {}).items()}

    game = _fuzzy_pick(spoken, _games)
    if prefer_game and game:
        os.startfile(f"steam://rungameid/{game[1]}")  # noqa: S606
        return Result(speak=f"Abrindo {game[0]}, senhor.")

    app = _fuzzy_pick(spoken, apps)
    if app and (not game or app[2] >= game[2]):
        _open_app_value(app[1])
        return Result(speak=f"Abrindo {app[0]}, senhor.")

    if game:
        os.startfile(f"steam://rungameid/{game[1]}")  # noqa: S606
        return Result(speak=f"Abrindo {game[0]}, senhor.")

    lnk = _fuzzy_pick(spoken, _lnks)
    if lnk:
        os.startfile(lnk[1])  # noqa: S606
        return Result(speak=f"Abrindo {lnk[0]}, senhor.")

    webbrowser.open("https://www.google.com/search?q=" + quote_plus(spoken))
    return Result(speak=f"Não achei {spoken} instalado, senhor. Procurei na web.")


# --------------------------------------------------------------------------
# escrever / digitar
# --------------------------------------------------------------------------
def type_verbatim(text: str) -> Result:
    paste_text(text)
    return Result(speak="")


def write_document(topic: str, cfg: dict, speak, brain) -> Result:
    speak(f"Redigindo sobre {topic}, senhor. Só um momento.")
    body = brain.compose(
        f"Escreva um texto em português do Brasil sobre: {topic}. "
        f"Texto corrido, de 2 a 4 parágrafos, sem título, sem listas, sem marcadores.",
        num_predict=int(cfg["assistant"].get("compose_num_predict", 600)),
    )
    os.startfile("notepad")  # noqa: S606
    time.sleep(1.4)
    paste_text(body)
    return Result(speak="Pronto, senhor. O texto está no Bloco de Notas.")


# --------------------------------------------------------------------------
# sistema
# --------------------------------------------------------------------------
def _run(*args: str) -> None:
    subprocess.run(list(args), creationflags=CNW, timeout=15)


def _lock() -> None:
    __import__("ctypes").windll.user32.LockWorkStation()


def _suspend() -> None:
    _run("rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0")


def _shutdown(delay: int = 30):
    def do():
        _run("shutdown", "/s", "/t", str(delay))
        return f"Desligando em {delay} segundos, senhor. Diga 'jarvis cancelar' para abortar."
    return do


def _restart(delay: int = 30):
    def do():
        _run("shutdown", "/r", "/t", str(delay))
        return f"Reiniciando em {delay} segundos, senhor."
    return do


def _append(fname: str, text: str) -> None:
    with open(HERE / fname, "a", encoding="utf-8") as fh:
        fh.write(f"- [{datetime.now():%Y-%m-%d %H:%M}] {text}\n")


# --------------------------------------------------------------------------
# dispatch
# --------------------------------------------------------------------------
STOP_WORDS = ("para", "parar", "chega", "obrigado", "obrigada", "valeu",
              "tchau", "pode ir", "encerra", "silencio", "cala a boca", "cancela")


def dispatch(raw: str, cfg: dict, speak, brain) -> Result:
    t = norm(raw)
    dz = cfg.get("danger", {})

    if not t:
        return Result(speak=cfg["assistant"].get("attention_reply", "Pois não, senhor?"))

    if t in STOP_WORDS or (len(t.split()) <= 3 and any(w in t for w in STOP_WORDS)):
        # exceção: "cancela ..." de desligamento tratado abaixo
        if "cancel" not in t:
            return Result(speak="Às ordens, senhor.", stop=True)

    # --- pausar a escuta ("modo cinema") ---
    if re.search(r"\bmod[eo]s?\s+(de\s+)?cinema\b|\bmod[eo]s?\s+filme\b|\bmod[eo]s?\s+soneca\b|"
                 r"\bmod[eo]s?\s+silencio\b|para de (me )?(ouvir|escutar|prestar atencao)|"
                 r"pausa\w*\s+(a\s+)?escuta|se desliga|desativa\w*\s+(voce|a escuta)|"
                 r"nao me (escuta|ouve)|fica quieto|fica em silencio", t):
        write_control(paused=True)
        write_app_state(status="PAUSADO", speaking=False)
        return Result(speak="Escuta pausada, senhor. Aperte o botão no aplicativo ou "
                            "Control Alt J para me chamar de volta.")

    # --- câmera do app (troca a tela: cérebro <-> webcam) ---
    if re.search(r"\b(ativa\w*|liga\w*|abr\w*|mostra\w*|inicia\w*)\s+(a\s+)?c[aâe]mera\b|"
                 r"\bmodo c[aâe]mera\b|\bvis[aã]o (da\s+)?c[aâe]mera\b|\bliga\w* a webcam\b", t):
        write_control(view="camera")
        return Result(speak="")
    if re.search(r"\b(desativa\w*|desliga\w*|fecha\w*|para\w*|tira|encerra\w*)\s+(a\s+)?c[aâe]mera\b|"
                 r"\bvolta\w*\s+(pro|para o|ao)\s+cerebro\b|\bmodo cerebro\b|\bfecha\w* a webcam\b", t):
        write_control(view="brain")
        return Result(speak="")

    # --- criar / limpar hologramas na tela da câmera ---
    if re.search(r"\b(limpa\w*|apaga\w*|remove\w*|tira|deleta\w*|zera)\s+"
                 r"(tudo|os?\s+holograma\w*|as?\s+forma\w*|a\s+tela)\b", t):
        write_control(holo={"action": "clear", "n": int(time.time() * 1000)})
        return Result(speak="")

    _mk = ("cria\\w*|criar|faz\\w*|adiciona\\w*|gera\\w*|desenha\\w*|projeta\\w*|"
           "poe|monta\\w*|mostra\\w*|exibe\\w*|abre\\w*|traz\\w*")
    _trig = None
    if re.search(rf"\b(?:{_mk})\b.*\btriangulo\s+retangulo\b|\btriangulo retangulo\b", t):
        _trig = "triangulo"
    elif re.search(rf"\b(?:{_mk})\b.*\b(tabela|quadro).*(angulos?\s+notave|angulos? notave)|"
                   r"\bangulos?\s+notave\w*\b", t):
        _trig = "tabela_angulos"
    elif re.search(rf"\b(?:{_mk})\b.*\brela\w+\s+trigonom|\btabela\s+de\s+rela\w+\b|"
                   r"\brela\w+\s+trigonometrica\w*\b", t):
        _trig = "tabela_relacoes"
    if _trig:
        write_control(holo={"action": "add", "shape": _trig, "n": int(time.time() * 1000)})
        return Result(speak="")

    m = re.search(rf"\b(?:{_mk})\s+"
                  r"(?:um\s+|uma\s+|o\s+|a\s+|mais\s+um\s+|outro\s+|outra\s+)?"
                  r"(?:holograma\s+(?:de\s+)?(?:um\s+|uma\s+)?|forma\s+de\s+(?:um\s+|uma\s+)?)?([a-zç]+)", t)
    if m:
        shape = _SHAPES.get(m.group(1)) or _SHAPES.get(norm(m.group(1)))
        if shape:
            write_control(holo={"action": "add", "shape": shape, "n": int(time.time() * 1000)})
            return Result(speak="")

    # --- cancelar desligamento/reinício ---
    if re.search(r"cancela\w*.*(deslig|reinic|reinici)", t) or re.fullmatch(r"cancela\w*", t):
        _run("shutdown", "/a")
        return Result(speak="Cancelei, senhor.")

    # --- hora / data ---
    if re.search(r"\b(que horas?|as horas?|horario agora|que hora e|me diz as horas|horas sao)\b", t):
        now = datetime.now()
        return Result(speak=f"São {now.hour} horas e {now.minute} minutos, senhor.")
    if re.search(r"\b(que dia (e )?hoje|data de hoje|dia da semana|hoje e dia)\b", t):
        dias = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                "sexta-feira", "sábado", "domingo"]
        meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                 "agosto", "setembro", "outubro", "novembro", "dezembro"]
        n = datetime.now()
        return Result(speak=f"Hoje é {dias[n.weekday()]}, {n.day} de {meses[n.month - 1]}, senhor.")

    # --- volume ---
    if re.search(r"\bvolume\b|\bsom\b", t) or re.search(r"\b(aumenta|abaixa|diminui|sobe|desce)\b", t):
        if re.search(r"mud[oa]|sem som|tira o som|silenci", t):
            tap(VK["VOL_MUTE"])
            return Result(speak="")
        if re.search(r"aument|sobe|mais alto|mais forte|aumenta", t):
            tap(VK["VOL_UP"], 6)
            return Result(speak="")
        if re.search(r"abaixa|diminui|desce|mais baixo|baixa", t):
            tap(VK["VOL_DOWN"], 6)
            return Result(speak="")

    # --- controle de mídia ---
    if re.search(r"\b(proxima|pula|avanca)\b.*\b(musica|faixa|som)\b|\bpula essa\b", t):
        tap(VK["MEDIA_NEXT"]); return Result(speak="")
    if re.search(r"\b(volta|anterior)\b.*\b(musica|faixa)\b", t):
        tap(VK["MEDIA_PREV"]); return Result(speak="")
    if re.search(r"\bpausa\w*\b|\bpara a musica\b|\bpara o som\b", t):
        tap(VK["MEDIA_PLAY"]); return Result(speak="")
    if re.fullmatch(r"(toca|continua|retoma|play)\w*", t):
        tap(VK["MEDIA_PLAY"]); return Result(speak="")

    # --- bloquear tela ---
    if re.search(r"\bbloqueia?\b.*\b(tela|pc|computador|maquina)\b|\btrava a tela\b", t):
        _lock()
        return Result(speak="Trancado, senhor.")

    # --- suspender ---
    if re.search(r"\b(suspende\w*|modo de espera|dormir o pc|hiberna\w*|poe pra dormir)\b", t):
        if not dz.get("allow_suspend", True):
            return Result(speak="A suspensão está desativada na configuração, senhor.")
        return Result(confirm=("Suspender o computador, senhor?",
                               lambda: (_suspend(), "Até logo, senhor.")[1]))

    # --- desligar ---
    if re.search(r"\bdeslig\w+\b", t) and not re.search(r"\bdeslig\w+ (o|a) (steam|spotify|musica|som|monitor)\b", t):
        if not dz.get("allow_shutdown", True):
            return Result(speak="O desligamento está desativado na configuração, senhor.")
        delay = int(dz.get("shutdown_delay_seconds", 30))
        return Result(confirm=("Confirma desligar o computador, senhor?", _shutdown(delay)))

    # --- reiniciar ---
    if re.search(r"\b(reinicia\w*|reinicializa\w*|reboot)\b", t):
        if not dz.get("allow_restart", True):
            return Result(speak="O reinício está desativado na configuração, senhor.")
        delay = int(dz.get("shutdown_delay_seconds", 30))
        return Result(confirm=("Confirma reiniciar o computador, senhor?", _restart(delay)))

    # --- fechar janela / app ---
    m = re.search(r"\b(fecha\w*|encerra\w*)\b\s+(.*)$", t)
    if m:
        if not dz.get("allow_close", True):
            return Result(speak="Fechar janelas está desativado, senhor.")
        alvo = m.group(2).strip()
        if not alvo or re.fullmatch(r"(isso|a janela|essa janela|a tela|o programa|tudo)", alvo):
            combo("ALT", "F4")
            return Result(speak="")
        exe = alvo.split()[0]
        return Result(confirm=(f"Fechar {alvo}, senhor?",
                               lambda e=exe: (_run("taskkill", "/f", "/im", e if e.endswith('.exe') else e + '.exe'),
                                              "Feito, senhor.")[1]))

    # --- pesquisar no Google ---
    m = re.search(r"(?:pesquis\w+|busca\w*|procur\w+|googl\w+|da uma olhada em)"
                  r"(?:\s+(?:no|na|por|pelo|pela|sobre|o|a|em))*\s+(.+)", t)
    if m:
        q = re.sub(r"^(?:no\s+|na\s+)?(?:google|internet|web|navegador|browser)\s+", "", m.group(1).strip())
        q = re.sub(r"\s+(?:no|na)\s+(?:google|internet|web|navegador)$", "", q).strip()
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(q))
        return Result(speak=f"Pesquisando {q}, senhor.")

    # --- tocar música (Spotify) ---
    m = re.search(r"^(?:toc\w+|coloc\w+|bota\w*|p(?:oe|õe)|manda|escut\w+|ouvir|ouve|"
                  r"quero\s+ouvir|quero\s+escutar|poe\s+pra\s+tocar)\s+"
                  r"(?:a\s+musica\s+|a\s+|o\s+|umas?\s+)?(.+)", t)
    if m:
        song = re.sub(r"\s+(?:no|pelo|pela|la\s+no)\s+spotify$", "", m.group(1)).strip()
        if song:
            ok, fala = spotify.play(song, cfg)
            return Result(speak=fala)

    # --- redigir um texto (LLM -> Bloco de Notas) ---
    m = re.search(r"^(?:escrev\w+|redi[jg]\w*|reda\w*|faz\w*\s+um\s+texto|cria\w*\s+um\s+texto|"
                  r"elabora\w*|digit\w*\s+um\s+texto|prepara\w*\s+um\s+texto)\s+"
                  r"(?:um\s+|uma\s+)?(?:texto\s+|paragrafo\s+|email\s+|e-?mail\s+|mensagem\s+|carta\s+|redacao\s+)?"
                  r"(?:sobre\s+|a\s+respeito\s+de\s+|falando\s+de\s+|de\s+|do\s+|da\s+)?(.+)", t)
    if m:
        if not dz.get("allow_typing", True):
            return Result(speak="Escrever textos está desativado, senhor.")
        return write_document(m.group(1).strip(), cfg, speak, brain)

    # --- digitar literalmente (o que você ditar vai pro campo em foco) ---
    m = re.search(r"^(?:digit\w*|escrev[ae]\s+isso|transcrev\w*|poe\s+isso|escreve\s+o\s+seguinte|"
                  r"anota\s+literalmente)[:,\s]+(.+)", raw.strip(), flags=re.IGNORECASE)
    if m:
        if not dz.get("allow_typing", True):
            return Result(speak="A digitação está desativada, senhor.")
        return type_verbatim(m.group(1).strip())

    # --- abrir jogo ---
    m = re.search(r"\b(?:jog\w+|abr\w+\s+o\s+jogo|inicia\w*\s+o\s+jogo|roda\w*\s+o\s+jogo|bota\w*\s+o\s+jogo)\b\s*(.*)$", t)
    if m:
        alvo = m.group(1).strip() or re.sub(r"\b(quero|vamos|bora|joga\w*)\b", "", t).strip()
        return open_target(alvo, cfg, prefer_game=True)

    # --- abrir app / programa / site ---
    m = re.search(r"\b(?:abr\w+|abre|inicia\w*|liga\w*|roda\w*|executa\w*|chama\w*|poe|abrir)\b\s+"
                  r"(?:o\s+|a\s+|os\s+|as\s+|um\s+|uma\s+|meu\s+|minha\s+)?(.+)", t)
    if m:
        return open_target(m.group(1).strip(), cfg)

    # --- anotar / lembrete ---
    m = re.search(r"^(?:anota\w*|lembra\w*|salva\w*|apont\w*|toma\s+nota)"
                  r"(?:\s+(?:isso|o\s+seguinte|que|pra\s+mim|ai))?[:,\s]+(.+)", t)
    if m:
        _append("NOTAS.md", m.group(1).strip())
        return Result(speak="Anotado, senhor.")

    # --- pedido de melhoria pro próprio Jarvis (fila para o desenvolvedor/Claude) ---
    m = re.search(r"^(?:pedido|melhoria|ideia|anota\s+pra\s+voce|pro\s+desenvolvedor|modo\s+dev\w*)"
                  r"[:,\s]+(.+)", t)
    if m:
        _append("PEDIDOS.md", m.group(1).strip())
        return Result(speak="Registrei o pedido, senhor. Passo ao desenvolvedor.")

    # --- nada bateu: manda pro LLM ---
    return Result(to_llm=raw.strip())
