#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
jarvis_setup.py — instalador do Jarvis, estilo "instalar um jogo".

Roda numa janela só, passo a passo. O usuário não precisa de terminal.
Fica ao lado de uma pasta  payload/  com tudo que vai ser instalado:

    JarvisSetup.exe
    payload/
        python/            (runtime portátil)
        voice/             (código + config.toml modelo + profiles/)
        app/JarvisApp.exe
        models/faster-whisper-tiny/ , faster-whisper-small/
        ollama/OllamaSetup.exe
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

import setup_lib as L

# ---- paleta Jarvis -------------------------------------------------------
BG      = "#0a0e17"
PANEL   = "#0f1622"
LINE    = "#1c2a3a"
INK     = "#dce8f2"
DIM     = "#63788c"
CYAN    = "#37e1ff"
AMBER   = "#ffb454"
OK      = "#54e08a"
BAD     = "#ff5d6c"

APP_W, APP_H = 860, 620

PKG = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
PAYLOAD = PKG / "payload"


def payload_dir(name: str) -> Path:
    for base in (PAYLOAD, PKG):
        p = base / name
        if p.exists():
            return p
    return PAYLOAD / name


def read_model_name() -> str:
    cfg = payload_dir("voice") / "config.toml"
    try:
        import re
        m = re.search(r'^\s*model\s*=\s*"([^"]+)"', cfg.read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else "qwen3.5:2b"
    except Exception:  # noqa: BLE001
        return "qwen3.5:2b"


# ========================================================================
class Wizard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Instalação do Jarvis")
        self.configure(bg=BG)
        self.resizable(False, False)
        x = (self.winfo_screenwidth() - APP_W) // 2
        y = (self.winfo_screenheight() - APP_H) // 3
        self.geometry(f"{APP_W}x{APP_H}+{x}+{max(y, 0)}")

        self.f_h1 = tkfont.Font(family="Segoe UI Semibold", size=20)
        self.f_h2 = tkfont.Font(family="Segoe UI", size=11)
        self.f_body = tkfont.Font(family="Segoe UI", size=10)
        self.f_mono = tkfont.Font(family="Consolas", size=9)

        # estado partilhado entre passos
        self.state = {
            "dest_root": None,       # Path do disco escolhido (ex: F:\)
            "install_dir": None,     # <disco>\Jarvis
            "model": read_model_name(),
            "profile": "",           # perfil padrão escolhido
            "mic": None,
            "camera": None,
            "voice": None,
            "installed": False,
        }
        self.q: queue.Queue = queue.Queue()

        self._build_chrome()
        self.steps: list[Step] = [
            WelcomeStep(self), TermsStep(self), ProfileStep(self), DriveStep(self),
            InstallStep(self), OllamaStep(self), MicStep(self), CameraStep(self),
            VoiceStep(self), DoneStep(self),
        ]
        self.idx = 0
        self._show(0)
        self.after(120, self._pump)

    # ---- moldura fixa (cabeçalho + rodapé) ------------------------------
    def _build_chrome(self) -> None:
        head = tk.Frame(self, bg=BG, height=96)
        head.pack(fill="x")
        head.pack_propagate(False)
        cv = tk.Canvas(head, width=64, height=64, bg=BG, highlightthickness=0)
        cv.place(x=24, y=16)
        cv.create_oval(6, 6, 58, 58, outline=CYAN, width=2)
        cv.create_oval(16, 16, 48, 48, outline=AMBER, width=2)
        cv.create_oval(27, 27, 37, 37, fill=CYAN, outline="")
        tk.Label(head, text="J A R V I S", font=self.f_h1, fg=INK, bg=BG).place(x=104, y=22)
        tk.Label(head, text="assistente pessoal — instalação", font=self.f_body,
                 fg=DIM, bg=BG).place(x=106, y=56)
        tk.Frame(self, bg=LINE, height=1).pack(fill="x")

        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True)

        tk.Frame(self, bg=LINE, height=1).pack(fill="x")
        foot = tk.Frame(self, bg=BG, height=64)
        foot.pack(fill="x")
        foot.pack_propagate(False)
        self.dots = tk.Label(foot, text="", font=self.f_body, fg=DIM, bg=BG)
        self.dots.place(x=24, y=22)
        self.btn_next = _Btn(foot, "Avançar", self._next, primary=True)
        self.btn_next.place(relx=1.0, x=-24, y=14, anchor="ne")
        self.btn_back = _Btn(foot, "Voltar", self._back)
        self.btn_back.place(relx=1.0, x=-168, y=14, anchor="ne")

    # ---- navegação ----------------------------------------------------
    def _show(self, i: int) -> None:
        for s in self.steps:
            s.pack_forget()
        st = self.steps[i]
        st.pack(fill="both", expand=True, padx=40, pady=28)
        self.idx = i
        self.dots.config(text=f"passo {i + 1} de {len(self.steps)}   "
                              + "•" * (i + 1) + "·" * (len(self.steps) - i - 1))
        self.btn_back.set_enabled(i > 0 and st.allow_back)
        self.btn_next.config_text(st.next_label)
        self.btn_next.set_enabled(st.can_advance())
        st.enter()

    def _next(self) -> None:
        st = self.steps[self.idx]
        if not st.can_advance():
            return
        if not st.on_next():          # retorna False = fica no passo (ele cuida sozinho)
            return
        if self.idx < len(self.steps) - 1:
            self._show(self.idx + 1)

    def _back(self) -> None:
        if self.idx > 0:
            self._show(self.idx - 1)

    def refresh_nav(self) -> None:
        st = self.steps[self.idx]
        self.btn_next.set_enabled(st.can_advance())
        self.btn_next.config_text(st.next_label)
        self.btn_back.set_enabled(self.idx > 0 and st.allow_back)

    # ---- fila de eventos das threads --------------------------------
    def _pump(self) -> None:
        try:
            while True:
                fn = self.q.get_nowait()
                fn()
        except queue.Empty:
            pass
        self.after(120, self._pump)

    def post(self, fn) -> None:
        self.q.put(fn)


