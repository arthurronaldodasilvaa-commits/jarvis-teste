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

import calc
import maps
import news
import reminders
import spotify
import translate
import weather
import wiki
from common import HERE, combo, log, norm, paste_text, tap, VK, write_app_state, write_control

try:
    import skills_extra
except Exception as _exc:  # noqa: BLE001
    skills_extra = None
    log(f"skills_extra não disponível: {_exc}")

try:
    import study
except Exception as _exc:  # noqa: BLE001
    study = None
    log(f"study não disponível: {_exc}")

try:
    import teach
except Exception as _exc:  # noqa: BLE001
    teach = None
    log(f"teach não disponível: {_exc}")

try:
    import invent
except Exception as _exc:  # noqa: BLE001
    invent = None
    log(f"invent não disponível: {_exc}")

try:
    import face as facemod
except Exception as _exc:  # noqa: BLE001
    facemod = None
    log(f"face não disponível: {_exc}")

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
    s = re.sub(r"^\s*(?:de|da|do|das|dos|pra|para|que|:|,|o|a|para que|pra que)\s+", " ", s)
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
    await_reply: object = None            # callable(fala_do_usuario:str)->str : consome a próxima fala


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

_MK = (r"cria\w*|criar|faz\w*|adiciona\w*|gera\w*|desenha\w*|projeta\w*|poe|monta\w*|"
       r"mostra\w*|exibe\w*|abre\w*|traz\w*|quero\w*|queria|vira|me\s+ve|manda\w*|"
       r"coloca\w*|bota\w*|plota\w*|plot|grafico|explica\w*|ensina\w*")

# (regex de gatilho, nome do modelo no models.js/trig.js, nome falado)
_MODELS = [
    (r"triangulo\s+retangulo", "triangulo", "Triângulo retângulo"),
    (r"(tabela|quadro).*(angulos?\s+notave|angulos? notave)|angulos?\s+notave\w*",
     "tabela_angulos", "Tabela de ângulos notáveis"),
    (r"rela\w+\s+trigonom|tabela\s+de\s+rela\w+|rela\w+\s+trigonometrica\w*",
     "tabela_relacoes", "Relações trigonométricas"),
    (r"circulo\s+trigonometrico|circunferencia\s+trigonometrica|ciclo\s+trigonometrico",
     "circulo_trigonometrico", "Círculo trigonométrico"),
    (r"corpo\s+livre|diagrama\s+de\s+forcas?|vetores?\s+de\s+forca", "corpo_livre",
     "Diagrama de corpo livre"),
    (r"lancamento\s+obliquo|movimento\s+de\s+projetil|tiro\s+obliquo", "lancamento_obliquo",
     "Lançamento oblíquo"),
    (r"plano\s+inclinado|rampa\s+(com|de)\s+bloco", "plano_inclinado", "Plano inclinado"),
    (r"molecula\s+de\s+agua|molecula\s+da\s+agua|\bh2o\b|\bagua\b\s*(3d|molecula)", "molecula_agua",
     "Molécula de água"),
    (r"molecula\s+de\s+metano|\bmetano\b|\bch4\b", "molecula_metano", "Molécula de metano"),
    (r"molecula\s+de\s+benzeno|\bbenzeno\b|anel\s+benzenico", "molecula_benzeno", "Molécula de benzeno"),
    (r"tabela\s+periodica", "tabela_periodica", "Tabela periódica"),
    (r"celula\s+animal|\bcelula\b|organelas", "celula", "Célula animal"),
    (r"molecula\s+de\s+(gas carbonico|dioxido de carbono)|\bco2\b|\bgas carbonico\b",
     "molecula_co2", "Molécula de CO₂"),
    (r"molecula\s+de\s+amonia|\bamonia\b|\bnh3\b", "molecula_amonia", "Molécula de amônia"),
    # --- lote B: física ---
    (r"\bonda\s+(senoidal|transversal|eletromagnetica)?\b|onda\s+na\s+corda|"
     r"\bfuncao\s+de\s+onda\b|movimento\s+ondulatorio", "onda", "Onda"),
    (r"pendulo\s+simples|\bpendulo\b|movimento\s+harmonico", "pendulo", "Pêndulo simples"),
    (r"circuito\s+(eletrico|em serie|simples)|\bcircuito\b(?!.*paralelo)|lei\s+de\s+ohm", "circuito",
     "Circuito em série"),
    (r"campo\s+eletrico|linhas?\s+de\s+campo|duas\s+cargas|forca\s+entre\s+cargas",
     "campo_eletrico", "Campo elétrico"),
    # --- lote B: cálculo / álgebra linear ---
    (r"soma\s+de\s+vetores|somar?\s+vetores?|adicao\s+de\s+vetores|"
     r"\bvetores\b|regra\s+do\s+paralelogramo", "vetores", "Soma de vetores"),
    (r"reta\s+tangente|derivada\s+(geometrica|como inclinacao|no ponto)|"
     r"inclinacao\s+da\s+curva|\bderivada\b", "derivada", "Reta tangente / derivada"),
    (r"soma\s+de\s+riemann|integral\s+(como area|definida)|area\s+sob\s+a\s+curva|"
     r"\bintegral\b", "integral", "Integral / soma de Riemann"),
    (r"superficie\s+(3d|tridimensional)|z\s*=\s*f\s*\(?\s*x\s*,?\s*y|"
     r"grafico\s+3d|funcao\s+de\s+duas\s+variaveis|paraboloide|\bsela\b", "superficie_3d",
     "Superfície z = f(x, y)"),
    # --- lote B: química ---
    (r"geometria\s+molecular|\bvsepr\b|repulsao\s+de\s+pares|"
     r"geometria\s+(linear|angular|trigonal|tetraedrica|piramidal|octaedrica)",
     "geometria_molecular", "Geometria molecular"),
    # --- lote C: biologia / astronomia / estatística / transformações ---
    (r"\bdna\b|dupla\s+helice|acido\s+desoxirribonucleico|codigo\s+genetico", "dna", "DNA"),
    (r"sistema\s+solar|\bplanetas\b|orbitas?\s+dos?\s+planetas|modelo\s+heliocentrico",
     "sistema_solar", "Sistema solar"),
    (r"\bcoracao\b|camaras\s+do\s+coracao|sistema\s+circulatorio|atrios?\s+e\s+ventriculos?",
     "coracao", "Coração"),
    (r"grafico\s+de\s+setores|grafico\s+de\s+pizza|grafico\s+circular", "grafico_setores",
     "Gráfico de setores"),
    (r"grafico\s+de\s+barras|grafico\s+de\s+colunas|\bhistograma\b", "grafico_barras",
     "Gráfico de barras"),
    (r"transla[cç][ãa]o\s+(de|da|do)|transladar", "translacao", "Translação"),
    (r"reflex[ãa]o\s+(de|da|do|no eixo)|espelhar\s+(a|o|uma|um)", "reflexao", "Reflexão"),
    (r"homotetia|amplia[cç][ãa]o\s+proporcional", "homotetia", "Homotetia"),
    (r"transforma[cç][õo]es\s+geometricas|geometria\s+de\s+transforma", "transformacoes",
     "Transformações geométricas"),
    # --- lote E ---
    (r"\blente\b|lente\s+convergente|\boptica\b|forma[cç][aã]o\s+de\s+imagem|"
     r"equacao\s+dos?\s+pontos?\s+conjugados?", "lente", "Lente convergente"),
    (r"colis[aã]o\s+inel[aá]stica", "colisao_inelastica", "Colisão inelástica"),
    (r"colis[aã]o(\s+el[aá]stica)?|choque\s+entre\s+(dois\s+)?(blocos|corpos)|"
     r"conserva[cç][aã]o\s+d[ao]\s+(momento|quantidade de movimento)", "colisao", "Colisão"),
    (r"circuito\s+(em\s+)?paralelo|resist[eê]ncias?\s+em\s+paralelo", "circuito_paralelo",
     "Circuito em paralelo"),
    (r"[aá]rvore\s+d[ea]\s+probabilidade|diagrama\s+de\s+[aá]rvore|"
     r"probabilidade\s+condicional", "arvore_probabilidade", "Árvore de probabilidade"),
    (r"\bneur[oô]nio\b|\bsinapse\b|c[eé]lula\s+nervosa|impulso\s+nervoso", "neuronio", "Neurônio"),
    (r"\bpilha\b|pilha\s+(eletroquimica|de daniell)|c[eé]lula\s+galv[aâ]nica|"
     r"\beletroquimica\b|potencial\s+de\s+reducao", "pilha", "Pilha eletroquímica"),
    (r"\besqueleto\b|\bossos\b|corpo\s+humano.*ossos|sistema\s+esquel[eé]tico", "esqueleto",
     "Esqueleto humano"),
    (r"\bc[eé]rebro\b|\benc[eé]falo\b|lobos?\s+(cerebrais|do cerebro)|sistema\s+nervoso\s+central",
     "cerebro", "Cérebro"),
]

