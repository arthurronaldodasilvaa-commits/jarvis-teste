# Registro do trabalho autônomo — 2026-09-09

---

## ⚠️ INCIDENTE (10/09 ~00:33) — Jarvis em loop de comandos

**O que aconteceu:** Arthur estava ao telefone. O Whisper transcreveu trechos
da conversa/ruído como se fossem comandos ("jarvis me lembra de tirar o bolo
em 20 minutos", buscas no Google por "gato", tocar música no Spotify) e o
daemon executou **em sequência, sem parar**. Em 2,5 min foram criados **41
lembretes** idênticos. Arthur teve que **forçar o desligamento do PC**.

**Causa raiz:** o gate da wake-word era frouxo (similaridade ≥ 0,6 com
"jarvis" — ruído de TV/telefone passava) e **não havia nenhuma trava contra
repetição**: cada transcrição virava um comando, sem dedup nem limite de taxa.
(Os "2 processos pythonw" no Gerenciador são normais: a venv do `uv` usa um
trampolim + o interpretador real. Era 1 daemon só.)

**Correções (commit `fix(seguranca)`):**
- `_guard_command()` no `jarvis_voice.py`: 3 comandos quase iguais
  (similaridade ≥ 0,75) OU 5 comandos em 20 s → **PAUSA a escuta** + aviso
  falado + nota no HUD (volta com Ctrl+Alt+J). Comando idêntico repetido em
  < 12 s é ignorado. Config em `[safety]` (dá pra desligar com `enabled=false`).
- `strip_wake_word()`: gate mais rígido (0,6 → 0,72; ≥ 4 letras; prefixo
  "jarvi"). Ruído para de virar comando.
- `reminders.add()`: dedup de 90 s por texto.
- `ensure_single_instance()`: handle do mutex não é mais coletado pelo GC.
- `common.sweep_tmp()` no arranque limpa `.tmp` órfão de escrita atômica.
- `reminders.json` limpo (41 → 0).

Testado (`python voice/test_audio.py safety`): replay do incidente é cortado
no 3º comando; uso legítimo rápido (2–4 comandos distintos) passa normal.
**Deploy:** daemon reiniciado 01:13 com o conjunto completo (guard + gate +
mutex + escrita atômica + dedup de lembrete/tarefa + roteador só p/ fala
dirigida + tema de cor). Boot limpo, quieto, `reminders.json`/`tasks.json`
limpos. `AUTONOMOUS_LOG` + `COMANDOS.md` + `docs/` atualizados.

Pendência anotada (não é do incidente): `app.py _patch_toml_line` casa a
chave pelo nome sem a seção — `enabled` existe em `[arrival]`, `[app]` e
`[safety]`. Hoje funciona por sorte (ordem no arquivo). Ver Onda I.

---

## RODADA 4 (09/09, noite) — ROADMAP_2.md

Arthur saiu de novo. Pediu: aplicar TUDO do `ROADMAP_2.md` (ondas A–I) +
pendências do `ROADMAP.md`, autonomamente, commit por passo, sem teste
destrutivo, e ao acabar: revisar/otimizar/polir código + design + mais ideias.
Parar só quando ele mandar. Permissão total, pode instalar qualquer coisa.

Progresso (atualizo aqui conforme fecho cada onda):
- [x] Onda A — hologramas interativos (sliders + voz) — commit 63
- [x] Onda B — Jarvis lê os materiais (RAG-lite, BM25, pypdf) — commit 67
- [x] Onda C — APIs sem chave (facts.py: B3, CEP, feriado, ar, sol/lua, história) — 64
- [x] Onda D — Windows (tarefas, top procs, pomodoro, apresentação, ler em voz, memo) — 65-66
- [x] Onda E — 7 modelos novos + modo aula — commits 69-70
- [x] Onda F — OCR (tesseract.js, ~15 MB) + anatomia procedural — 71-73
- [x] Onda G1 — temperatura GPU no HUD + voz (CPU temp bloqueada por permissão) — 68
- [~] Onda H — otimização / revisão / polimento (H1,H3-H8 feitos; H2 parcial)
- [ ] Onda I — ideias novas

Rodada 5 (10/09, madrugada) — commits ~74–95:
- **Fix de segurança do incidente** (ver topo) — trava anti-loop, gate,
  dedup, roteador conservador, mutex, escrita atômica, lembrete/tarefa
  dedup, `test_audio.py safety`.
- **Onda H**: H8 (COMANDOS.md regenerado), H6/H7 (escrita atômica + Whisper
  `small` lazy + `norm` cacheado + `sweep_tmp`), H3 (MediaPipe downshift
  quando ocioso), H5 (cérebro muda de cor por fase), H4 (tokens de cor no
  HUD + status colorido + feed com fade-out real).
- **Onda I**: temas de cor do holograma (`[app] theme`), diário de bordo
  ("o que eu fiz hoje"), `_patch_toml_line` por seção, data no log.
- **docs/**: DEPLOY.md, PERF.md.

Daemon reiniciado 3× nesta rodada, todos boot limpo. Estado final: rodando,
quieto, `reminders.json`/`tasks.json` limpos, tema cyan.

**10/09 ~16h — faxina da pasta OpenJarvis (14 GB → 8,4 GB, -5,6 GB)**
Apagado (só lixo regenerável, nada de fonte/venv/modelos/dados):
`installer/{packB, build, pacote, dist}`, `jarvis-app/build`, `*.log` de
build, todo `__pycache__`/`.pyc`, `uv-cache`, dirs vazios (`cargo rustup
skills`), `_tts_out.wav`. Removidos 3 atalhos `Jarvis.lnk` acidentais
(Área de Trabalho + Menu Iniciar + Inicializar) que o Arthur criou rodando
`INSTALAR.bat` de dentro de `installer/pacoteB/Jarvis/`; o autostart do dev
(`Jarvis Voz.lnk`) foi mantido. Pacote B resetado pro estado de envio.
Mantido: `pacoteB/` (não subiu ainda), `OllamaSetup.exe`, `packB_libs/` +
`packB_py/` (insumos pra reconstruir o Pacote B), `src/` (venv), caches de
modelo. Regerar o Pacote A: `build_voice.bat` + `..\jarvis-app\build.bat`
+ `build_setup.bat` + `build_package.bat`.
> Nota: 2 entradas suspeitas no Inicializar do Windows, fora do projeto —
> `Audio system.lnk` → `C:\Netframework.4.5.2\...` e `system.lnk` →
> `C:\Dumper\system.vbs`. Não são do Jarvis. Não mexi. Vale o Arthur olhar.

**10/09 15:00 — o pai não conseguiu instalar: Smart App Control**
O Windows 11 do Robson tem **Smart App Control** ligado — bloqueia TODO
`.exe` não assinado, sem opção de "permitir". Os `JarvisVoice.exe` /
`JarvisApp.exe` congelados (PyInstaller) batem nisso: instalava, mas nada
rodava, nada no Gerenciador de Tarefas.

**Solução — "Pacote B" (roda do código):**
- Python **embeddable oficial da python.org** (assinado pela PSF → o SAC
  aceita). `installer/packB_py/` (extraído) + `installer/packB_libs/`
  (`pip install --target` do `requirements-runtime.txt`).
- `INSTALAR.bat` (o usuário **desbloqueia o .zip** antes de extrair → sem
  marca-da-web → o `.bat` roda). Ajusta o config (modelos em caminho
  absoluto, perfil), cria `iniciar_jarvis.vbs` **localmente** e os atalhos,
  puxa o modelo do Ollama.
- `build_package_src.bat` → `installer/pacoteB/Jarvis/` (2,5 GB):
  `python\ libs\ voice\ jarvis-app\ models\ ollama\` + INSTALAR/DIAGNOSTICO/
  LEIA-ME/MANUAL/COMANDOS.
- `jarvis_voice._app_command()`: abre o app com `pythonw app.py` quando não
  há `.exe`.
- Testado ponta a ponta do pacote real: `INSTALAR.bat` → `iniciar_jarvis.vbs`
  → daemon + app sobem com o embeddable, modelos do caminho local, renderer
  ok. **Pronto pro Drive** (o "Pacote A" congelado fica pra quem não tem SAC).

**10/09 13:00–13:45 — pacote final pro pai (Robson):**
- `manual/jarvis-manual.html` — site único, offline, tema HUD holográfico:
  busca de comando, índice com scroll-spy, copiar comando, esfera em canvas
  que cicla as cores de fase, 5 temas de acento (= os do app), tamanho de
  texto, modo calmo, impressão, cartão de bolso. Abre por voz:
  "Jarvis, como você funciona" (`skills._find_manual`).
- Reconhecimento facial: "aprende meu rosto" agora **pergunta o nome** e
  anexa (`face.clean_name`, `await_reply`); confirma falando o nome.
- Correções de cor de fase (verde só em busca real; volta pro ciano ao
  responder) + o fix de rolagem do manual.
- Rebuild final: `JarvisVoice.exe` 13:36, `JarvisApp.exe` 13:34, manual,
  `installer/pacote/Jarvis/` (2,6 GB). Testado: daemon do pacote sobe limpo
  no perfil **robson**. `LEIA-ME.txt` e `MONTAR_PACOTE.md` atualizados.
  **Pronto pro Drive.**

**10/09 06:30 — Arthur voltou:** pediu pra reiniciar o Jarvis dele e regerar
o pacote pro pai.
- Reiniciei daemon (fonte) + JarvisApp (build novo). Achei um `JarvisVoice.exe`
  congelado de um teste antigo segurando o mutex — matei. Ambos rodando limpo.
- **`installer/pacote/Jarvis/` regenerado** (commit `build:`): os 3 `.exe`
  recompilados do código atual. Corrigi o `JarvisVoice.spec` (faltavam
  `diary`/`aula` nos hiddenimports — modo aula e diário não iam no congelado)
  e o `build_package.bat` (não copiava `study/` — modo estudo quebrava no
  congelado). Testado: `JarvisVoice.exe` congelado sobe com os 25 módulos,
  Piper, LLM; `JarvisApp.exe` renderer ok. Pacote = 2,6 GB (com Ollama).

Reconhecimento facial: já feito antes (rodada anterior). face-api.js local.

---

## RODADAS 1–3 (histórico abaixo)

Arthur saiu do escritório e pediu pra eu aplicar TODAS as ideias do
`ROADMAP.md`, sozinho, em loop, até ele voltar e mandar parar.

Ambiente: repo local `E:\OpenJarvis` (sem remote — **nada saiu da máquina**),
daemon de voz rodando o tempo todo, Ollama no ar. Trabalhei ~1h30.

Regras que eu me impus e cumpri:
- Só trabalho local. Nada de enviar/publicar/gastar/contatar ninguém.
- Não toquei no pacote que foi enviado pro pai (`installer/pacote/`) até o fim.
- Commit a cada feature testada. ~30 commits.
- O que precisa de conta externa / chave paga / hardware / asset que eu não
  tenho: **documentei, não fingi**.

---

## ROADMAP — status final

| Seção | Status |
|---|---|
| **A. Módulos de estudo holográficos** | ✅ (menos anatomia — precisa de assets glTF) |
| **B. Interação de mão** | ✅ completa |
| **C. Assistente mais capaz** | ✅ completa |
| **D. HUD no cérebro** | ✅ completa (menos temperatura CPU/GPU — precisa de libs admin) |
| **E. Câmera / visão** | ✅ parcial (gestos + QR + presença; falta OCR de texto e face-recognition) |
| **F. Plataforma / infra** | ✅ parcial (perfis, instalador, painel de config, Piper TTS, fila de pedidos; falta assinar o .exe e modelo LLM maior) |

### A — `ui/models.js` (11 modelos novos)
círculo trigonométrico animado · plotter de função ("plota x^2-4") ·
sólido + fórmula · diagrama de corpo livre · lançamento oblíquo (bola animada) ·
plano inclinado · moléculas H₂O/CH₄/benzeno (ball-and-stick) · tabela periódica ·
célula animal. `skills._clean_expr()` = fala → expressão matemática.

### B — `ui/holograms.js`
travar/soltar (fica verde) · duplicar ("copia isso") · explodir (afasta as peças) ·
rotação de uma mão só (✌️ pela inclinação da palma) · desenhar no ar (modo desenho + ☝️) ·
medir (modo medida + 2 pinças → distância).

### C — módulos novos em `voice/`
- **reminders.py** — lembretes/timers persistentes + **recorrentes** ("todo dia às 8")
- **weather.py** — Open-Meteo (sem chave)
- **calc.py** — porcentagem, aritmética, conversão (comprimento/massa/temp/**câmbio**/**cripto**)
- **news.py** — RSS do Google Notícias
- briefing na chegada · ditado direcionado ("escreve no bloco de notas: ...")