# ---- botão estilizado --------------------------------------------------
class _Btn(tk.Label):
    def __init__(self, parent, text, cmd, primary: bool = False):
        self._cmd = cmd
        self._primary = primary
        self._on = True
        super().__init__(parent, text=text, font=tkfont.Font(family="Segoe UI", size=10),
                         padx=22, pady=9, cursor="hand2")
        self._paint()
        self.bind("<Button-1>", lambda e: self._on and self._cmd())
        self.bind("<Enter>", lambda e: self._paint(hover=True))
        self.bind("<Leave>", lambda e: self._paint())

    def _paint(self, hover: bool = False) -> None:
        if not self._on:
            self.config(bg=PANEL, fg=DIM)
            return
        if self._primary:
            self.config(bg=CYAN if not hover else "#8af0ff", fg="#04121a")
        else:
            self.config(bg=PANEL, fg=INK if hover else DIM)

    def set_enabled(self, on: bool) -> None:
        self._on = bool(on)
        self.config(cursor="hand2" if on else "arrow")
        self._paint()

    def config_text(self, t: str) -> None:
        self.config(text=t)


# ========================================================================
class Step(tk.Frame):
    next_label = "Avançar"
    allow_back = True

    def __init__(self, wiz: "Wizard"):
        super().__init__(wiz.body, bg=BG)
        self.wiz = wiz
        self.build()

    # subclasses sobrescrevem:
    def build(self) -> None: ...
    def enter(self) -> None: ...
    def can_advance(self) -> bool: return True
    def on_next(self) -> bool: return True

    # helpers de layout
    def title(self, text: str) -> None:
        tk.Label(self, text=text, font=self.wiz.f_h1, fg=INK, bg=BG,
                 anchor="w").pack(fill="x", pady=(0, 6))

    def para(self, text: str, fg: str = INK) -> tk.Label:
        lb = tk.Label(self, text=text, font=self.wiz.f_h2, fg=fg, bg=BG,
                      justify="left", anchor="w", wraplength=APP_W - 96)
        lb.pack(fill="x", pady=3)
        return lb


