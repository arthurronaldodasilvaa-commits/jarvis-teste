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

import maps
import reminders
import spotify
from common import HERE, combo, log, norm, paste_text, tap, VK, write_app_state, write_control

PROFILES_DIR = HERE / "profiles"


def list_profiles() -> list[dict]:
    """[{name, label}] — perfis em profiles/*.toml. label vem do cabeçalho
    '# Perfil: <Nome> | <descrição>' ou, na falta, do nome do arquivo."""
    out = []
    for p in sorted(PROFILES_DIR.glob("*.toml")) if PROFILES_DIR.is_dir() else []:
        label = p.stem.capitalize()
        try:
            head = p.read_text(encoding="utf-8")[:400]
            m = re.search(r"#\s*Perfil:\s*(.+)", head)
            if m:
                label = m.group(1).strip().rstrip(".")[:80]
        except OSError:
            pass
        out.append({"name": p.stem, "label": label})
    return out


def _resolve_profile(spoken: str) -> str | None:
    n = norm(spoken)
    names = {pr["name"] for pr in list_profiles()}
    for name in names:
        if name in n:
            return name
    alias = {"pai": "robson", "meu pai": "robson", "trabalho": "robson",
             "pessoal": "arthur", "eu": "arthur", "meu": "arthur"}
    for k, v in alias.items():
        if re.search(rf"\b{k}\b", n) and v in names:
            return v
    return None


def _write_active_profile(name: str) -> bool:
    cfgp = HERE / "config.toml"
    try:
        txt = cfgp.read_text(encoding="utf-8")
    except OSError:
        return False
    new, k = re.subn(r'(?m)^(\s*active\s*=\s*)"[^"]*"', rf'\g<1>"{name}"', txt, count=1)
    if k == 0:
        if re.search(r"(?m)^\[profile\]\s*$", new):
            new = re.sub(r"(?m)^(\[profile\]\s*\n)", rf'\1active = "{name}"\n', new, count=1)
        else:
            new = f'[profile]\nactive = "{name}"\n\n' + new
    try:
        cfgp.write_text(new, encoding="utf-8")
        return True
    except OSError:
        return False


_WHEN_RX = re.compile(
    r"\b(?:em|daqui a|dentro de|apos|depois de)\s+[\w ]+?\s*(?:segundos?|minutos?|min|horas?|h)\b(?:\s+e meia)?|"
    r"\b\d+\s*(?:segundos?|minutos?|min|horas?)\b|"
    r"\b(?:as|ao)\s+\d{1,2}\s*h?(?:\s*(?:e|:|h)\s*\d{1,2}|\s+\d{2}|\s*e meia)?"
    r"(?:\s*(?:da (?:manha|tarde|noite)|horas?|hora))?|"
    r"\bmeio[- ]?dia\b|\bmeia[- ]?noite\b|\bmeia hora\b|\bum quarto de hora\b|"
    r"\b(?:uma )?hora e meia\b|\bamanha\b")