### D — `voice/hud.py` + `ui/hud.js`
relógio + data + clima · **próximos lembretes** · gauges CPU/RAM/GPU (psutil+pynvml) ·
música tocando com barra de progresso (winsdk) · feed de notificações ·
estados visuais (PENSANDO / PESQUISANDO / ERRO).

### E — `ui/vision.js` + `voice/media.py`
gestos de mídia fora do modo holograma · leitura de QR (BarcodeDetector nativo) ·
modo presença leve (`[camera] auto_return_seconds`).

### F
- **Sistema de perfis** (feito antes) — só persona, não trava funções
- **Instalador gráfico** (feito antes) — `installer/`, sem terminal
- **Painel de configurações** no app — ⚙ / "abre as configurações" — 17 campos,
  salva no config.toml e reinicia (`ui/settings.js`, `app.py`)
- **Piper TTS** — voz neural pt-BR `pt_BR-faber-medium` (muito melhor que a SAPI).
  `[tts] engine="piper"`, fallback automático. `voice/piper/` (~98 MB, gitignored)
- **Fila de pedidos** — "quais meus pedidos" / "processa meus pedidos"

---

## Ideias novas (além do roadmap) — aplicadas

- **Memória de conversa** — as últimas 3 trocas; "e a população dela?" funciona.
  "repete" / "esquece".