# ---- 1. boas-vindas --------------------------------------------------
class WelcomeStep(Step):
    next_label = "Começar"
    allow_back = False

    def build(self) -> None:
        self.title("Vamos instalar o Jarvis, senhor.")
        self.para("\nO Jarvis é um assistente pessoal que ouve a sua voz e responde. "
                  "Ele roda no seu computador — não precisa de internet pra conversar.")
        self.para("\nEsta instalação faz tudo pra você, passo a passo:")
        for t in ("escolher onde instalar",
                  "copiar os arquivos do Jarvis",
                  "instalar o \"cérebro\" (Ollama) e baixar o modelo",
                  "configurar o microfone, a câmera e a voz",
                  "deixar o Jarvis pronto pra abrir sozinho quando ligar o PC"):
            self.para(f"     ·  {t}", fg=DIM)
        self.para("\nÉ só ir clicando em \"Avançar\". Leva alguns minutos.", fg=AMBER)


# ---- 2. termos / permissões ----------------------------------------
class TermsStep(Step):
    def build(self) -> None:
        self.title("O que o Jarvis vai usar")
        self.para("\nPara funcionar, o Jarvis precisa da sua permissão para:")
        for t in ("ouvir o microfone (só age quando você diz \"Jarvis\")",
                  "usar a câmera quando você pedir (\"Jarvis, ativar câmera\")",
                  "usar os alto-falantes para falar com você",
                  "abrir junto com o Windows"):
            self.para(f"     ·  {t}", fg=DIM)
        self.para("\nNada é enviado pela internet. Tudo fica no seu computador.", fg=OK)
        self.var = tk.BooleanVar(value=False)
        c = tk.Checkbutton(self, text="  Eu concordo e quero continuar", variable=self.var,
                           font=self.wiz.f_h2, fg=INK, bg=BG, selectcolor=PANEL,
                           activebackground=BG, activeforeground=INK,
                           command=self.wiz.refresh_nav)
        c.pack(anchor="w", pady=18)

    def can_advance(self) -> bool:
        return bool(getattr(self, "var", None) and self.var.get())


# ---- 3. perfil (quem vai usar) ------------------------------------
class ProfileStep(Step):
    def build(self) -> None:
        self.title("Quem vai usar o Jarvis")
        self.para("O perfil define como o Jarvis chama e trata você. Todas as funções "
                  "ficam iguais — dá pra trocar depois falando \"Jarvis, muda de perfil\".\n",
                  fg=DIM)
        self.var = tk.StringVar(value="")
        self.holder = tk.Frame(self, bg=BG)
        self.holder.pack(fill="x", pady=4)

    def enter(self) -> None:
        for w in self.holder.winfo_children():
            w.destroy()
        profs = L.list_profiles(payload_dir("voice"))
        if not profs:
            self.para("(nenhum perfil encontrado — vai usar a configuração padrão)", fg=AMBER)
            self.wiz.state["profile"] = ""
            self.wiz.refresh_nav()
            return
        for p in profs:
            tk.Radiobutton(self.holder, text=f"   {p['label']}", value=p["name"],
                           variable=self.var, font=self.wiz.f_h2, fg=INK, bg=BG,
                           selectcolor=PANEL, activebackground=BG, activeforeground=CYAN,
                           wraplength=APP_W - 130, justify="left",
                           command=self._pick).pack(anchor="w", pady=5)
        pref = next((p["name"] for p in profs if p["name"] == "robson"), profs[0]["name"])
        self.var.set(pref)
        self._pick()

    def _pick(self) -> None:
        self.wiz.state["profile"] = self.var.get()
        self.wiz.refresh_nav()

    def can_advance(self) -> bool:
        return True     # sem perfil = configuração padrão, tudo bem