def _reminder_msg(rest: str) -> str:
    """Tira o pedaço de tempo e conectores, sobra a mensagem do lembrete."""
    s = _WHEN_RX.sub(" ", rest)
    s = re.sub(r"^\s*(?:de|pra|para|que|:|,|o|a|para que|pra que)\s+", " ", s)
    s = re.sub(r"\s+(?:de|pra|para)\s*$", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,.:;-")
    # se sobrou só conectivo/lixo, considera timer sem descrição
    return "" if len(s) < 3 or s in ("de", "pra", "para", "isso") else s

CNW = 0x08000000  # CREATE_NO_WINDOW


# --------------------------------------------------------------------------
@dataclass
class Result:
    speak: str = ""
    confirm: tuple | None = None          # (pergunta:str, do:callable-> str|None)
    to_llm: str = ""                      # se preenchido, o loop manda pro LLM
    stop: bool = False
    fallback: bool = False                # True = não achou nada certo (só chutou uma busca web)
    restart: bool = False                 # True = o loop deve reiniciar o daemon (troca de perfil)


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


def open_target(spoken: str, cfg: dict, *, prefer_game: bool = False,
                web_fallback: bool = True) -> Result:
    apps = {norm(k): v for k, v in cfg.get("apps", {}).items()}

    spoken = re.sub(r"\s+(?:pra\s+mim|pro\s+senhor|por\s+favor|ai|agora|de\s+novo)$", "",
                    spoken.strip()).strip()

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

    if web_fallback:
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(spoken))
        return Result(speak=f"Não achei {spoken} instalado, senhor. Procurei na web.", fallback=True)
    return Result(fallback=True)   # nada aberto — quem chamou decide (tenta rotear antes)


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
    subprocess.run(list(args), creationflags=CNW, timeout=15,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


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

# --- "manual" do Jarvis: perguntas de "como eu faço X com você" -----------
# Cada item: (regex no texto normalizado, resposta falada).
# Checado bem no início do dispatch — resposta sempre certa, sem depender do LLM.
_HELP = [
    (r"nao me (ouc|ouv|escut)|par\w* de (me )?(ouvir|escut\w*)|silenci\w* (voce|voce )?um pouco|"
     r"fic\w* (quiet|em silencio|calad)|modo cinema|te (cal|deslig|mut|silenci)\w*|"
     r"desativ\w* (a )?(escuta|voce)|paus\w* (a )?escuta|nao (te )?quero (te )?(ouvir|escut\w*)|"
     r"silenci\w* voce",
     "Simples, senhor: diga \"Jarvis, modo cinema\". Para eu voltar a ouvir, "
     "aperte Control Alt J ou o botão no aplicativo."),
    (r"volt\w* a (ouvir|escut\w*)|te (cham|ativ)\w* de volta|sair do modo cinema|"
     r"reativ\w* (a )?escuta|(voltar|sair) do (modo )?(cinema|pausa)",
     "Aperte Control Alt J, ou clique no botão de energia no aplicativo do Jarvis, senhor."),
    (r"abr\w* (um |o )?(programa|aplicativo|app|jogo)|inici\w* (um )?(programa|jogo)|"
     r"jog\w* (um )?jogo",
     "Diga \"Jarvis, abre\" e o nome, senhor. Por exemplo: \"Jarvis, abre o navegador\"."),
    (r"toc\w* (uma )?musica|coloc\w* (uma )?musica|ouv\w* (uma )?musica|por musica|"
     r"por uma musica|escut\w* (uma )?musica",
     "Diga \"Jarvis, toca\" e o nome da música ou do artista, senhor."),
    (r"cheg\w* (em|no|na|ate)|trac\w* (uma )?rota|v\w* (uma )?rota|ir (pra|para|ate)|"
     r"us\w* (o )?(google )?maps|abr\w* (o )?maps|acha\w* (um )?(restaurante|lugar|empresa)",
     "Diga \"Jarvis, como chegar em\" e o lugar, senhor. Ou \"Jarvis, restaurantes "
     "bem avaliados em\" e a cidade."),
    (r"ativ\w* (a )?camera|lig\w* (a )?camera|v\w+ (a )?camera|us\w* (a )?camera|"
     r"cri\w* (um )?holograma|faz\w* (um )?holograma|v\w+ (um )?holograma|"
     r"cri\w* (um )?(cubo|forma)",
     "Diga \"Jarvis, ativar câmera\", senhor. Depois \"Jarvis, cria um cubo\" ou outra "
     "forma. Para sair, \"Jarvis, desativar câmera\"."),
    (r"mud\w* (o )?volume|aument\w* (o )?(volume|som)|abaix\w* (o )?(volume|som)|"
     r"control\w* (o )?(som|volume)|(deix\w*|por) (o )?som mais",
     "Diga \"Jarvis, aumenta o volume\" ou \"Jarvis, abaixa o volume\", senhor."),
    (r"escrev\w* (um )?(texto|email|e-?mail|mensagem)|redi[jg]\w* (um )?texto|"
     r"faz\w* (um )?texto|te dit\w*|voce escrev\w*",
     "Diga \"Jarvis, escreve um texto sobre\" e o assunto, senhor. Eu escrevo no Bloco de Notas."),
    (r"deslig\w* (o )?(pc|computador|maquina)|reinici\w* (o )?(pc|computador)|"
     r"faz\w* o (pc|computador) (deslig|reinici)",
     "Diga \"Jarvis, desliga o computador\", senhor. Eu peço confirmação — responda \"sim\". "
     "Para abortar, \"Jarvis, cancelar\"."),
    (r"que horas|v\w+ (as )?horas|sab\w* (a )?hora|v\w+ (a )?data|que dia (e )?hoje",
     "Diga \"Jarvis, que horas são\" ou \"Jarvis, que dia é hoje\", senhor."),
    (r"te (us|comand|control)\w*|(quais|que) (sao (os )?)?comando|o que voce (faz|sabe faz\w*)|"
     r"(como )?voce funciona|me ajud\w* com o que|(pra|para) que voce serve|suas funcoes|"
     r"lista de comandos|me ensin\w* a te us\w*|o que (da (pra|para)|posso) (faz\w*|ped\w*)",
     "Eu te atendo quando o senhor começa a fala com \"Jarvis\". Posso abrir programas, "
     "tocar música, traçar rotas no mapa, mostrar hologramas na câmera, escrever textos, "
     "controlar o volume e desligar o computador. Diga \"Jarvis, modo cinema\" quando "
     "quiser que eu pare de ouvir."),
    (r"te (cham|acord)\w*|(falo|chamo|fal\w*) (com )?(voce|contigo|vc)|"
     r"palavra (de ativacao|magica|chave)|como come[cç]\w*|te acion\w*",
     "É só dizer \"Jarvis\" no começo da frase, senhor. \"Jarvis\" sozinho eu respondo; "
     "\"Jarvis\" com um pedido eu executo."),
    (r"mud\w* (de )?perfil|troc\w* (de )?perfil|mud\w* (de )?usuario|outro perfil|"
     r"perfil de (outra|outro)",
     "Diga \"Jarvis, muda para o perfil\" e o nome, senhor. Eu reinicio já no perfil novo."),
    (r"(cri\w*|marc\w*|por|poe|faz\w*) (um )?(lembrete|timer|alarme)|me lembr\w*|"
     r"me avis\w*|me acord\w*|cronometr\w*",
     "Diga \"Jarvis, me lembra de\" e o quê, mais um tempo — tipo \"em 20 minutos\" ou "
     "\"às 15 horas\", senhor."),
    (r"clim\w*|tempo (hoje|agora|la fora)|previs\w* do tempo|vai chov\w*|"
     r"quantos graus|temperatura (hoje|agora|la fora)",
     "Diga \"Jarvis, como está o tempo?\" — eu falo a temperatura e a previsão de hoje, senhor."),
]


def dispatch(raw: str, cfg: dict, speak, brain, _depth: int = 0) -> Result:
    t = norm(raw)
    dz = cfg.get("danger", {})

    if not t:
        return Result(speak=cfg["assistant"].get("attention_reply", "Pois não, senhor?"))

    if t in STOP_WORDS or (len(t.split()) <= 3 and any(w in t for w in STOP_WORDS)):
        # exceção: "cancela ..." de desligamento tratado abaixo
        if "cancel" not in t:
            return Result(speak="Às ordens, senhor.", stop=True)

    # --- "manual": "como eu faço X com você?" -> instrução (não executa nada) ---
    # Só entra se a pergunta é sobre COMO usar o Jarvis (menciona "você/te/jarvis"
    # ou é uma pergunta meta), pra não roubar comandos reais tipo "como chegar em X".
    _asks_how = re.search(r"\b(como|de que jeito|de que forma|como que|nao sei como|"
                          r"qual (a |o )?(forma|maneira|jeito|palavra|comando|nome)|"
                          r"me ensin\w*|me explic\w*)\b", t)
    _about_jarvis = re.search(r"\b(voce|vc|contigo|te |ti |o jarvis|no jarvis|com voce)\b", t)
    _meta_q = re.search(r"\bo que (voce )?(faz|sabe faz\w*)|(pra|para) que (voce )?serve|"
                        r"quais?\s+.*comando|suas funcoes|lista de comando|"
                        r"o que (da (pra|para)|posso) (faz|ped|dizer|fal)\w*", t)
    if _meta_q or (_asks_how and _about_jarvis):
        for pat, ans in _HELP:
            if re.search(rf"\b(?:{pat})", t):
                return Result(speak=ans)
        if _meta_q:                       # meta sem casar item: dá a visão geral
            return Result(speak=_HELP[-2][1])

    # --- perfis: qual está ativo / trocar ---
    if re.search(r"\b(perfil|perfis)\b", t):
        ativo = str(cfg.get("profile", {}).get("active", "")) or "padrão"
        if re.search(r"\b(qual|que|quem|mostra|lista|quais)\b", t) and not re.search(
                r"\b(muda|mudar|troca|trocar|ativa|ativar|usa|usar|passa|passar|poe|por|coloca)\b", t):
            nomes = ", ".join(p["name"] for p in list_profiles())
            return Result(speak=f"Perfil ativo: {ativo}, senhor. Disponíveis: {nomes}.")
        alvo = _resolve_profile(t)
        if not alvo:
            nomes = ", ".join(p["name"] for p in list_profiles())
            return Result(speak=f"Qual perfil, senhor? Tenho: {nomes}.")
        if alvo == norm(ativo):
            return Result(speak=f"O perfil {alvo} já está ativo, senhor.")
        if not _write_active_profile(alvo):
            return Result(speak="Não consegui alterar a configuração, senhor.")
        return Result(speak=f"Perfil {alvo} ativado, senhor. Vou reiniciar agora.",
                      restart=True)

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
        return Result(speak="Câmera ativada, senhor.")
    if re.search(r"\b(desativa\w*|desliga\w*|fecha\w*|para\w*|tira|encerra\w*)\s+(a\s+)?c[aâe]mera\b|"
                 r"\bvolta\w*\s+(pro|para o|ao)\s+cerebro\b|\bmodo cerebro\b|\bfecha\w* a webcam\b", t):
        write_control(view="brain")
        return Result(speak="Voltando pro cérebro, senhor.")

    # --- criar / limpar hologramas na tela da câmera ---
    if re.search(r"\b(limpa\w*|apaga\w*|remove\w*|tira|deleta\w*|zera)\s+"
                 r"(tudo|os?\s+holograma\w*|as?\s+forma\w*|a\s+tela)\b", t):
        write_control(holo={"action": "clear", "n": int(time.time() * 1000)})
        return Result(speak="Tela limpa, senhor.")

    _mk = ("cria\\w*|criar|faz\\w*|adiciona\\w*|gera\\w*|desenha\\w*|projeta\\w*|"
           "poe|monta\\w*|mostra\\w*|exibe\\w*|abre\\w*|traz\\w*|quero\\w*|queria|"
           "vira|me\\s+ve|manda\\w*|coloca\\w*|bota\\w*")
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
        _nome = {"triangulo": "Triângulo retângulo",
                 "tabela_angulos": "Tabela de ângulos notáveis",
                 "tabela_relacoes": "Relações trigonométricas"}[_trig]
        return Result(speak=f"{_nome} na tela, senhor.")

    m = re.search(rf"\b(?:{_mk})\b\s+(.+)", t)
    if m:
        for w in m.group(1).split():                       # varre as palavras após o verbo
            shape = _SHAPES.get(w) or _SHAPES.get(norm(w))
            if shape:
                write_control(holo={"action": "add", "shape": shape, "n": int(time.time() * 1000)})
                return Result(speak=f"{w.capitalize()} na tela, senhor.")

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

    # --- lembretes / timers ---
    if re.search(r"\b(meus lembretes|que lembretes|quais lembretes|tenho lembrete|"
                 r"algum lembrete|lista de lembretes)\b", t):
        pend = reminders.pending()
        if not pend:
            return Result(speak="Nenhum lembrete, senhor.")
        agora = datetime.now()
        linhas = []
        for r in pend[:5]:
            quando = datetime.fromtimestamp(r["at"])
            q = quando.strftime("%H:%M") if quando.date() == agora.date() else quando.strftime("%d/%m %H:%M")
            linhas.append(f"{r['text']} às {q}")
        return Result(speak="Senhor: " + "; ".join(linhas) + ".")
    if re.search(r"\b(cancela|apaga|limpa|tira)\w*\s+(os |todos os |meus )?(lembretes?|timers?|alarmes?)\b", t):
        n = reminders.clear_all()
        return Result(speak=("Limpei os lembretes, senhor." if n else "Não tinha lembrete, senhor."))
    m = re.search(r"\b(me lembr\w+|lembr[ae]\s+(?:de\s+)?mim|me avis\w+|me acord\w+|me cham\w+|"
                  r"p[oõ]e\s+(?:um\s+)?(?:lembrete|timer|alarme|despertador)|"
                  r"timer\s+(?:de|pra|para)|cronometr\w+\s+(?:de|pra|para)|"
                  r"alarme\s+(?:de|pra|para|das?)|despertador\s+(?:pra|para|das?))\b(.*)", t)
    if m:
        rest = m.group(2).strip()
        when = reminders.parse_when(rest)
        if not when:
            return Result(speak="Pra quando, senhor? Diga um tempo, tipo 'em 20 minutos' ou 'às 15 horas'.")
        ts, human = when
        msg = _reminder_msg(rest)
        reminders.add(msg or "(sem descrição)", ts)
        prefixo = "Às" if (":" in human or "meio-dia" in human or "meia-noite" in human) else "Daqui a"
        if prefixo == "Às":
            human = human.replace(":", " e ").replace(" de amanhã", ", amanhã,")
        if msg:
            return Result(speak=f"Combinado, senhor. {prefixo} {human} eu aviso: {msg}.")
        return Result(speak=f"Marcado pra {human}, senhor. Eu aviso." if prefixo == "Às"
                      else f"Timer de {human}, senhor. Eu aviso quando terminar.")

    # --- Google Maps (rota / buscar lugar / restaurantes bem avaliados) ---
    fala = maps.handle(t)
    if fala is not None:
        return Result(speak=fala)

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
        song = m.group(1)
        song = re.sub(r"^(?:pra|pro|para)\s+(?:tocar|ouvir|escutar|mim)\s+", "", song)
        song = re.sub(r"^(?:ver|ouvir|tocar|escutar|botar|colocar|por)\s+", "", song)
        song = re.sub(r"^(?:aquele|aquela|esse|essa|uns|umas)\s+(?:d[aeo]s?\s+)?", "", song)
        song = re.sub(r"^(?:um|uns|uma|umas)\s+(?:som|sonzinho|musica|musiquinha|hit|classico|faixa)\s+"
                      r"(?:d[aeo]s?\s+)?", "", song)
        song = re.sub(r"^(?:aquele|aquela|essa|esse|a|o)\s+(?:som|musica|hit|classico|faixa)\s+"
                      r"(?:d[aeo]s?\s+)?", "", song)
        song = re.sub(r"\s+(?:no|pelo|pela|la\s+no)\s+spotify$", "", song)
        song = re.sub(r"\s+(?:pra\s+mim|por\s+favor|ai|agora)$", "", song).strip()
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

    _deferred = None   # "abrir X" que não achou nada — tenta rotear antes de chutar busca
    _strip_tail = lambda s: re.sub(r"\s+(?:pra\s+mim|pro\s+senhor|por\s+favor|ai|agora|de\s+novo)$",
                                   "", s.strip()).strip()

    # --- abrir jogo ---
    m = re.search(r"\b(?:jog\w+|abr\w+\s+o\s+jogo|inicia\w*\s+o\s+jogo|roda\w*\s+o\s+jogo|bota\w*\s+o\s+jogo)\b\s*(.*)$", t)
    if m:
        alvo = _strip_tail(m.group(1).strip() or re.sub(r"\b(quero|vamos|bora|joga\w*)\b", "", t).strip())
        r = open_target(alvo, cfg, prefer_game=True, web_fallback=False)
        if not r.fallback:
            return r
        _deferred = alvo

    # --- abrir app / programa / site ---
    m = re.search(r"\b(?:abr\w+|abre|inicia\w*|liga\w*|roda\w*|executa\w*|chama\w*|poe|abrir)\b\s+"
                  r"(?:o\s+|a\s+|os\s+|as\s+|um\s+|uma\s+|meu\s+|minha\s+)?(.+)", t)
    if m:
        alvo = _strip_tail(m.group(1).strip())
        r = open_target(alvo, cfg, web_fallback=False)
        if not r.fallback:
            return r
        _deferred = _deferred or alvo

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

    # --- nada bateu: o LLM tenta traduzir o pedido num COMANDO ---
    _is_question = re.search(r"\b(por ?que|porque|qual|quais|quem|quanto\s+(custa|vale)|"
                             r"o\s+que\s+(e|significa|quer dizer)|me\s+(explica|conta|fala\s+sobre)|"
                             r"voce\s+(sabe|acha|pode\s+me\s+dizer))\b|\?", t)
    if _depth == 0 and brain is not None and hasattr(brain, "route") and not _is_question:
        try:
            routed = brain.route(raw)
        except Exception as exc:  # noqa: BLE001
            log(f"route falhou: {exc}"); routed = ""
        if routed and norm(routed) != t:
            log(f"  roteado: {raw!r} -> {routed!r}")
            r2 = dispatch(routed, cfg, speak, brain, _depth=1)
            if not r2.to_llm and not r2.fallback:   # achou um comando de verdade
                return r2
            log("  (roteamento não deu num comando claro — vai pro chat)")

    # --- "abrir X" que não achou nada e o roteador não resolveu: chuta busca na web ---
    if _deferred:
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(_deferred))
        return Result(speak=f"Não achei {_deferred} instalado, senhor. Procurei na web.", fallback=True)

    # --- é conversa/pergunta mesmo: manda pro chat ---
    return Result(to_llm=raw.strip())