- **"Que música é essa?"** + "do começo" / "adianta 30 segundos" (`voice/media.py`)
- **Fatos da Wikipédia** (`voice/wiki.py`) — "quem foi X", "o que é Y"
- **Comandos de desktop** — print, área de transferência (ler/escrever), janelas
  (minimizar tudo, maximizar, jogar pra outra tela, dividir)
- **Cripto** — "quanto tá o bitcoin" (CoinGecko)
- **Contagem de dias** — "quantos dias faltam pro natal"
- **Velocidade da fala** — "fala mais devagar/rápido"
- **Pontuação ditada** — "vírgula", "ponto final", "nova linha" no "digita:"
- **Encadear 2 comandos** — "abre a steam e o spotify"
- **Diálogo aberto (`Result.await_reply`)** + **quiz de estudo por voz** —
  "me faz uma pergunta sobre a segunda guerra" → responde falando → o LLM corrige
- **Roteador LLM expandido** — traduz frases soltas pra TODOS os recursos novos

---

## O que ficou pendente (e por quê)

| Item | Motivo |
|---|---|
| Anatomia (esqueleto/órgãos) | precisa de modelos glTF que eu não tenho; procedural não fica bom |
| OCR de texto pela câmera | precisa bundlar tesseract.js + por.traineddata (~13 MB) — decisão de tamanho |
| Reconhecimento facial (você vs outros) | precisa face-api.js + modelos (~6 MB) + enrollment |
| Temperatura de CPU/GPU no HUD | precisa de lib com admin no Windows (LibreHardwareMonitor) |
| Assinar o `JarvisSetup.exe` | certificado de code-signing é pago e exige verificação de identidade |
| Modelo LLM maior (qwen 7b/14b) | só trocar `[assistant] model`, mas precisa de RAM/GPU que o PC não tem |