# ---- 4. disco -------------------------------------------------------
class DriveStep(Step):
    def build(self) -> None:
        self.title("Onde instalar")
        self.para("Escolha o disco. O Jarvis ocupa cerca de 5 GB.\n", fg=DIM)
        self.var = tk.StringVar(value="")
        self.holder = tk.Frame(self, bg=BG)
        self.holder.pack(fill="x", pady=4)
        self.note = tk.Label(self, text="", font=self.wiz.f_body, fg=AMBER, bg=BG)
        self.note.pack(anchor="w", pady=10)

    def enter(self) -> None:
        for w in self.holder.winfo_children():
            w.destroy()
        drives = L.list_drives()
        rec = L.recommended_drive(drives)
        for d in drives:
            enough = d["free_gb"] >= 6
            txt = (f"   {d['letter']}:\\   {d['label']:<18}   "
                   f"{d['free_gb']:.0f} GB livres de {d['total_gb']:.0f} GB"
                   + ("   (recomendado)" if rec and d["letter"] == rec["letter"] else ""))
            rb = tk.Radiobutton(self.holder, text=txt, value=d["root"], variable=self.var,
                                font=self.wiz.f_mono, fg=INK if enough else DIM, bg=BG,
                                selectcolor=PANEL, activebackground=BG, activeforeground=CYAN,
                                state="normal" if enough else "disabled",
                                command=self._pick)
            rb.pack(anchor="w", pady=2)
        if rec:
            self.var.set(rec["root"])
        self._pick()

    def _pick(self) -> None:
        root = self.var.get()
        if root:
            self.wiz.state["dest_root"] = Path(root)
            self.wiz.state["install_dir"] = Path(root) / "Jarvis"
            self.note.config(text=f"Vai instalar em:  {root}Jarvis")
        self.wiz.refresh_nav()

    def can_advance(self) -> bool:
        return bool(self.var.get())


# ---- 4. instalação (cópia) -----------------------------------------
class InstallStep(Step):
    next_label = "Avançar"
    allow_back = False

    def build(self) -> None:
        self.title("Instalando o Jarvis")
        self.para("")
        self.pb = ttk.Progressbar(self, length=APP_W - 100, mode="determinate", maximum=1.0)
        self.pb.pack(pady=8, anchor="w")
        self.msg = tk.Label(self, text="preparando…", font=self.wiz.f_mono, fg=DIM, bg=BG,
                            anchor="w")
        self.msg.pack(fill="x")
        self.done = False

    def enter(self) -> None:
        if self.done or self.wiz.state["installed"]:
            return
        self.wiz.btn_next.set_enabled(False)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        st = self.wiz.state
        dest: Path = st["install_dir"]
        try:
            parts = ("voice", "jarvis-app", "models")
            present = [n for n in parts if payload_dir(n).exists()]
            if "voice" not in present:
                self._set("ERRO: não encontrei a pasta 'payload' ao lado do instalador.", None)
                self.wiz.post(lambda: self.msg.config(fg=BAD))
                return
            dest.mkdir(parents=True, exist_ok=True)
            for name in parts:
                src = payload_dir(name)
                if not src.exists():
                    continue
                self._set(f"copiando {name}…", None)
                L.copy_payload(src, dest / name,
                               on_progress=lambda p, f, n=name: self._set(f"{n}: {f}", p))
            # config.toml
            self._set("ajustando a configuração…", 0.98)
            cfgp = dest / "voice" / "config.toml"
            if cfgp.exists():
                txt = cfgp.read_text(encoding="utf-8")
                txt = L.set_whisper_paths(txt, dest / "models")
                patch = {"exe_path": str(dest / "jarvis-app" / "JarvisApp.exe")}
                if st.get("profile"):
                    patch["active"] = st["profile"]
                txt = L.patch_config(txt, patch)
                cfgp.write_text(txt, encoding="utf-8")
            # launcher + atalhos
            self._set("criando atalhos…", 0.99)
            vbs = L.write_launcher(dest)
            L.make_shortcut(L.start_menu_dir() / "Jarvis.lnk", str(vbs), workdir=str(dest))
            L.make_shortcut(L.startup_dir() / "Jarvis.lnk", str(vbs), workdir=str(dest))
            L.make_shortcut(Path(os.path.expandvars(r"%USERPROFILE%\Desktop")) / "Jarvis.lnk",
                            str(vbs), workdir=str(dest))
            st["installed"] = True
            self._set("pronto.", 1.0)
            self.wiz.post(lambda: (self.wiz.btn_next.set_enabled(True),
                                   self.wiz._next()))
        except Exception as exc:  # noqa: BLE001
            self._set(f"ERRO: {exc}", None)
            self.wiz.post(lambda: self.msg.config(fg=BAD))

    def _set(self, text: str, prog: float | None) -> None:
        def go() -> None:
            self.msg.config(text=text)
            if prog is not None:
                self.pb["value"] = prog
        self.wiz.post(go)

    def can_advance(self) -> bool:
        return self.wiz.state["installed"]