# geometrias VSEPR nomeadas -> variação do modelo
_VSEPR = {"linear": "geometria_linear", "angular": "geometria_angular",
         "trigonal": "geometria_trigonal", "tetraedrica": "geometria_tetraedrica",
         "tetraédrica": "geometria_tetraedrica", "piramidal": "geometria_piramidal",
         "octaedrica": "geometria_octaedrica", "octaédrica": "geometria_octaedrica"}

_SOLIDS_FORMULA = {"esfera": "esfera", "cubo": "cubo", "cilindro": "cilindro",
                   "cone": "cone", "piramide": "piramide", "pirâmide": "piramide"}

_PARAM_WORDS = (r"angulo|ângulo|inclinacao|inclinação|massa|peso|velocidade|"
                r"frequencia|frequência|amplitude|comprimento|abertura|altura|tamanho")
_NUMW = {"zero": 0, "um": 1, "uma": 1, "dois": 2, "tres": 3, "três": 3, "quatro": 4,
         "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
         "quinze": 15, "vinte": 20, "vinte e cinco": 25, "trinta": 30,
         "trinta e cinco": 35, "quarenta": 40, "quarenta e cinco": 45,
         "cinquenta": 50, "sessenta": 60}


def _holo_param(t: str) -> "Result | None":
    """'muda o ângulo pra 30', 'aumenta a massa', 'diminui a frequência'."""
    m = re.search(rf"\b(muda\w*|ajust\w*|coloc\w*|poe|bota|deix\w*|defin\w*|set\w*|"
                  rf"aument\w*|sobe|cresc\w*|diminu\w*|abaix\w*|reduz\w*|baix\w*)\b"
                  rf".*?\b({_PARAM_WORDS})\b(.*)", t)
    if not m:
        m = re.search(rf"\b({_PARAM_WORDS})\b\s+(?:pra|para|em|no|de)\s+(.+)", t)
        if not m:
            return None
        verbo, nome, resto = "muda", m.group(1), m.group(2)
    else:
        verbo, nome, resto = m.group(1), m.group(2), m.group(3)

    holo = {"action": "param", "name": nome, "n": int(time.time() * 1000)}
    is_delta = bool(re.search(r"aument|sobe|cresc|diminu|abaix|reduz|baix", verbo))

    val = None
    num = re.search(r"(-?\d+(?:[.,]\d+)?)", resto)
    if num:
        val = float(num.group(1).replace(",", "."))
    else:
        for w, n in sorted(_NUMW.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf"\b{re.escape(w)}\b", resto):
                val = n
                break

    if not is_delta and val is not None:
        holo["value"] = val
        write_control(holo=holo)
        v = int(val) if val == int(val) else val
        return Result(speak=f"{nome.capitalize()} em {v}, senhor.")
    holo["delta"] = 1 if re.search(r"aument|sobe|cresc", verbo) else -1
    write_control(holo=holo)
    return Result(speak="Ajustado, senhor.")


def _holo_models(t: str, raw: str = "") -> "Result | None":
    """Modelos de estudo + formas simples na câmera. t = texto normalizado."""
    has_verb = re.search(rf"\b(?:{_MK})\b", t) is not None

    # ajuste de parâmetro de um modelo interativo (slider)
    _pr = _holo_param(t)
    if _pr is not None:
        return _pr

    # gráfico estatístico: "gráfico de barras 4 7 3 9" / "gráfico de setores 30 50 20"
    mg = re.search(r"grafico\s+(?:de\s+|em\s+)?(barras?|colunas?|setores?|pizza|circular|"
                   r"histograma)\b(.*)", t)
    if mg:
        nums = [float(x) for x in re.findall(r"-?\d+(?:[.,]\d+)?", mg.group(2).replace(",", "."))]
        kind = "setores" if re.search(r"setor|pizza|circular", mg.group(1)) else "barras"
        holo = {"action": "add", "shape": f"grafico_{kind}", "n": int(time.time() * 1000)}
        if nums:
            holo["data"] = nums[:8]
        write_control(holo=holo)
        tipo = "de setores" if kind == "setores" else "de barras"
        return Result(speak=f"Gráfico {tipo} na tela, senhor.")

    # plotter de função: "plota y = x ao quadrado" / "grafico de x^2 + 1"
    low = (raw or "").lower().strip()
    mp = re.search(r"\b(?:plot\w*|gr[aá]fic\w*|tra[cç]\w*\s+o\s+gr[aá]fico|"
                   r"desenh\w*\s+(?:o\s+)?gr[aá]fico)\b"
                   r"(?:\s+(?:de|da|do|a\s+fun[cç][aã]o))?\s+(.+)", low)
    if mp:
        expr = _clean_expr(mp.group(1))
        if expr:
            write_control(holo={"action": "add", "shape": "plot", "expr": expr,
                                "n": int(time.time() * 1000)})
            return Result(speak=f"Plotando {expr}, senhor.")

    # sólido + fórmula: "mostra a fórmula do volume da esfera" / "volume da esfera"
    if re.search(r"\b(formula|volume|area)\b", t) and re.search(r"\b(esfera|cubo|cilindro|cone|piramide)\b", t):
        sol = next(v for k, v in _SOLIDS_FORMULA.items() if k in t)
        write_control(holo={"action": "add", "shape": "solido_formula", "solid": sol,
                            "n": int(time.time() * 1000)})
        art = "da" if sol in ("esfera", "piramide") else "do"
        return Result(speak=f"Fórmulas {art} {sol} na tela, senhor.")

    # derivada / integral de uma função dita: "reta tangente de x ao quadrado"
    md = re.search(r"\b(reta tangente|derivada|integral|soma de riemann|area sob a curva)\b"
                   r"(?:\s+(?:de|da|do)\s+(.+))?", t)
    if md and (has_verb or md.group(1) in ("reta tangente", "soma de riemann")):
        shape = "integral" if re.search(r"integral|riemann|area sob", md.group(1)) else "derivada"
        holo = {"action": "add", "shape": shape, "n": int(time.time() * 1000)}
        if md.group(2):
            ex = _clean_expr(md.group(2))
            if ex:
                holo["expr"] = ex
        write_control(holo=holo)
        return Result(speak=("Integral na tela, senhor." if shape == "integral"
                             else "Reta tangente na tela, senhor."))

    # geometria molecular nomeada: "geometria tetraédrica"
    if re.search(r"geometria\s+molecular|\bvsepr\b", t) or \
            (re.search(r"geometria", t) and any(k in t for k in _VSEPR)):
        shp = next((v for k, v in _VSEPR.items() if k in t), "geometria_molecular")
        write_control(holo={"action": "add", "shape": shp, "n": int(time.time() * 1000)})
        return Result(speak="Geometria molecular na tela, senhor.")

    # superfície 3D nomeada
    if re.search(r"\bparaboloide\b|\bsela\b", t) and re.search(r"superficie|grafico|3d|\bmostra\w*|\bcria\w*", t):
        shp = "paraboloide" if "paraboloide" in t else "sela"
        write_control(holo={"action": "add", "shape": shp, "n": int(time.time() * 1000)})
        return Result(speak=f"Superfície {shp} na tela, senhor.")

    # modelos nomeados
    _auto = ("tabela", "circulo", "molecula", "onda", "pendulo", "circuito", "campo",
             "vetores", "derivada", "integral", "superficie", "geometria",
             "dna", "sistema_solar", "coracao", "grafico", "translacao", "reflexao",
             "homotetia", "transforma", "lente", "colisao", "arvore", "neuronio", "pilha",
             "esqueleto", "cerebro")
    for pat, name, nome in _MODELS:
        if re.search(pat, t) and (has_verb or name.startswith(_auto)
                                  or re.search(r"\b(triangulo retangulo|corpo livre|plano inclinado)\b", t)):
            write_control(holo={"action": "add", "shape": name, "n": int(time.time() * 1000)})
            return Result(speak=f"{nome} na tela, senhor.")

    # formas geométricas simples
    if has_verb:
        m = re.search(rf"\b(?:{_MK})\b\s+(.+)", t)
        if m:
            for w in m.group(1).split():
                shape = _SHAPES.get(w) or _SHAPES.get(norm(w))
                if shape:
                    write_control(holo={"action": "add", "shape": shape,
                                        "n": int(time.time() * 1000)})
                    return Result(speak=f"{w.capitalize()} na tela, senhor.")
    return None