---

## ⚠️ Aviso

Durante um teste de regressão eu rodei "bloqueia a tela" de verdade — a
função executa `LockWorkStation()`. **Sua tela ficou bloqueada.** É só
destravar com a senha, nada foi perdido, o daemon continuou rodando o
tempo todo. Não vou mais rodar comandos destrutivos em lote (aprendi:
os testes de `skills.dispatch` executam efeitos reais — mídia, arquivos,
LockWorkStation). Desligar/reiniciar/suspender pedem "sim" falado, então
esses não dispararam.

## Pra você quando voltar

1. **Diga "Jarvis, para o ciclo"** (ou qualquer coisa) pra eu encerrar.
2. A **voz mudou** — agora é o Piper (neural). Se preferir a antiga:
   config → "Motor de voz" → sapi.
3. O **pacote do instalador** (`installer/pacote/Jarvis/`) foi **regenerado**
   com tudo isso + Piper. O que você mandou pro seu pai ANTES não tem nada
   disso — se quiser, sobe a pasta nova no Drive.
4. Tudo commitado no git local. `git log` conta a história. `ROADMAP.md` tem
   os checkboxes. Nada foi enviado pra lugar nenhum.
5. **`COMANDOS.md`** (novo, na raiz) lista TUDO que dá pra pedir agora — é
   uma boa pra você revisar e depois mostrar pro seu pai.