# ---- 5. Ollama -----------------------------------------------------
class OllamaStep(Step):
    def build(self) -> None:
        self.title("O cérebro do Jarvis (Ollama)")
        self.para("O Ollama é o programa que deixa o Jarvis pensar. "
                  "Vamos instalar e baixar o modelo de linguagem.\n", fg=DIM)
        self.status = tk.Label(self, text="verificando…", font=self.wiz.f_h2, fg=AMBER, bg=BG,
                               anchor="w")
        self.status.pack(fill="x", pady=4)
        row = tk.Frame(self, bg=BG)
        row.pack(anchor="w", pady=6)
        self.b_install = _Btn(row, "Instalar o Ollama", self._install)
        self.b_install.pack(side="left")
        self.b_check = _Btn(row, "Já instalei / verificar", self._check)
        self.b_check.pack(side="left", padx=10)
        self.tip = tk.Label(self, text="", font=self.wiz.f_body, fg=DIM, bg=BG,
                            justify="left", anchor="w", wraplength=APP_W - 96)
        self.tip.pack(fill="x", pady=6)
        self.pb = ttk.Progressbar(self, length=APP_W - 100, mode="determinate")
        self.log = tk.Label(self, text="", font=self.wiz.f_mono, fg=DIM, bg=BG, anchor="w")
        self.ready = False

    def enter(self) -> None:
        self._check()

    def _check(self) -> None:
        model = self.wiz.state["model"]
        has_ollama = bool(L.find_ollama())
        if not has_ollama:
            self.status.config(text="Ollama ainda não está instalado.", fg=AMBER)
            self.tip.config(text="Clique em \"Instalar o Ollama\". Vai abrir uma janela azul "
                                 "do Ollama — clique em Install e espere terminar. Depois volte "
                                 "aqui e clique em \"Já instalei / verificar\".")
            self.b_install.config_text("Instalar o Ollama")
            self.b_install._cmd = self._install
            self.b_install.set_enabled(True)
            self.ready = False
        elif not L.has_model(model):
            self.status.config(text=f"Ollama instalado. Falta baixar o modelo ({model}).", fg=AMBER)
            self.tip.config(text="Clique em \"Baixar o modelo\" abaixo. É um download grande "
                                 "(cerca de 2 GB), pode levar alguns minutos.")
            self.b_install.config_text("Baixar o modelo")
            self.b_install._cmd = self._pull
            self.b_install.set_enabled(True)
            self.ready = False
        else:
            self.status.config(text="Tudo certo — Ollama e modelo prontos.", fg=OK)
            self.tip.config(text="")
            self.b_install.set_enabled(False)
            self.ready = True
        self.wiz.refresh_nav()

    def _install(self) -> None:
        inst = payload_dir("ollama") / "OllamaSetup.exe"
        if inst.exists():
            L.run_ollama_installer(str(inst))
            self.tip.config(text="Abri o instalador do Ollama. Na janela que apareceu, clique "
                                 "em INSTALL e espere a barra encher. Quando fechar sozinha, "
                                 "volte aqui e clique em \"Já instalei / verificar\".")
            return
        # sem instalador embutido: baixa direto do site
        import webbrowser
        webbrowser.open("https://ollama.com/download/OllamaSetup.exe")
        self.tip.config(text="Começou a baixar o \"OllamaSetup.exe\" (fica na pasta Downloads / "
                             "ou aparece embaixo no navegador). Quando terminar, clique nele, "
                             "depois em INSTALL. Terminou? Clique em \"Já instalei / verificar\".")

    def _pull(self) -> None:
        self.b_install.set_enabled(False)
        self.b_check.set_enabled(False)
        self.pb.pack(pady=6, anchor="w")
        self.log.pack(fill="x")
        L.start_ollama_serve()
        threading.Thread(target=self._pull_thread, daemon=True).start()

    def _pull_thread(self) -> None:
        import re
        model = self.wiz.state["model"]

        def on_line(ln: str) -> None:
            pct = re.search(r"(\d+)%", ln)
            def go() -> None:
                self.log.config(text=ln[-90:])
                if pct:
                    self.pb["value"] = int(pct.group(1))
            self.wiz.post(go)

        ok = L.ollama_pull(model, on_line=on_line)
        def done() -> None:
            self.b_check.set_enabled(True)
            self._check()
        self.wiz.post(done)

    def can_advance(self) -> bool:
        return self.ready