def _quiz_round(brain, tema: str, n: int) -> "Result":
    """Gera 1 pergunta sobre `tema` e devolve um Result que espera a resposta falada."""
    try:
        q = brain._post(
            [{"role": "system", "content":
              "Você é um professor. Faça UMA pergunta curta de estudo sobre o tema pedido, "
              "nível ensino médio. Só a pergunta, sem numeração, sem a resposta."},
             {"role": "user", "content": f"Tema: {tema}"}], 60, temperature=0.7).strip()
    except Exception:  # noqa: BLE001
        return Result(speak="Não consegui montar a pergunta agora, senhor.")
    q = re.sub(r'^["\-\d.\s]+', "", q).strip()
    if not q:
        return Result(speak="Não consegui montar a pergunta agora, senhor.")

    def avaliar(resposta: str):
        r = (resposta or "").strip().lower()
        if re.search(r"\b(para|parar|chega|desisto|sair do quiz|acabou|encerra)\b", r):
            return "Encerrando o quiz, senhor.", None
        if re.search(r"\b(nao sei|sei la|passa|pula|proxima|nenhuma ideia)\b", r):
            veredito = "Sem problema."
        else:
            try:
                veredito = brain._post(
                    [{"role": "system", "content":
                      "Avalie a resposta do aluno à pergunta. Diga se acertou, errou ou "
                      "acertou em parte, e dê a resposta correta em 1 frase. Máximo 2 frases, "
                      "tom de professor gentil. Trate o aluno por 'senhor'."},
                     {"role": "user", "content": f"Pergunta: {q}\nResposta do aluno: {resposta}"}],
                    90, temperature=0.3).strip()
            except Exception:  # noqa: BLE001
                veredito = "Não consegui avaliar agora, senhor."
        prox = _quiz_round(brain, tema, n + 1)
        return f"{veredito} Próxima: {prox.speak}", (prox.await_reply if not prox.to_llm else None)

    return Result(speak=(f"Pergunta {n}, senhor: {q}" if n == 1 else q),
                  await_reply=avaliar)


_MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
          "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
_FERIADOS = {  # nome -> (dia, mes)  — fixos
    "natal": (25, 12), "reveillon": (31, 12), "ano novo": (1, 1), "fim do ano": (31, 12),
    "virada do ano": (31, 12), "primeiro de maio": (1, 5), "dia do trabalho": (1, 5),
    "sete de setembro": (7, 9), "independencia": (7, 9), "tiradentes": (21, 4),
    "dia das criancas": (12, 10), "nossa senhora aparecida": (12, 10), "finados": (2, 11),
    "proclamacao da republica": (15, 11), "consciencia negra": (20, 11),
    "dia dos namorados": (12, 6), "dia das maes": (11, 5), "dia dos pais": (10, 8),
    "sao joao": (24, 6), "halloween": (31, 10),
}


def _dias_ate(t: str) -> str | None:
    from datetime import date
    hoje = date.today()
    alvo = None
    for k, (d, mth) in _FERIADOS.items():
        if k in t:
            alvo = date(hoje.year, mth, d)
            break
    if not alvo:
        m = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)", t)
        if m and m.group(2) in _MESES:
            alvo = date(hoje.year, _MESES[m.group(2)], int(m.group(1)))
        else:
            m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", t)
            if m:
                y = int(m.group(3) or hoje.year)
                if y < 100:
                    y += 2000
                try:
                    alvo = date(y, int(m.group(2)), int(m.group(1)))
                except ValueError:
                    return None
    if not alvo:
        return None
    if alvo < hoje:
        alvo = alvo.replace(year=alvo.year + 1)
    n = (alvo - hoje).days
    dsem = _DIA_SEMANA[alvo.weekday()]
    if n == 0:
        return "É hoje, senhor!"
    if n == 1:
        return f"Falta 1 dia, senhor. É amanhã, {dsem}."
    return f"Faltam {n} dias, senhor. Cai " + ("num " if dsem in ("sábado", "domingo") else "numa ") + dsem + "."


_DIA_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]

_FUSOS = {
    "toquio": "Asia/Tokyo", "japao": "Asia/Tokyo",
    "nova york": "America/New_York", "new york": "America/New_York", "ny": "America/New_York",
    "los angeles": "America/Los_Angeles", "california": "America/Los_Angeles",
    "londres": "Europe/London", "inglaterra": "Europe/London",
    "paris": "Europe/Paris", "franca": "Europe/Paris",
    "lisboa": "Europe/Lisbon", "portugal": "Europe/Lisbon",
    "berlim": "Europe/Berlin", "alemanha": "Europe/Berlin",
    "madri": "Europe/Madrid", "madrid": "Europe/Madrid", "espanha": "Europe/Madrid",
    "roma": "Europe/Rome", "italia": "Europe/Rome",
    "moscou": "Europe/Moscow", "russia": "Europe/Moscow",
    "pequim": "Asia/Shanghai", "china": "Asia/Shanghai", "xangai": "Asia/Shanghai",
    "dubai": "Asia/Dubai", "india": "Asia/Kolkata", "nova delhi": "Asia/Kolkata",
    "sidney": "Australia/Sydney", "sydney": "Australia/Sydney", "australia": "Australia/Sydney",
    "buenos aires": "America/Argentina/Buenos_Aires", "argentina": "America/Argentina/Buenos_Aires",
    "cidade do mexico": "America/Mexico_City", "mexico": "America/Mexico_City",
    "nova iorque": "America/New_York", "seul": "Asia/Seoul", "coreia": "Asia/Seoul",
}


def _hora_no_mundo(lugar: str) -> str | None:
    lugar = re.sub(r"\s+(agora|hoje|senhor)$", "", lugar).strip()
    tzname = _FUSOS.get(lugar)
    if not tzname:
        tzname = next((v for k, v in _FUSOS.items() if k in lugar or lugar in k), None)
    if not tzname:
        return None
    try:
        from zoneinfo import ZoneInfo
        n = datetime.now(ZoneInfo(tzname))
    except Exception:  # noqa: BLE001
        return None
    per = "da manhã" if 5 <= n.hour < 12 else ("da tarde" if 12 <= n.hour < 18
                                               else ("da noite" if n.hour >= 18 else "da madrugada"))
    disp = {"toquio": "Tóquio", "franca": "França", "italia": "Itália", "russia": "Rússia",
            "china": "China", "india": "Índia", "japao": "Japão", "mexico": "México",
            "sidney": "Sydney", "seul": "Seul"}.get(lugar, lugar.title())
    return f"Em {disp} são {n.hour}h{n.minute:02d} {per}, senhor."


def _clean_expr(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[áàâã]", "a", s)
    s = re.sub(r"^\s*(?:y|f\s*\(?\s*x\s*\)?)\s*=\s*", "", s)   # tira "y =" / "f(x) ="
    s = re.sub(r"\bao\s+quadrado\b", "^2", s)
    s = re.sub(r"\bao\s+cubo\b", "^3", s)
    s = re.sub(r"\belevado\s+a\s+", "^", s)
    s = re.sub(r"\s+mais\s+", "+", s)
    s = re.sub(r"\s+menos\s+", "-", s)
    s = re.sub(r"\s+vezes\s+|\s+multiplicado\s+por\s+", "*", s)
    s = re.sub(r"\s+dividido\s+por\s+|\s+sobre\s+", "/", s)
    s = re.sub(r"\braiz\s+(?:quadrada\s+)?de\s+([a-z0-9]+)", r"sqrt(\1)", s)
    s = re.sub(r"\b(?:seno|sen)\s*(?:de\s+)?([a-z0-9]+)", r"sin(\1)", s)
    s = re.sub(r"\b(?:cosseno|cos)\s*(?:de\s+)?([a-z0-9]+)", r"cos(\1)", s)
    s = re.sub(r"\b(?:tangente|tg)\s*(?:de\s+)?([a-z0-9]+)", r"tan(\1)", s)
    s = re.sub(r"\b(?:por favor|senhor|pra mim|na tela|agora|a funcao|funcao|da funcao)\b", "", s)
    s = re.sub(r"[^0-9a-z^+\-*/(). ]", "", s).strip(" .")
    return re.sub(r"\s+", "", s)

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
# frases de pontuação faladas (2 palavras primeiro, depois 1) -> símbolo
_DICT_MULTI = {
    ("nova", "linha"): "\n", ("quebra", "linha"): "\n", ("novo", "paragrafo"): "\n\n",
    ("ponto", "final"): ".", ("dois", "pontos"): ":", ("ponto", "virgula"): ";",
    ("ponto", "interrogacao"): "?", ("ponto", "exclamacao"): "!",
    ("abre", "parenteses"): "(", ("fecha", "parenteses"): ")",
    ("abre", "aspas"): '"', ("fecha", "aspas"): '"',
}
_DICT_ONE = {
    "virgula": ",", "ponto": ".", "interrogacao": "?", "exclamacao": "!",
    "reticencias": "...", "travessao": "-", "hifen": "-", "parenteses": "",
}
_DICT_TRIPLE = {("ponto", "de", "interrogacao"): "?", ("ponto", "de", "exclamacao"): "!",
                ("ponto", "e", "virgula"): ";"}


def _apply_dictation(text: str) -> str:
    words = text.split()
    if not any(norm(w) in _DICT_ONE or norm(w) in ("nova", "novo", "dois", "abre", "fecha")
               for w in words):
        return text
    out = []
    i = 0
    while i < len(words):
        w0 = norm(words[i])
        t3 = tuple(norm(x) for x in words[i:i + 3])
        t2 = tuple(norm(x) for x in words[i:i + 2])
        if len(t3) == 3 and t3 in _DICT_TRIPLE:
            out.append(_DICT_TRIPLE[t3]); i += 3; continue
        if len(t2) == 2 and t2 in _DICT_MULTI:
            out.append(_DICT_MULTI[t2]); i += 2; continue
        if w0 in _DICT_ONE:
            if _DICT_ONE[w0]:
                out.append(_DICT_ONE[w0])
            i += 1; continue
        out.append(words[i]); i += 1
    s = " ".join(out)
    s = re.sub(r"\s+([.,;:!?)])", r"\1", s)
    s = re.sub(r"([(])\s+", r"\1", s)
    s = re.sub(r"([.,;:!?])(?=[A-Za-zÀ-ÿ])", r"\1 ", s)
    s = re.sub(r" *\n *", "\n", s)
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def type_verbatim(text: str) -> Result:
    paste_text(_apply_dictation(text))
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
    (r"estud\w*|modelo\w*|holograma\w* de (fisica|quimica|biologia|matematica)|"
     r"circulo trigonometrico|plota\w*|grafico|molecula|corpo livre|plano inclinado|"
     r"tabela periodica|celula",
     "Ative a câmera e peça, senhor: \"círculo trigonométrico\", \"plota x ao quadrado\", "
     "\"molécula da água\", \"diagrama de corpo livre\", \"plano inclinado\", \"tabela periódica\", "
     "\"fórmula do volume da esfera\", ou \"célula animal\"."),
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
    (r"pesquis\w*|busc\w*|fato|sab\w* (mais )?sobre|informacao sobre|"
     r"quem foi|o que e|significado",
     "Pergunte \"Jarvis, quem foi\" ou \"o que é\" e o assunto, senhor — eu busco na Wikipédia."),
    (r"estud\w*|quiz|flashcard|me test\w*|me pergunt\w*|revis\w* materia",
     "Diga \"Jarvis, me faz uma pergunta sobre\" e a matéria, senhor. Responda em voz alta e "
     "eu corrijo. \"Para\" encerra."),
    (r"que (musica|som) (ta|esta) tocando|nome da musica|calcul\w*|conta de|"
     r"converter?|quantos? (quilo|metro|milha)|cotacao|bitcoin|dolar",
     "Pergunte direto, senhor: \"que música é essa?\", \"quanto é 15% de 200?\", "
     "\"quantos km são 5 milhas?\", \"quanto tá o dólar?\"."),
    (r"print|captura de tela|area de transferencia|janela|monitor|"
     r"minimiz\w*|maximiz\w*",
     "\"Jarvis, tira um print\", \"minimiza tudo\", \"maximiza a janela\", "
     "\"o que tem na área de transferência\", senhor."),
    (r"junt\w* (dois|2) comando|(dois|2) coisas de uma vez|(um comando|tudo) de uma vez",
     "Pode juntar com \"e\", senhor: \"Jarvis, abre o navegador e pesquisa gatos\"."),
]