## Estado final (16h45)

- ~32 commits. Daemon rodando (perfil arthur, voz Piper).
- Frozen `JarvisVoice.exe` + `JarvisApp.exe` rebuildados; `installer/pacote/Jarvis/`
  regenerado (~1,1 GB) com tudo + COMANDOS.md dentro.
- Verificado visualmente na janela real: HUD (relógio/clima/gauges/música),
  círculo trigonométrico na câmera, painel de configurações. Tudo renderiza certo.
- Verificado por dispatch: 73 comandos, 0 exceções.
- A partir daqui entro em cadência leve: checo a saúde do daemon de tempos
  em tempos e faço polimento pequeno, esperando você voltar e mandar parar.

## Rodada 2 (09/09, 19h) — bugs do Arthor + Onda 1 do Kimi

Arthur voltou, testou, e trouxe bugs + pediu pra aplicar ideias do kimi-cli.

**Bugs corrigidos:**
- Não dava pra sair do modo desenho/medida nem limpar os traços por voz.
  Causa: `STOP_WORDS` ("para", "chega") comia "para de desenhar" / "chega de
  medir" antes do handler; e o regex de sair era estreito e ainda reativava a
  entrada. Agora sair vem primeiro e cobre desativa/cancela/fecha/encerra/sai
  da/volta ao normal. "limpa a tela"/"limpa tudo" também apaga traços e medidas.
- Botões de fechar/config em cima do relógio e o X quase invisível na câmera —
  ajustado no `index.html` (fundo sólido, opacidade, relógio desceu, X desce
  abaixo do colchete no modo câmera). Verificado em navegador nos 2 modos.
- Relançamento do daemon morria no meio (`timeout /t 4` falha com stdin
  redirecionado) — agora usa ping + a instância nova espera o mutex (JARVIS_RELAUNCH).
- **bloquear a tela agora pede confirmação** (era imediato — foi o que me
  travou). Toggle `danger.allow_lock`.

**Onda 1 do KIMI_IDEAS.md (Arthur escolheu só a Onda 1):**
- `voice/hooks.py` + `hooks.toml` — sistema de hooks (8 eventos de ciclo de
  vida → speak / then / run shell). Fail-open. Automação sem programar.
- `voice/llm.py` — abstração de provedor (ollama | openai-compat | anthropic)
  com fallback. `Brain` agora fala com um `llm.Router`. Comportamento padrão idêntico.
- `voice/skills_extra.py` + `skills_extra.toml` — catálogo de skills declarativo:
  `[[skill]]` com patterns/speak/open/run/then/confirm. Prioridade sobre a torre
  de regex. Recarrega ao salvar.

Testado: daemon sobe limpo com os 3 módulos; 23 comandos variados por dispatch,
0 exceções. Onda 2/3 (MCP, task manager, IPC) ficaram documentadas, não feitas.

**Deploy (feito, ~20h):**
- `JarvisApp.exe` recompilado com os ajustes de UI — testado, abre OK.
- Frozen `JarvisVoice.exe` recompilado com Onda 1 — testado standalone:
  sobe com Whisper + Piper + `llm: provedor 'ollama'` + `hooks: 0 carregado`.
- `installer/pacote/Jarvis/` atualizado no lugar (sem re-baixar os 540 MB de
  modelos): novo daemon, novo app, hooks.toml, skills_extra.toml, profiles,
  COMANDOS.md, KIMI_IDEAS.md. config do pacote ganhou `provider = "ollama"`,
  mantém `active = "robson"` + Piper.
- Arthur baixou o `OllamaSetup.exe` (1,5 GB, assinatura Ollama Inc. válida) —
  coloquei em `installer/OllamaSetup.exe` e `payload/ollama/`. Agora o passo do
  Ollama no instalador abre a janela azul direto, sem mandar o Robson pro site.

**Pacote final: `installer/pacote/Jarvis/` (~2,6 GB), pronto pro Drive.**
JarvisSetup.exe + COMANDOS.md + LEIA-ME.txt + payload{voice frozen, jarvis-app,
models tiny+small, ollama}. Perfil padrão robson, provider ollama, voz Piper.

## Rodada 3 (09/09, 20h–21h30) — endgame holográfico: modelos + gestos