# ---- 6. microfone -------------------------------------------------
class MicStep(Step):
    def build(self) -> None:
        self.title("Microfone")
        self.para("Escolha o microfone que você usa. Fale perto dele e clique em Testar.\n", fg=DIM)
        self.cb = ttk.Combobox(self, state="readonly", width=54, font=self.wiz.f_body)
        self.cb.pack(anchor="w", pady=4)
        self.cb.bind("<<ComboboxSelected>>", lambda e: self._pick())
        row = tk.Frame(self, bg=BG)
        row.pack(anchor="w", pady=10)
        _Btn(row, "Testar (fale por 2 s)", self._test).pack(side="left")
        self.bar = ttk.Progressbar(row, length=260, mode="determinate", maximum=1.0)
        self.bar.pack(side="left", padx=14)
        self.res = tk.Label(self, text="", font=self.wiz.f_body, fg=DIM, bg=BG)
        self.res.pack(anchor="w")
        self._mics: list[dict] = []

    def enter(self) -> None:
        self._mics = L.list_mics()
        names = [m["name"] for m in self._mics]
        self.cb["values"] = names
        pref = next((n for n in names if "brio" in n.lower()), names[0] if names else "")
        if pref:
            self.cb.set(pref)
            self._pick()

    def _pick(self) -> None:
        self.wiz.state["mic"] = self.cb.get()
        self.wiz.refresh_nav()

    def _test(self) -> None:
        self.res.config(text="ouvindo…", fg=AMBER)
        idx = next((m["index"] for m in self._mics if m["name"] == self.cb.get()), None)
        threading.Thread(target=lambda: self._test_thread(idx), daemon=True).start()

    def _test_thread(self, idx) -> None:
        peak = L.mic_peak(idx if isinstance(idx, int) and idx >= 0 else None, 2.0)
        def go() -> None:
            if peak < 0:
                self.res.config(text="não consegui testar — mas pode seguir.", fg=DIM)
                return
            self.bar["value"] = min(peak * 3, 1.0)
            if peak > 0.02:
                self.res.config(text="perfeito, ouvi você.", fg=OK)
            else:
                self.res.config(text="quase não ouvi — chegue mais perto ou escolha outro.", fg=AMBER)
        self.wiz.post(go)

    def can_advance(self) -> bool:
        return bool(self.cb.get())

    def on_next(self) -> bool:
        _patch_cfg(self.wiz, {"input_device_match": _short(self.cb.get())})
        return True


# ---- 7. câmera ---------------------------------------------------
class CameraStep(Step):
    def build(self) -> None:
        self.title("Câmera")
        self.para("Escolha a webcam. O Jarvis só liga a câmera quando você pede "
                  "(\"Jarvis, ativar câmera\").\n", fg=DIM)
        self.cb = ttk.Combobox(self, state="readonly", width=54, font=self.wiz.f_body)
        self.cb.pack(anchor="w", pady=4)
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.wiz.refresh_nav())
        self.para("")
        self.skip = tk.Label(self, text="Sem webcam? Pode avançar — dá pra configurar depois.",
                             font=self.wiz.f_body, fg=DIM, bg=BG)
        self.skip.pack(anchor="w", pady=8)

    def enter(self) -> None:
        cams = L.list_cameras()
        self.cb["values"] = cams or ["(nenhuma câmera encontrada)"]
        if cams:
            pref = next((c for c in cams if "brio" in c.lower()), cams[0])
            self.cb.set(pref)
        else:
            self.cb.set("(nenhuma câmera encontrada)")
        self.wiz.refresh_nav()

    def can_advance(self) -> bool:
        return True

    def on_next(self) -> bool:
        val = self.cb.get()
        if val and "nenhuma" not in val:
            _patch_cfg(self.wiz, {"camera_match": _short(val)})
        return True