def dispatch(raw: str, cfg: dict, speak, brain, _depth: int = 0) -> Result:
    t = norm(raw)
    dz = cfg.get("danger", {})

    if not t:
        return Result(speak=cfg["assistant"].get("attention_reply", "Pois não, senhor?"))

    # palavra de parada solta ("para", "chega", "obrigado"...) — só como PALAVRA
    # inteira (senão "paraboloide", "chega mais" etc. eram engolidos)
    _stop_hit = t in STOP_WORDS or (
        len(t.split()) <= 3
        and any(re.search(rf"\b{re.escape(w)}\b", t) for w in STOP_WORDS))
    if _stop_hit:
        # exceções: "cancela ..." (desligamento) e "para de desenhar / chega de medir"
        # (modos da câmera) — tratados mais abaixo
        if "cancel" not in t and not re.search(
                r"\b(desenh\w*|desenhar|caneta|pincel|lapis|risco\w*|tra[cç]o\w*|"
                r"rabisc\w*|medi\w*|medir|regua|modo)\b", t):
            return Result(speak="Às ordens, senhor.", stop=True)

    # --- Jarvis aprende / esquece comandos ("Jarvis, aprende ...") ---
    #     (não confundir com "aprende meu rosto" — isso é o reconhecimento facial)
    if teach is not None and skills_extra is not None and brain is not None \
            and not re.search(r"\b(meu|o meu)\s+rosto\b|\besse sou eu\b", t):
        if teach.match_list(t):
            nomes = skills_extra.learned_names()
            if not nomes:
                return Result(speak="Ainda não aprendi nenhum comando, senhor.")
            return Result(speak="Comandos que aprendi, senhor: " + ", ".join(nomes) + ".")
        if teach.match_forget(t):
            alvo = re.sub(r".*\bcomando\b\s*", "", t).strip() or t
            ok = skills_extra.remove_learned(alvo)
            return Result(speak=("Esqueci o comando, senhor." if ok
                                 else "Não achei esse comando pra esquecer, senhor."))
        if teach.match_enter(t):
            if len(t.split()) < 5:
                return Result(speak="Pode falar o comando, senhor: \"aprende: quando "
                                    "eu disser tal coisa, você faz tal coisa\".")
            speak("Deixa eu montar esse comando, senhor.")
            spec = teach.parse(raw, brain)
            if not spec:
                return Result(speak="Não consegui montar o comando, senhor. "
                                    "Tente: \"aprende: quando eu disser tal coisa, "
                                    "você fala tal coisa\".")

            def _save(_sp=spec):
                skills_extra.add_learned(_sp)
                return f"Pronto, senhor. O comando \"{_sp['name']}\" já está ativo."
            return Result(confirm=(teach.confirm_text(spec), _save))

    # --- reconhecimento facial: cadastrar / esquecer / consultar ---
    if facemod is not None:
        if facemod.match_enroll(t):
            nome = str(cfg.get("profile", {}).get("active", "")).strip().lower() or "arthur"
            write_control(view="camera",
                          face_enroll=nome + "|" + str(int(time.time())))
            return Result(speak="Olhe pra câmera um instante, senhor. "
                                "Estou memorizando o seu rosto.")
        if facemod.match_forget(t):
            from common import _SHARED
            try:
                import json as _j
                f = _SHARED / "faces.json"
                db = _j.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
                nome = str(cfg.get("profile", {}).get("active", "")).strip().lower() or "arthur"
                if db.pop(nome, None) is not None:
                    f.write_text(_j.dumps(db), encoding="utf-8")
                    return Result(speak="Esqueci o seu rosto, senhor.")
            except Exception:  # noqa: BLE001
                pass
            return Result(speak="Não tinha o seu rosto guardado, senhor.")
        if facemod.match_query(t):
            from common import _SHARED
            try:
                import json as _j
                fj = _SHARED / "face.json"
                cur = _j.loads(fj.read_text(encoding="utf-8")).get("name", "") if fj.is_file() else ""
            except Exception:  # noqa: BLE001
                cur = ""
            if cur and cur not in ("", "desconhecido", "__enrolled__"):
                return Result(speak=f"Reconheço o senhor, {cur.capitalize()}.")
            if cur == "desconhecido":
                return Result(speak="Vejo um rosto, mas não reconheço, senhor.")
            return Result(speak="Não estou te vendo na câmera agora, senhor. "
                                "Abra a câmera e diga \"aprende meu rosto\".")

    # --- modo aula: "me dá uma aula sobre X" ---
    if brain is not None:
        try:
            import aula
            _at = aula.match(t)
            if _at:
                speak(f"Um momento, senhor. Montando a aula sobre {_at}.")
                return aula.start(_at, cfg, brain, speak)
        except Exception as exc:  # noqa: BLE001
            log(f"aula: {exc}")

    # --- modo estudo: entrar / sair / atalhos da sessão ---
    if study is not None:
        if study.active() and study.match_exit(t):
            return Result(speak=study.exit_session(brain))
        _sm = study.match_enter(t)
        if _sm:
            return Result(speak=study.enter(_sm, cfg, brain))   # entra ou troca de modo
        if study.active() and _depth == 0:      # atalhos de sessão só na fala do usuário
            _sr = study.handle(raw, cfg, speak, brain)
            if _sr is not None:
                return _sr

    # --- encadear 2 comandos: "abre o navegador e pesquisa X" ---
    if _depth == 0 and brain is not None:
        parts = re.split(r"\s+(?:e\s+depois|e\s+tambem|e\s+ai|e|depois|,\s*e|,\s*depois)\s+",
                         raw.strip(), maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and all(2 <= len(p.split()) <= 10 for p in parts) \
                and not re.search(r"\b(por ?que|porque|quando|seno|cosseno|entao)\b", t) \
                and not re.match(r"^(anota|digita|escrev|lembr|pedido|nota|me lembr|toc|coloc|"
                                 r"bota|poe|manda|escut|ouv|pesquis|busc|procur|googl)", t):
            r1 = dispatch(parts[0], cfg, speak, brain, _depth=1)
            r2 = dispatch(parts[1], cfg, speak, brain, _depth=1)
            if r2.to_llm and not r1.to_llm:
                # 2ª parte sem verbo? tenta com o verbo da 1ª ("cria um cubo E uma esfera")
                vb = parts[0].split()[0]
                if re.match(r"(?i)^(cria|faz|abre|mostra|poe|toca|coloca|liga|plota)", vb):
                    r2b = dispatch(f"{vb} {parts[1]}", cfg, speak, brain, _depth=1)
                    if not r2b.to_llm:
                        r2 = r2b
            if not r1.to_llm and not r2.to_llm and not r1.confirm and not r2.confirm \
                    and not r1.fallback and not r2.fallback:
                if r1.speak:
                    speak(r1.speak)
                return Result(speak=(r2.speak or r1.speak or ""))

    # --- velocidade da fala ---
    if re.search(r"\bfal\w*\s+mais\s+(devagar|lento|calmo|pausad)|\bmais\s+devagar\b|"
                 r"\bfal\w*\s+mais\s+(rapido|ligeiro|depressa)|\bmais\s+rapido\b", t):
        mo = getattr(speak, "__self__", None)
        if mo and hasattr(mo, "adjust_rate"):
            faster = bool(re.search(r"\b(rapido|ligeiro|depressa)\b", t))
            return Result(speak=mo.adjust_rate(faster))

    # --- repetir a última fala ---
    if re.search(r"\b(repete|repita|de novo|nao entendi|o que voce (disse|falou)|"
                 r"pode repetir|como e que e|fala de novo)\b", t) and len(t.split()) <= 6:
        last = getattr(getattr(speak, "__self__", None), "last", "") or getattr(brain, "last_reply", "")
        return Result(speak=(last or "Não falei nada ainda, senhor."))

    # --- esquecer o contexto da conversa ---
    if re.search(r"\b(esquece|esquec\w+|novo assunto|mud\w+ de assunto|comeca de novo|"
                 r"limpa\w*\s+(a\s+)?(conversa|contexto|memoria))\b", t) and len(t.split()) <= 6:
        if brain is not None and hasattr(brain, "forget"):
            brain.forget()
        return Result(speak="Esquecido, senhor. Assunto novo.")

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

    # --- catálogo declarativo (voice/skills_extra.toml) — o que o usuário
    #     adicionou tem prioridade sobre a torre de regex abaixo ---
    if skills_extra is not None:
        _redisp = (lambda p: dispatch(p, cfg, speak, brain, _depth=_depth + 1)) \
            if _depth < 2 else None
        _cr = skills_extra.match(t, raw, Result, _redisp)
        if _cr is not None:
            return _cr

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

    # --- modo apresentação (varrer a mão = próximo/anterior slide) ---
    if re.search(r"\b(sai\w*|sair|fecha\w*|encerra\w*|para\w*|termin\w*|acab\w*)\b.*"
                 r"\b(apresenta[cç][aã]o|slides?|palestra)\b", t):
        write_control(present=False)
        return Result(speak="Modo apresentação encerrado, senhor.")
    if re.search(r"\bmod[eo]\s+(apresenta[cç][aã]o|slides?|palestra)\b|"
                 r"\bvou\s+apresentar\b|\bcomeca\w*\s+a\s+apresenta", t):
        write_control(view="camera", present=True, media_gestures=True)
        return Result(speak="Modo apresentação, senhor. Varra a mão pra trocar de slide.")

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

    # --- manipular a forma selecionada: travar / duplicar / explodir ---
    if re.search(r"\b(trava\w*|tranca\w*|fixa\w*|prende\w*|congela\w*)\s+(essa|a|o|esse|isso|a forma|o holograma)\b|"
                 r"\btrava isso\b", t):
        write_control(holo={"action": "lock", "on": True, "n": int(time.time() * 1000)})
        return Result(speak="Travei a forma, senhor.")
    if re.search(r"\b(solta\w*|destrava\w*|destranca\w*|libera\w*)\s+(essa|a|o|esse|isso|a forma|o holograma)\b|"
                 r"\bsolta isso\b|\bdestrava\b", t):
        write_control(holo={"action": "lock", "on": False, "n": int(time.time() * 1000)})
        return Result(speak="Soltei, senhor.")
    if re.search(r"\b(copia|duplica|clona)\w*\s+(essa|a|o|esse|isso|a forma|o holograma)\b|"
                 r"\b(copia|duplica|clona) isso\b|\bfaz uma copia\b", t):
        write_control(holo={"action": "dup", "n": int(time.time() * 1000)})
        return Result(speak="Dupliquei, senhor.")
    if re.search(r"\bexplod\w+|\bdesmont\w+\s+(essa|a|o|isso)\b|\bseparar? as pecas\b|"
                 r"\babre\s+(essa|a)\s+(molecula|forma|estrutura)\b", t):
        write_control(holo={"action": "explode", "n": int(time.time() * 1000)})
        return Result(speak="Feito, senhor.")

    # --- modos da câmera: desenho / medida / normal ---
    # SAIR do modo vem primeiro: "sai do modo desenho" não pode reativar o desenho.
    _cam_noun = re.search(r"\b(desenh\w*|desenhar|caneta|lapis|pincel|risco\w*|tra[cç]o\w*|"
                          r"rabisc\w*|medi\w*|medir|regua|medi[cç]\w+|distancia)\b", t)
    _exit_word = re.search(r"\bmodo\s+normal\b|volta\w*\s+ao\s+normal|"
                           r"\bsai\w*\s+d[eoa]\b|\bsair\b|\bpar[ae]\s+de\b|\bparar?\b|"
                           r"\bchega\s+de\b|\bpode\s+(parar|sair)\b|"
                           r"\b(encerra\w*|termina\w*|acaba\w*|desativa\w*|desliga\w*|"
                           r"fecha\w*|cancela\w*)\b", t)
    if re.search(r"\bmodo\s+normal\b|volta\w*\s+ao\s+normal\b|"
                 r"\bpar[ae]\s+de\s+(desenhar|medir)\b|\bchega\s+de\s+(desenhar|medir)\b", t) \
            or (_cam_noun and _exit_word):
        write_control(holo={"action": "mode", "mode": "normal", "n": int(time.time() * 1000)})
        return Result(speak="Pronto, senhor — voltei ao modo normal.")
    if re.search(r"\b(limpa\w*|apaga\w*|tira|remove\w*|some com|deleta\w*|zera\w*)\s+"
                 r"(o\s+|a\s+|os\s+|as\s+|esse\s+|esses\s+|essa\s+|essas\s+|meu\s+|meus\s+|"
                 r"minha\s+|minhas\s+|todo\s+|toda\s+|tudo\s+que\s+|o que\s+)*"
                 r"(desenho\w*|tra[cç]o\w*|risco\w*|rabisc\w*|medida\w*|medi[cç]\w+)\b|"
                 r"\b(limpa\w*|apaga\w*|tira)\s+(o|tudo|isso)?\s*(que\s+)?(eu\s+)?"
                 r"(desenhei|risquei|tracei|marquei)\b", t):
        write_control(holo={"action": "clear_ink", "n": int(time.time() * 1000)})
        return Result(speak="Limpei o desenho e as medidas, senhor.")
    if re.search(r"\bmodo\s+(desenho|caneta|lapis|pincel)\b|deixa eu desenhar|quero desenhar|"
                 r"ativa\w*\s+(o\s+)?desenho|desenhar? no ar|come[cç]a\w*\s+a desenhar", t):
        write_control(holo={"action": "mode", "mode": "draw", "n": int(time.time() * 1000)})
        return Result(speak="Modo desenho, senhor. Aponte o indicador e desenhe no ar.")
    if re.search(r"\bmodo\s+(medi\w+|regua|distancia)\b|quero medir|deixa eu medir|"
                 r"ativa\w*\s+(a\s+)?(medida|regua)|medir? (a )?distancia|come[cç]a\w*\s+a medir", t):
        write_control(holo={"action": "mode", "mode": "measure", "n": int(time.time() * 1000)})
        return Result(speak="Modo medida, senhor. Pince dois pontos.")

    # --- abrir o painel de configurações no app ---
    if re.search(r"\b(abr\w*|mostra\w*|ver as|entra n\w*)\s+(as\s+)?configura\w+|"
                 r"\bmodo\s+configura\w+|\bpainel\s+de\s+configura\w+|\bajustes do jarvis\b|"
                 r"\bmuda\w*\s+(uma\s+)?configura\w+", t):
        write_control(holo={"action": "settings", "n": int(time.time() * 1000)})
        return Result(speak="Abri as configurações, senhor.")

    # --- ler QR code pela câmera ---
    if re.search(r"\b(le\w*|escaneia\w*|escanear|scann?e\w*|decifra\w*)\s+(o\s+|esse\s+|este\s+)?"
                 r"(qr|qr\s?code|codigo qr|q r code)\b|\bqr\s?code\b", t):
        write_control(view="camera", scan="qr")
        return Result(speak="Aponte o QR code pra câmera, senhor.")

    # --- OCR: ler texto pela câmera ---
    if re.search(r"\b(le\w*|reconhec\w*|escaneia\w*|captur\w*|copia\w*|transcrev\w*|"
                 r"digitaliz\w*)\s+(o\s+|esse\s+|este\s+|essa\s+|a\s+)?"
                 r"(texto|escrito|frase|paragrafo|palavra|pagina|folha|placa|etiqueta|documento)\b|"
                 r"\bo que (esta|ta)\s+escrito\b|\bque diz (a|o|esse|aquela)\b", t):
        write_control(view="camera", scan="ocr")
        return Result(speak="Aponte o texto pra câmera, senhor. Vou ler.")

    r = _holo_models(t, raw)
    if r is not None:
        return r

    # --- Jarvis INVENTA um holograma: só chega aqui se nenhum modelo pronto casou ---
    if invent is not None and brain is not None:
        _tema = invent.match(t)
        if _tema:
            speak("Deixa eu montar isso, senhor. Um instante.")
            spec = invent.make_spec(_tema, brain)
            if not spec:
                return Result(speak=f"Não consegui montar {_tema}, senhor. Tente descrever "
                                    "de outro jeito.")
            write_control(holo={"action": "add", "shape": "spec", "spec": spec,
                                "n": int(time.time() * 1000)})
            return Result(speak=f"{spec.get('title', _tema)} na tela, senhor. "
                                "Se ficou estranho, é que eu improvisei.")

    # --- cancelar desligamento/reinício ---
    if re.search(r"cancela\w*.*(deslig|reinic|reinici)", t) or re.fullmatch(r"cancela\w*", t):
        _run("shutdown", "/a")
        return Result(speak="Cancelei, senhor.")

    # --- tradução ---
    _lang_after = re.search(r"\b(?:em|pra|para|pro)\s+(?:o\s+)?(ingles|espanhol|frances|alemao|"
                            r"italiano|japones|mandarim|chines|russo|coreano|holandes|latim|arabe)\b",
                            norm(raw))
    if (re.search(r"\b(traduz|traduza|traducao de|como se (diz|fala)|"
                  r"como (e|que e) que se (diz|fala))\b", t)
            or (re.search(r"\bcomo se escreve\b", t) and _lang_after)) \
            and not re.match(r"^(soletra|me diz as letras)", t):
        fala = translate.handle(raw, brain)
        if fala:
            return Result(speak=fala)

    # --- soletrar ---
    m = re.search(r"\b(soletra\w*|soletre|me diz as letras de|como se escreve)\s+(?:a palavra\s+)?(.+)", t)
    if m:
        w = re.sub(r"[^a-zà-ÿ]", "", m.group(2).split()[0])
        if w:
            return Result(speak=", ".join(c.upper() for c in w) + ", senhor.")

    # --- hora no mundo ---
    m = re.search(r"\bque horas?\s.*?\b(?:em|no|na|nos|nas)\s+([a-zà-ÿ][a-zà-ÿ ]+?)\s*(?:agora|hoje|senhor)?\s*$", t)
    if m and _hora_no_mundo(m.group(1).strip()):
        return Result(speak=_hora_no_mundo(m.group(1).strip()))

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

    # --- quantos dias até <data/feriado> ---
    if re.search(r"\bquantos?\s+dias?\s+(faltam?|ate|pra|para)\b|\bdias?\s+ate\b", t):
        fala = _dias_ate(t)
        if fala:
            return Result(speak=fala)

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
    if re.search(r"\b(cancela|apaga|limpa|tira|para)\w*\s+(o |os |todos os |meus )?"
                 r"(lembretes?|timers?|alarmes?|cronometr\w+|pomodoro|contagem)\b", t):
        write_app_state(timer={"end": 0})
        if re.search(r"\b(cronometr\w*|pomodoro|timer|contagem)\b", t) and not re.search(r"lembrete", t):
            # só o cronômetro visual; mantém lembretes com texto
            return Result(speak="Cronômetro cancelado, senhor.")
        n = reminders.clear_all()
        return Result(speak=("Limpei os lembretes, senhor." if n else "Não tinha lembrete, senhor."))
    m = re.search(r"\b(me lembr\w+|lembr[ae]\s+(?:de\s+)?mim|me avis\w+|me acord\w+|me cham\w+|"
                  r"p[oõ]e\s+(?:um\s+)?(?:lembrete|timer|alarme|despertador|pomodoro|cronometr\w+)|"
                  r"timer\s+(?:de|pra|para)|cronometr\w+\s+(?:de|pra|para)|pomodoro\s+(?:de|pra|para)|"
                  r"alarme\s+(?:de|pra|para|das?)|despertador\s+(?:pra|para|das?))\b(.*)", t)
    if m:
        rest = m.group(2).strip()
        rec = reminders.parse_recurring(rest)
        if rec:
            ts, human, rule = rec
            msg = _reminder_msg(re.sub(r"\b(todo dia|todos os dias|toda \w+|de hora em hora|"
                                       r"diariamente|semanalmente)\b", "", rest))
            reminders.add(msg or "(sem descrição)", ts, rule=rule)
            return Result(speak=f"Combinado, senhor. Eu aviso {human}"
                          + (f": {msg}." if msg else "."))
        when = reminders.parse_when(rest)
        if not when:
            return Result(speak="Pra quando, senhor? Diga um tempo, tipo 'em 20 minutos' ou 'às 15 horas'.")
        ts, human = when
        msg = _reminder_msg(rest)
        if not reminders.add(msg or "(sem descrição)", ts):
            return Result(speak="Esse lembrete o senhor acabou de pedir — já está anotado.")
        # timer/cronômetro/pomodoro sem texto -> mostra a contagem no HUD
        if not msg and re.search(r"\b(timer|cronometr\w+|pomodoro|contagem)\b", t):
            write_app_state(timer={"end": ts, "label": "pomodoro" if "pomodoro" in t else "timer"})
        prefixo = "Às" if (":" in human or "meio-dia" in human or "meia-noite" in human) else "Daqui a"
        if prefixo == "Às" and ":" in human:
            hh, mm = human.split(" de ")[0].split(":")
            human = f"{int(hh)} horas" if mm == "00" else f"{int(hh)}h{mm}"
            if "amanhã" in when[1]:
                human += ", amanhã"
        if msg:
            return Result(speak=f"Combinado, senhor. {prefixo} {human} eu aviso: {msg}.")
        return Result(speak=f"Marcado pra {human}, senhor. Eu aviso." if prefixo == "Às"
                      else f"Timer de {human}, senhor. Eu aviso quando terminar.")

    # --- clima ---
    if re.search(r"\b(tempo|clima|previs\w+|vai chov\w+|ta chov\w+|esta chov\w+|"
                 r"quantos graus|qual (a )?temperatura|ta (frio|calor|quente)|"
                 r"faz (frio|calor)|tempo la fora)\b", t) and not re.search(
                 r"\b(quanto tempo|ao mesmo tempo|com o tempo|perde\w* tempo|um tempo|"
                 r"cpu|gpu|placa|processador|\bpc\b|computador|maquina|notebook)\b", t):
        dia = "amanhã" if re.search(r"\bamanha\b", t) else "hoje"
        _tw = "hoje|amanha|agora|de manha|de tarde|de noite|hoje a noite|essa semana|senhor|la fora|aqui|fora"
        mc = re.search(rf"\b(?:em|no|na)\s+([a-z][a-z\s]+?)(?:\s+(?:{_tw}))*\s*$", t)
        cidade = None
        if mc:
            cand = re.sub(rf"\b(?:{_tw})\b", "", mc.group(1)).strip()
            if cand and cand not in ("casa", "mim", "voce", "cidade", "regiao"):
                cidade = cand
        return Result(speak=weather.report(cfg, cidade, dia))

    # --- notícias ---
    if re.search(r"\b(noticias?|manchetes?|novidades do dia|o que (esta|ta) acontecendo|"
                 r"o que rolou|me atualiza|jornal de hoje|principais noticias)\b", t):
        write_app_state(phase="searching")
        mq = re.search(r"\b(?:noticias?|manchetes?)\s+(?:de|sobre|do|da|dos|das)\s+(.+)", t)
        return Result(speak=news.headlines(mq.group(1) if mq else ""))

    # --- diário de bordo: "o que eu fiz hoje" ---
    try:
        import diary
        _dq = diary.match(t)
        if _dq:
            return Result(speak=diary.resumo(_dq, brain))
    except Exception as exc:  # noqa: BLE001
        log(f"diary: {exc}")

    # --- contas / porcentagem / conversão de unidades e moeda ---
    fala = calc.handle(t)
    if fala is not None:
        return Result(speak=fala)

    # --- responder a partir dos materiais de estudo do Senhor (RAG-lite local) ---
    try:
        import materials
        mr = materials.handle(raw, cfg, brain)
        if mr is not None:
            return mr
    except Exception as exc:  # noqa: BLE001
        log(f"materials: {exc}")

    # --- consultas via APIs sem chave (ações, CEP, feriado, ar, sol/lua, história…) ---
    #     (o phase="searching" quem seta é o facts._get, só quando REALMENTE busca)
    try:
        import facts
        fr = facts.handle(raw, cfg, brain)
        if fr is not None:
            return fr
    except Exception as exc:  # noqa: BLE001
        log(f"facts: {exc}")

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

    # --- "que música é essa?" ---
    if re.search(r"\b(que (musica|som|faixa) (e|esta) (essa|tocando)|qual (musica|nome da musica)|"
                 r"nome dess[ae] (musica|som)|quem (canta|toca) iss[oa]|que (musica|som) e ess[ae])\b", t):
        import media
        return Result(speak=media.now_playing())

    # --- controle de mídia ---
    if re.search(r"\b(proxima|pula|avanca|passa)\b.*\b(musica|faixa|som)\b|\bpula essa\b|"
                 r"\bproxima musica\b", t):
        tap(VK["MEDIA_NEXT"]); return Result(speak="")
    if re.search(r"\b(volta|anterior)\b.*\b(musica|faixa)\b|\bmusica anterior\b", t):
        tap(VK["MEDIA_PREV"]); return Result(speak="")
    if re.search(r"\bpausa\w*\b|\bpara a musica\b|\bpara o som\b", t):
        tap(VK["MEDIA_PLAY"]); return Result(speak="")
    if re.fullmatch(r"(toca|continua|retoma|play)\w*", t):
        tap(VK["MEDIA_PLAY"]); return Result(speak="")
    if re.search(r"\b(do comeco|desde o inicio|de novo essa|reinicia (a )?musica|recomeca)\b", t):
        import media
        media.restart_track(); return Result(speak="")
    m = re.search(r"\b(adianta\w*|avanca\w*|pula|volta\w*|retrocede\w*)\s+(\d{1,3})\s+"
                  r"(segundos?|minutos?)\b", t)
    if m:
        import media
        secs = int(m.group(2)) * (60 if m.group(3).startswith("min") else 1)
        if m.group(1).startswith(("volta", "retro")):
            secs = -secs
        media.seek(secs)
        return Result(speak="")

    # --- screenshot ---
    if re.search(r"\b(tira|faz|captur\w+|bat\w+)\s+(um\s+|uma\s+)?(print|screenshot|foto da tela|"
                 r"captura de tela|imagem da tela)\b|\bprint da tela\b|\bprintar\b", t):
        combo("WIN", "SNAPSHOT")
        return Result(speak="Print salvo em Imagens, na pasta Capturas de Tela, senhor.")

    # --- lista de tarefas ---
    try:
        import tasks
        mt = re.search(r"\b(adiciona|anota|p[oõ]e|bota|coloca|acrescenta)\s+(?:na\s+lista\s+|"
                       r"nas\s+tarefas\s+|uma\s+tarefa\s+)?(.+?)(?:\s+na\s+lista|\s+nas\s+tarefas)?$", t)
        if mt and re.search(r"\b(lista|tarefa|afazer|to-?do|pend[êe]ncia)\b", t):
            return Result(speak=tasks.add(mt.group(2)))
        if re.search(r"\b(minhas|quais|que|lista de)\s+(tarefas?|afazeres|pend[êe]ncias?)\b|"
                     r"\bo que (eu )?(tenho|preciso) (pra|para) fazer\b|\bminha lista\b", t):
            return Result(speak=tasks.listar())
        mc = re.search(r"\b(risca|marca|conclui|termina|feito|completa|tira)\s+(?:a\s+|o\s+|"
                       r"da\s+|de\s+)?(?:tarefa\s+)?(.+?)(?:\s+(?:como\s+)?(?:feita|feito|conclu[ií]d\w+|pront\w+))?$", t)
        if mc and re.search(r"\btarefa|\blista|risca\b|conclui\b", t):
            return Result(speak=tasks.concluir(mc.group(2)))
        if re.search(r"\blimpa\s+(a\s+)?(lista|minhas tarefas)\b|\bapaga\s+(as\s+)?tarefas\b", t):
            so_feitas = bool(re.search(r"\b(feitas|conclu[ií]d\w+|pronto|prontas)\b", t))
            return Result(speak=tasks.limpar(so_feitas))
    except Exception as exc:  # noqa: BLE001
        log(f"tasks: {exc}")

    # --- meus memos de voz ---
    if re.search(r"\b(meus|quais|ultimos?|últimos?|le|lê)\s+memos?\b|\bmemos? de voz\b|"
                 r"\bo que eu gravei\b", t):
        d = HERE / "memos"
        arqs = sorted(d.glob("*.txt"), reverse=True)[:5] if d.is_dir() else []
        if not arqs:
            return Result(speak="Não tem nenhum memo gravado, senhor.")
        linhas = []
        for a in arqs:
            try:
                txt = a.read_text(encoding="utf-8").strip().replace("\n", " ")
            except OSError:
                continue
            dia = a.stem.replace("_", " às ")
            linhas.append(f"{dia}: {txt[:80]}")
        return Result(speak="Seus memos, senhor. " + " ... ".join(linhas))

    # --- temperatura CPU/GPU ---
    if re.search(r"\btemperatura\b.*\b(cpu|gpu|placa|processador|pc|computador|maquina|notebook)\b|"
                 r"\b(cpu|gpu|placa|processador)\b.*\btemperatura\b|"
                 r"\b(quente|esquentando|aquecid\w+|fervendo)\b.*\b(cpu|gpu|placa|pc|computador|maquina|notebook)\b|"
                 r"\b(o|meu)\s+(pc|computador|notebook|processador)\s+(ta|esta|está)\s+(quente|esquentando)\b", t):
        try:
            import hud
            s = hud._sys_snapshot()
            partes = []
            if s.get("gpu_t") is not None:
                partes.append(f"GPU a {s['gpu_t']} graus ({s.get('gpu', 0)}% de uso)")
            if s.get("cpu_t") is not None:
                partes.append(f"CPU a {s['cpu_t']} graus")
            elif not partes:
                return Result(speak="Não consigo ler as temperaturas nessa máquina, senhor.")
            if s.get("cpu_t") is None and partes:
                partes.append("a da CPU o Windows não deixa ver sem administrador, senhor")
            return Result(speak=", ".join(partes) + ".")
        except Exception as exc:  # noqa: BLE001
            log(f"temp: {exc}")
            return Result(speak="Não consegui as temperaturas, senhor.")

    # --- o que está pesado (top processos) ---
    if re.search(r"\bo que (ta|esta|está)\s+(pesado|pesando|consumindo|comendo|travando)|"
                 r"\bque programa\s+(ta|esta|está)\s+(usando|comendo|consumindo)|"
                 r"\buso de (cpu|memoria|mem[óo]ria)\b|\bo que (ta|esta) usando (mais )?(cpu|mem)", t):
        try:
            import psutil
            psutil.cpu_percent(interval=None)
            time.sleep(0.4)
            procs = []
            for p in psutil.process_iter(["name", "cpu_percent", "memory_info"]):
                try:
                    procs.append((p.info["name"] or "?", p.info["cpu_percent"] or 0,
                                  (p.info["memory_info"].rss if p.info["memory_info"] else 0) / 1024**2))
                except Exception:  # noqa: BLE001
                    pass
            top_cpu = sorted(procs, key=lambda x: -x[1])[:3]
            top_mem = sorted(procs, key=lambda x: -x[2])[:3]
            return Result(speak="CPU, senhor: " + ", ".join(f"{n} {c:.0f}%" for n, c, _ in top_cpu) +
                                ". Memória: " + ", ".join(f"{n} {m:.0f} mega" for n, _, m in top_mem) + ".")
        except Exception as exc:  # noqa: BLE001
            log(f"top procs: {exc}")
            return Result(speak="Não consegui checar os processos, senhor.")

    # --- ler em voz alta ---
    try:
        import read_aloud
        if re.search(r"\bpar\w*\s+de\s+ler\b|\bpode\s+parar\s+de\s+ler\b|\bchega\s+de\s+ler\b|"
                     r"\bfecha\s+a\s+leitura\b", t) or (read_aloud.reading() and re.search(r"^para$", t)):
            read_aloud.stop()
            return Result(speak="Parei a leitura, senhor.")
        if re.search(r"\bl[eê]\w*\s+(isso|pra mim|o texto|essa|esse|a pagina|essa pagina|"
                     r"o arquivo|esse arquivo|essa materia|em voz alta|pra mim isso)\b|"
                     r"\bnarr\w+\s+(isso|o texto|essa pagina)\b|\bme l[eê]\b", t):
            src = read_aloud.source_text(t)
            if not src:
                return Result(speak="Não achei texto pra ler, senhor. Copie algo ou diga "
                                    "\"lê esse arquivo\" e o caminho.")
            mo = getattr(speak, "__self__", None)
            if mo is None:
                return Result(speak="Não consigo narrar agora, senhor.")
            return Result(speak=read_aloud.start(mo, src[0], src[1]))
    except Exception as exc:  # noqa: BLE001
        log(f"read_aloud: {exc}")

    # --- esvaziar a lixeira ---
    if re.search(r"\b(esvazia|limpa|despeja)\s+(a\s+)?lixeira\b", t):
        def _lixeira():
            _run("powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
            return "Lixeira esvaziada, senhor."
        return Result(confirm=("Confirma esvaziar a lixeira, senhor? Não dá pra desfazer.", _lixeira))

    # --- área de transferência ---
    m = re.search(r"^(?:copia|poe|bota)\s+(?:pra|para|na|no)?\s*(?:area de transferencia|"
                  r"transferencia|clipboard|memoria)\s*[:,]?\s*(.+)", t)
    if m:
        from common import set_clipboard
        set_clipboard(m.group(1).strip())
        return Result(speak="Copiado, senhor.")
    if re.search(r"\b(o que (tem|ta|esta)|le|mostra|cola)\s+.*\b(area de transferencia|clipboard|transferencia)\b|"
                 r"\bque copiei\b", t):
        from common import get_clipboard
        txt = get_clipboard().strip()
        if not txt:
            return Result(speak="A área de transferência está vazia, senhor.")
        return Result(speak=(txt if len(txt) <= 200 else txt[:200] + "…"))

    # --- janelas ---
    if re.search(r"\b(minimiza\w*|esconde\w*|abaixa\w*|oculta\w*)\s+(tudo|todas as janelas|as janelas)\b|"
                 r"\bmostra a area de trabalho\b|\bmostrar? o desktop\b", t):
        combo("WIN", "D"); return Result(speak="")
    if re.search(r"\bmaximiza\w*\s+(essa|a|esta)?\s*janela\b|\bjanela em tela cheia\b", t):
        combo("WIN", "UP"); return Result(speak="")
    if re.search(r"\bminimiza\w*\s+(essa|a|esta)?\s*janela\b", t):
        combo("WIN", "DOWN"); return Result(speak="")
    if re.search(r"\b(joga|manda|passa|move)\s+.*\b(outra tela|segundo monitor|monitor da (direita|esquerda)|"
                 r"pro lado)\b", t):
        combo("WIN", "SHIFT", "RIGHT"); return Result(speak="")
    if re.search(r"\b(encaixa|joga)\s+.*\b(esquerda|direita)\b|\bdivide a tela\b", t):
        combo("WIN", "LEFT" if "esquerda" in t else "RIGHT"); return Result(speak="")

    # --- bloquear tela --- (pede confirmação, igual suspender/desligar:
    #     travar sem querer deixa o Senhor pra fora até digitar a senha)
    if re.search(r"\bbloqueia?\b.*\b(tela|pc|computador|maquina)\b|\btrava a tela\b|"
                 r"\btranca (o )?(pc|computador|a tela)\b", t):
        if not dz.get("allow_lock", True):
            return Result(speak="O bloqueio de tela está desativado na configuração, senhor.")
        return Result(confirm=("Confirma bloquear a tela, senhor? O Senhor vai "
                               "precisar da senha pra voltar.",
                               lambda: (_lock(), "Trancado, senhor.")[1]))

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

    # --- ditado direcionado: "escreve no bloco de notas: ..." ---
    m = re.search(r"^(?:digit\w*|escrev[ae]|poe|transcrev\w*|anota)\s+"
                  r"(?:isso\s+)?n[oa]\s+(.+?)\s*[:,]\s*(.+)", raw.strip(), flags=re.IGNORECASE)
    if m:
        if not dz.get("allow_typing", True):
            return Result(speak="A digitação está desativada, senhor.")
        alvo, texto = m.group(1).strip(), m.group(2).strip()
        r = open_target(alvo, cfg, web_fallback=False)
        if not r.fallback:
            time.sleep(1.6)
        paste_text(texto)
        return Result(speak="")

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

    # --- limpar as anotações ---
    if re.search(r"\b(apaga|limpa|zera)\w*\s+(as\s+)?(minhas\s+)?(notas|anotacoes)\b", t):
        try:
            (HERE / "NOTAS.md").write_text("", encoding="utf-8")
        except OSError:
            pass
        return Result(speak="Anotações apagadas, senhor.")
    # --- ler as anotações ---
    if re.search(r"\b(minhas (notas|anotacoes)|quais.*(notas|anotacoes)|le\w*\s+(as\s+)?(minhas\s+)?"
                 r"(notas|anotacoes)|o que eu anotei|lista de (notas|anotacoes))\b", t):
        p = HERE / "NOTAS.md"
        try:
            itens = [re.sub(r"^-\s*(\[[^\]]*\]\s*)?", "", ln).strip()
                     for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip().startswith("-")]
        except OSError:
            itens = []
        if not itens:
            return Result(speak="O senhor não tem anotações no momento.")
        return Result(speak=f"{len(itens)} anotaç" + ("ões" if len(itens) > 1 else "ão")
                      + ", senhor: " + "; ".join(itens[-6:]) + ".")

    # --- anotar ---
    m = re.search(r"^(?:anota\w*|salva\w*|apont\w*|toma\s+nota)"
                  r"(?:\s+(?:isso|o\s+seguinte|que|pra\s+mim|ai))?[:,\s]+(.+)",
                  raw.strip(), flags=re.IGNORECASE)
    if m and re.match(r"^(anota|salva|apont|toma)", t):
        _append("NOTAS.md", m.group(1).strip())
        return Result(speak="Anotado, senhor.")

    # --- pedido de melhoria pro próprio Jarvis (fila para o desenvolvedor/Claude) ---
    m = re.search(r"^(?:pedido|melhoria|ideia|anota\s+pra\s+voce|pro\s+desenvolvedor|modo\s+dev\w*)"
                  r"[:,\s]+(.+)", t)
    if m:
        _append("PEDIDOS.md", m.group(1).strip())
        return Result(speak="Registrei o pedido, senhor. Passo ao desenvolvedor.")

    # --- ver / processar a fila de pedidos ---
    if re.search(r"\b(meus pedidos|quais.*pedidos|le\w*\s+os pedidos|lista de pedidos|"
                 r"processa\w*\s+(os\s+)?(meus\s+)?pedidos|fila de pedidos)\b", t):
        p = HERE / "PEDIDOS.md"
        try:
            linhas = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip().startswith("-")]
        except OSError:
            linhas = []
        if not linhas:
            return Result(speak="A fila de pedidos está vazia, senhor.")
        if re.search(r"\bprocessa\w*", t):
            try:
                os.startfile(str(p))  # noqa: S606
            except Exception:  # noqa: BLE001
                pass
            return Result(speak=f"{len(linhas)} pedido" + ("s" if len(linhas) > 1 else "")
                          + " na fila, senhor. Abri o arquivo pro desenvolvedor.")
        resumo = "; ".join(re.sub(r"^-\s*(\[[^\]]*\]\s*)?", "", ln).strip() for ln in linhas[:4])
        return Result(speak=f"Senhor, {len(linhas)} na fila: {resumo}.")

    # --- modo estudo / flashcards por voz ---
    m = re.search(r"\b(?:me (?:faz|faca|manda|de)\s+(?:uma\s+)?(?:pergunta|questao)|me pergunta|"
                  r"modo estudo|modo quiz|me testa|toma minha licao|"
                  r"quiz|flashcard\w*)\b(?:\s+(?:sobre|de|em|a respeito de)\s+(.+))?", t)
    if m and brain is not None and hasattr(brain, "_post"):
        tema = (m.group(1) or "").strip() or "conhecimentos gerais"
        return _quiz_round(brain, tema, 1)

    # --- fato rápido da Wikipédia ("quem foi X", "o que é Y") ---
    if re.match(r"^(quem (foi|e|era|s[aã]o)|o que (e|era|foi|significa)|"
                r"me (fala|conta|explica) (sobre|o que|quem)|defini\w+ de|significado de)\b",
                norm(raw)):
        fato = wiki.lookup(raw)      # rápido; o "pensando/buscando" fica com o roteador/LLM
        if fato:
            return Result(speak=fato)

    # --- nada bateu: o LLM tenta traduzir o pedido num COMANDO ---
    _is_question = re.search(r"\b(por ?que|porque|qual|quais|quem|quanto\s+(custa|vale)|"
                             r"o\s+que\s+(e|significa|quer dizer)|me\s+(explica|conta|fala\s+sobre)|"
                             r"voce\s+(sabe|acha|pode\s+me\s+dizer))\b|\?", t)
    # roteador só pra fala que PARECE dirigida: >= 2 palavras e algum conteúdo.
    # 1 palavra solta que não bateu em nenhuma skill é quase sempre ruído — e o
    # roteador (2b) mapeava isso pra google/musica/abrir (foi o "gato" do incidente).
    _routable = len(t.split()) >= 2 and len(t) >= 6
    if _depth == 0 and _routable and brain is not None \
            and hasattr(brain, "route") and not _is_question:
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