Instalador testado numa pasta isolada (`E:\_jarvis_install_test`, apagada):
cópia de 3219 arquivos OK, config repatchada (whisper→absoluto, perfil→robson),
launcher VBS OK, **daemon E app instalados bootaram** de um caminho novo. 3
atalhos mortos (`F:\Jarvis`, de um teste anterior) apagados com autorização.

**13 modelos de estudo novos** (`ui/models.js`): onda, pêndulo, circuito em
série, campo elétrico, soma de vetores, reta tangente/derivada (com expr),
integral/Riemann (com expr), superfície z=f(x,y), geometria VSEPR
(6 formas), CO₂, amônia. Verificados renderizando no navegador.
`skills.py`: `_MODELS` + extração de expressão + VSEPR nomeada.
BÔNUS: `STOP_WORDS` agora casa palavra inteira (`\bpara\b`) — "paraboloide"
não é mais engolido.

**3 gestos novos** (`ui/holograms.js`) — todos aprovados pelo Arthur:
- ✊✊ / ✋✋ com forma selecionada: gira como bola (trackball 2 mãos)
- ✋ modificadora sobre forma animada: congela e navega no tempo pela mão
- **menu de marcação** de 1 mão: palma parada ~0,5 s abre; empurra a mesma
  palma numa direção e segura ~1,1 s (LIMPAR/TRAVAR/DUPLICAR/EXPLODIR).
  1ª versão (radial + apontar com a outra mão) foi rejeitada — refeita.
  Estética refeita: texto glow sem caixa, no estilo do HUD.

**App rodando da FONTE** (`python app.py`) enquanto mexo nos hologramas —
mudança aparece na hora. Rebuild do `JarvisApp.exe` só quando a leva fechar.
50 commits na sessão.

## Encerramento (09/09, ~18h46)