# ---- 8. voz ----------------------------------------------------
class VoiceStep(Step):
    def build(self) -> None:
        self.title("A voz do Jarvis")
        self.para("Escolha a voz. As vozes em português vêm primeiro.\n", fg=DIM)
        self.cb = ttk.Combobox(self, state="readonly", width=54, font=self.wiz.f_body)
        self.cb.pack(anchor="w", pady=4)
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.wiz.refresh_nav())
        _Btn(self, "Ouvir amostra", self._sample).pack(anchor="w", pady=12)
        self.hint = tk.Label(self, text="", font=self.wiz.f_body, fg=DIM, bg=BG)
        self.hint.pack(anchor="w")
        self._voices: list[dict] = []

    def enter(self) -> None:
        self._voices = L.list_voices()
        names = [v["name"] for v in self._voices]
        self.cb["values"] = names
        if names:
            self.cb.set(names[0])
        if not any(v["pt"] for v in self._voices):
            self.hint.config(text="Nenhuma voz em português encontrada. Dá pra instalar depois "
                                  "em Configurações do Windows › Hora e idioma › Voz.")
        self.wiz.refresh_nav()

    def _sample(self) -> None:
        v = self.cb.get()
        if v:
            self.hint.config(text="tocando amostra…")
            threading.Thread(target=lambda: L.speak_sample(v), daemon=True).start()

    def can_advance(self) -> bool:
        return bool(self.cb.get())

    def on_next(self) -> bool:
        _patch_cfg(self.wiz, {"sapi_voice": self.cb.get()})
        return True


# ---- 9. fim --------------------------------------------------
class DoneStep(Step):
    next_label = "Concluir"
    allow_back = False

    def build(self) -> None:
        self.title("Tudo pronto, senhor.")
        self.para("\nO Jarvis está instalado e vai abrir sozinho quando você ligar o computador.\n")
        card = tk.Frame(self, bg=PANEL)
        card.pack(fill="x", pady=8)
        for t in ('Diga  "Jarvis"  →  ele responde e espera seu pedido',
                  'Diga  "Jarvis, que horas são"  →  ele responde',
                  'Diga  "Jarvis, abre o navegador"  →  ele abre',
                  'Diga  "Jarvis, modo cinema"  →  ele para de ouvir',
                  'Aperte  Ctrl + Alt + J  →  ele volta a ouvir',
                  'Diga  "Jarvis, muda de perfil"  →  troca de usuário',
                  'Pergunte  "Jarvis, o que você sabe fazer?"  →  ele te explica'):
            tk.Label(card, text="   " + t, font=self.wiz.f_h2, fg=INK, bg=PANEL,
                     anchor="w", justify="left").pack(fill="x", pady=5, padx=8)
        self.launch = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="  Abrir o Jarvis agora", variable=self.launch,
                       font=self.wiz.f_h2, fg=INK, bg=BG, selectcolor=PANEL,
                       activebackground=BG, activeforeground=INK).pack(anchor="w", pady=14)

    def on_next(self) -> bool:
        if self.launch.get():
            vbs = self.wiz.state["install_dir"] / "iniciar_jarvis.vbs"
            try:
                os.startfile(str(vbs))  # noqa: S606
            except Exception:  # noqa: BLE001
                pass
        self.wiz.after(300, self.wiz.destroy)
        return True


# ---- utils compartilhados --------------------------------------
def _short(name: str) -> str:
    """'Microfone (Brio 100)' -> 'Brio 100' ; 'Brio 100' -> 'Brio 100'."""
    import re
    m = re.search(r"\(([^)]+)\)", name)
    base = m.group(1) if m else name
    return re.sub(r"\b(microfone|microphone|camera|webcam)\b", "", base, flags=re.I).strip() or name


def _patch_cfg(wiz: "Wizard", changes: dict) -> None:
    cfgp = wiz.state["install_dir"] / "voice" / "config.toml"
    try:
        txt = cfgp.read_text(encoding="utf-8")
        cfgp.write_text(L.patch_config(txt, changes), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def main() -> None:
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass
    Wizard().mainloop()


if __name__ == "__main__":
    main()