Arthur voltou e mandou parar ("cheguei, ao finalizar esta tarefa, pare e me
diga tudo que aconteceu"). **Loop encerrado.**

Estado na hora de encerrar:
- Daemon de voz: vivo (pythonw 19940, ~524 MB, Whisper+Piper+LLM carregados),
  escrevendo `state.json` a cada segundo. Status OUVINDO, fase idle.
- Ollama: responde 200.
- Jarvis App: aberto (você já estava testando às 18h43–18h44).
- Git: branch `master`, árvore limpa, 34 commits desde o início da rodada.
- Correção final: checkboxes da seção D e "notícias" no ROADMAP estavam
  `[ ]` mas o trabalho existe desde os commits 274ebba/351d280 — marquei certo.
- Nada foi enviado pra fora da máquina.

## Onda 1 — controle pelo celular (10/09, ~16h50)

Arthur pediu ("Quer que eu comece por essa Onda 1? SIM / botão pra falar? SIM").
Feito e commitado (`a063401`).

O celular vira microfone + fone + telinha; o PC continua sendo o cérebro.
- `voice/remote.py` — servidor HTTPS **só na rede local**, token obrigatório em
  toda requisição, cert autoassinado (openssl do Git). `/listen` decodifica
  webm/opus (PyAV) → Whisper já carregado → `skills.dispatch` → Piper devolve
  o wav pro fone. Comandos destrutivos (desligar/reiniciar/bloquear) **recusados
  pelo celular**. Anti-flood (6 req/20 s) + lock serializando a execução.
- `voice/remote_page.html` — página push-to-talk (SEGURE PARA FALAR), estética
  HUD, fallback de texto, polling de `/state`.
- `Mouth.synth_file()` — gera o wav sem tocar na caixa de som do PC.
- App: botão 📱 + painel de pareamento com **QR** (`ui/remote.js`); some no modo
  câmera. QR gerado no daemon (`qrcode` → SVG data URI), passa no `state.json`
  (`remote_url` / `remote_qr`). `JarvisApp.exe` recompilado pra incluir.
- `config.toml [remote]` (enabled/port/token/bind). No pacote do Robson vai
  **desligado** por padrão (precisa de openssl na máquina dele) + `build_package_src.bat`
  agora tira `secrets.toml` e os arquivos de cert/token do pacote.

Testado ponta a ponta via curl: `/health`, `/`, `/state`, `/say` (dispatch +
wav), `/listen` (opus sintético → transcreve → responde), bloqueio de
"desliga o computador", chave errada → 403. Falta o Arthur parear o celular
de verdade (mesmo Wi-Fi, abrir o 📱, escanear, passar do aviso de certificado).

Estado: daemon vivo (pythonw 20664) com o servidor remoto no ar
(`https://192.168.15.3:8765`), `JarvisApp.exe` novo aberto (pid ~2656).

### Ainda pendente pro Arthur (fora da Onda 1)
- **Rodar `E:\OpenJarvis\LIMPAR_MINER.bat`** (2 cliques → "Sim" no UAC) — tira o
  cryptominer que veio do "adobe pack.exe" pirata. Reiniciar, rodar de novo,
  depois passar o Malwarebytes.
- **Compactar `installer\pacoteB\Jarvis\` e subir no Drive** pro Robson (rodar
  `build_package_src.bat` antes pra pegar o remote + a limpeza do secrets).

## Segundo Cérebro — 3º modo (10/09, ~18h)

Arthur: "vamos transformar o jarvis em um segundo cérebro para estudar... modo
cérebro(agora 'jarvis'), modo camera, modo segundo cerebro... teia de arquivos
igual no obsidian... mouse e teclado e também comando de voz". Depois, mid-turn:
"os arquivos de estudos serão compostos por células de anotações... manipuladas
por comando de movimento, pinça... webcam pequena no canto... quadro branco
(cor do tema) livre pra anotações por texto ou por voz" (print do "JARVIS.AIR"
do vídeo dos Maestros da IA). E mandou 4 repos de referência.

**Plano aprovado:** `C:\Users\thurg\.claude\plans\lazy-bubbling-llama.md`.
Decisões: integrar Obsidian de verdade (vault `.md` + `.canvas` em
`Documentos\Jarvis Vault`); o Jarvis classifica as notas; começar vault novo
com semente; quadro + teia juntos nesta leva.

Feito (commits `feat(brain2): … fundação` + o de voz/empacotamento):
- **`voice/vault.py`** — bootstrap do vault da semente + `.obsidian` mínimo;
  indexação incremental (frontmatter, `[[links]]`, `#tags`); classifica cada
  nota (materia/topico/ideia/questao/quadro/nota) por heurística → LLM só no
  ambíguo → cache + grava `tipo:` no frontmatter; thread `watch()`; escreve
  `jarvis-app/brain_graph.json`. CRUD de `.canvas` (add/connect/delete/new) +
  `handle()` dos comandos de voz.
- **`ui/atlas.js`** (Teia) — grafo força-dirigida Fruchterman-Reingold em
  canvas 2D; pan/zoom/arrastar; clicar nó → painel da nota (markdown mínimo
  próprio, `window.jarvisMD`); hover realça vizinhos; busca `/`; cor por tipo.
- **`ui/board.js`** (Quadro) — lousa infinita de células `.canvas` (DOM +
  SVG de arestas bézier); arrastar/resize/conectar/editar/apagar; autosave;
  barra IA/Texto/Imagem; gesto (punho pega a célula, palma arrasta o quadro —
  mapeamento do `ada_v2`); webcam encolhida no canto (`camera.js setViewport`).
- **`app.py`** — Api `brain_graph`/`board_read`/`board_write`/`note_text`/
  `board_open_obsidian` (`obsidian://`)/`brain_ctx`; view `brain2` no ciclo de 3.
- **`hologram.js`** — `applyView("brain2")` + sub-view board/teia + hooks +
  `window.jarvisBrainUI`; botão cicla Jarvis→Câmera→Segundo Cérebro.
- **`config.toml` `[brain]`**, `common.py` (`brain_ev` efêmero), semente
  `voice/vault_seed/` (Matemática → Trigonometria: tópicos, questões, ideias,
  um `.canvas` de 5 células).
- Empacotamento: `JarvisVoice.spec` + `build_package_src.bat`.

Testado: navegador com mock do bridge — teia (8 nós FR bem espalhados, cores,
rótulos, arestas), quadro (5 células do `.canvas` + bézier + markdown + painel
da nota). Daemon: vault criado, 8 notas indexadas, comandos de voz
("modo segundo cerebro", "mostra a teia", "cria uma celula sobre X",
"abre a materia matematica") todos OK.

Pendente (Onda J4, roadmap): células IA ao vivo, imagem/print, paridade de
gesto do `holograms.js`, `watchdog`, repetição espaçada, quadro pelo celular.
