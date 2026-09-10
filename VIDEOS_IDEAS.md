# Jarvis — ideias tiradas de 15 vídeos (IA / projetos de Jarvis)

Fonte: 15 links do YouTube que o Arthur mandou (14 vídeos únicos — um repetido).
Transcrições completas foram extraídas e lidas. Este documento separa **o que
vale copiar**, ranqueado por **impacto × risco**, e sempre amarrado aos arquivos
que já existem no projeto.

Data: 2026-09-10. Formato igual ao `KIMI_IDEAS.md`.

---

## Os vídeos (o que cada um realmente mostra)

| # | Canal | Título | Núcleo aproveitável |
|---|---|---|---|
| 1 | Zubair Trabzada / AI Workshop | I Built JARVIS with Claude Fable 5.1 | 2º cérebro 3D dos arquivos, tool-calling, ligação telefônica, persona mordomo |
| 2 | Tom Melo (Gravix) | JARVIS pessoal que sabe tudo do meu negócio | conectores Meta Ads/Instagram, voz ElevenLabs (e por que **não** compensa) |
| 3 | Mateus Dias | Testei o GPT-6 Astra | modelagem 3D / circuitos por prompt, deep-research, crítica a benchmark |
| 4 | Nerds de Negócios | Criei um Jarvis e cancelei todas as IAs | route-LLM, "analisa meu extrato e faz um painel", agente que **age** |
| 5 | Zubair | Is GPT-6 Astra AGI? Tested inside my JARVIS | **Olhos** (webcam), **Watch** (tela), **Foco** (trava aba + timer + contador de distração) |
| 6 | Maestros da IA | Criamos J.A.R.V.I.S. (Google AI Studio) | conversa com **barge-in**, busca **com fontes**, identificação de objeto/cena, gestos → canvas |
| 7 | Buildonaut | Build Your Own JARVIS in 10 min (Brahma, open-source) | briefing de sistema, "cria um app", organiza a pasta Downloads, **Mobile Connect por QR sem app** (= nossa Onda 1) |
| 8 | Hacksmith | I made JARVIS from Iron Man real (Smithi) | base de conhecimento dos próprios projetos, **incidente da pizza** (sem confirmação), fixação na palavra "generate" |
| 9 | Cyberbot | Demo do "Javes" comercial (R$ 9,90 vitalício) | abre/edita/fecha bloco de notas, cria/compacta pasta, **WhatsApp** (mensagem, apagar, listar grupos), Vision Control mão→cursor |
| 10 | ASN Web | Jarvis + Home Assistant + Tuya/Sonoff em 30 min | caminho Tuya → Home Assistant → Nabu Casa → asno.io; "comandos múltiplos" vs Alexa |
| 11 | FatihMakes | Jarvis Installation Step by Step | **inferno de versão do Python** (3.11 vs global) — exatamente o que quebrou pro Robson |
| 12 | FatihMakes | Jarvis Mark XXXV | **botão de MUTE (F4)**, memória ("meu nome é James"), pasta `actions/` = plugins, instalar jogo Steam/Epic por voz |
| 13 | Zubair | I Built JARVIS from Iron Man with Fable 5 | trocar o "cérebro" por voz (OpenRouter), memória de longo prazo = "máquina do tempo" |
| 14 | Zubair | I Gave JARVIS Full Control of My Computer | **takeover da tela com narração** + **seta apontando** onde clicar; sempre para no botão que gasta dinheiro (deixa em rascunho) |

Links: 1/13 `YK-qJwmwjVc` · 2 `sl-ByvLRAP0` · 3 `fMeVegslwA8` · 4 `gGFQU2CsAqk` ·
5 `mitzci4FsOg` · 6 `zgbJEBnTFyE` · 7 `F8_WMVQMetY` · 8 `e_nKCZe6Ikc` ·
9 `armZHBR-GvI` · 10 `GCEV9eR_IwA` · 11 `PWkyXZeXq3Q` · 12 `BhOsnGC_sAA` ·
14 `ud7wzdiM0gk` · (`I-cvxBMue08` = versão Fable 5 do #1).

---

## Tabela mestra — o que copiar

Legenda de risco: 🟢 baixo (mexe em coisa que já temos) · 🟡 médio (código
novo, sem depender de LLM grande) · 🔴 alto (precisa de LLM maior que o
`qwen3.5:2b` ou de automação frágil).

| Ideia | De onde | Como encaixa no que já temos | Impacto | Risco |
|---|---|---|---|---|
| **Modo Foco** (trava numa tarefa, timer, avisa quando você troca de janela, conta as distrações, alfineta com humor) | 5, 11 | `timers` + detecção de janela (`_app_command`/win32) + persona do Piper + HUD. Já está na Onda I do roadmap | ★★★★★ | 🟡 |
| **2º cérebro navegável** — grafo 3D das pastas/arquivos do Arthur; "Jarvis, abre tudo sobre X" puxa os arquivos; **mostra a fonte** (voa até o nó) | 1, 5, 13, 14 | já temos `materials.py` (RAG-lite), `study.py`, e o app holográfico (`models.js`, `hologram.js`). Falta: indexar pastas escolhidas + view "galáxia" + citar o arquivo que casou | ★★★★★ | 🟡 |
| **Confirmação p/ tudo que gasta / é irreversível** (o "freio de mão") | 8, 14 | generaliza o `[danger]` (hoje só shutdown/typing) e o `_BLOCK` do `remote.py`. **Prioridade alta** porque vai pro Robson | ★★★★★ | 🟢 |
| **Não ouvir a si mesmo** — mutar o mic (ou ignorar input) enquanto o Piper fala; **barge-in** = cortar a fala quando o usuário começa a falar | 6, 8, 12 | `jarvis_voice.py` loop de captura + `Mouth`. Provável buraco atual. É a maior lição de robustez dos vídeos | ★★★★★ | 🟡 |
| **Briefing melhor** (hoje: hora+clima+lembrete → +agenda do dia, +"o que precisa da sua atenção", +tarefas abertas) | 1, 5, 7, 13 | `[arrival] briefing` já existe; só ampliar o texto com `tasks.py`/`reminders.py`/`diary.py` | ★★★★ | 🟢 |
| **MUTE rápido** (tecla/gesto) — "quero falar sem o Jarvis responder" | 12 | atalho global (já temos Ctrl+Alt+J p/ pausar) + ícone no HUD. Um gesto 👎 também serviria (roadmap Onda I) | ★★★★ | 🟢 |
| **Memória de longo prazo / "máquina do tempo"** — fatos, preferências, "o que eu fiz terça passada" | 4, 12, 13 | `diary.py` já lê o próprio log; `push_note` já guarda notas. Falta um store de fatos ("me chama de Senhor", "meu treino é 3x semana") que entra no `system_prompt` | ★★★★ | 🟡 |
| **Trocar o "cérebro" por voz** ("Jarvis, usa o Gemini agora") | 4, 13 | `llm.Router` já tem `fallback_provider`. Só expor um comando que troca o provedor em runtime. Útil pro **pacote comercial** (Robson pluga um modelo pago) | ★★★ | 🟢 |
| **Ponteiro/seta na tela** — "me mostra onde clica pra criar um reel" | 14 | temos OCR (`ocr.js`/tesseract) + overlay na câmera/tela. Escopo pequeno: achar texto/elemento na tela e desenhar uma seta. Não precisa de LLM grande se for busca de texto | ★★★★ | 🟡 |
| **Gestos → cursor + ditado** (palma = move o mouse, punho = ditado, pinça = clica) | 6, 7, 9 | já temos MediaPipe (`handtrack.js`, `gestures.js`) e gestos de mídia. Estender p/ controle de cursor + um punho "ditado". `gestures.toml` já está no roadmap | ★★★ | 🟡 |
| **Instalar jogo por voz** (`steam://install/<appid>`) | 12 | `skills.py` já indexa e **abre** jogos da Steam (`_STEAM_LIBS`). Instalar é 1 linha a mais. Demo boa, risco nenhum | ★★ | 🟢 |
| **Conector Telegram** (bot oficial) — receber comando / mandar resposta e arquivos fora de casa | 1, 5, 13 | API oficial é estável (ao contrário do WhatsApp). Casa com a Onda 1 (celular). Bom pro "me manda o resumo" | ★★★ | 🟡 |
| **Organizar pasta bagunçada** ("arruma minha pasta Downloads") | 7 | Windows + `os`/`shutil`. Com **confirmação** e **preview** ("vou mover 40 arquivos em 6 grupos, ok?"). Risco = destrutivo → tem que ser reversível/dry-run | ★★★ | 🟡 |
| **Conectores Gmail / Google Agenda** | 1, 4, 5, 13, roadmap I | roadmap já cita. API direta (OAuth). Sem LLM grande dá pra "quais meus eventos hoje / cria evento". Ler e-mail e **agir** já precisa de modelo melhor | ★★★★ | 🔴 |
| **Conector WhatsApp** (mercado BR — é o produto inteiro do Cyberbot) | 9 | valioso pro comercial, mas **frágil**: no vídeo do Cyberbot a ponte cai ao vivo várias vezes. Só com reconexão automática + UX honesta ("a conexão caiu") | ★★★★ | 🔴 |
| **Takeover da tela / computer-use com narração** ("clicando em criar… nomeando… scroll…") e **parando no botão que gasta** | 14 | poderosíssimo, mas `qwen3.5:2b` não dá conta. **Adotar já o *padrão***: qualquer ação de UI narra o que faz e para em rascunho. Fazer de verdade = pós LLM grande | ★★★★★ | 🔴 |
| **"Cria um app/joguinho"** (calculadora, snake) | 7, 12 | os próprios vídeos admitem "é versão demo". Com 2b sai ruim. Versão com **templates** ("cria um cronômetro") funciona. Overlap com "co-piloto de código" da Onda I | ★★ | 🔴 |
| **Home Assistant / casa inteligente** (Tuya, Sonoff) | 10 | mundo à parte. Só se o Arthur/Robson tiver dispositivos. `facts.py` já faz HTTP. Integração real = via API do Home Assistant (token de longo acesso) | ★★ | 🔴 |
| **Ligação telefônica** (Retell/Twilio — liga em restaurante, pede preço) | 1, 13 | legal, mas $$ e não-local. Fora do escopo "Jarvis do Robson" por enquanto | ★★ | 🔴 |

---

## Robustez / "deixar a lógica mais robusta" — as lições concretas

Estes vídeos são um catálogo de **como esses projetos quebram**. Vários buracos
o Jarvis já cobre; uns não.

### 1. Não ouvir a própria voz + barge-in  🟡
- Hacksmith: "mandou os últimos 2 min de áudio pra transcrição" sem querer.
- FatihMakes: "toda vez que você fala, o Jarvis responde" → solução foi um
  botão de **mute (F4)**.
- Maestros: só funciona bem com **fone** pra IA não captar o próprio alto-falante.
- **Estado atual:** `_handle_block` já começa com `if mouth.speaking:
  ring.clear(); return` — ou seja, **o daemon já descarta áudio enquanto o
  Piper fala.** Bom. Faltam duas coisas:
  - **(a) margem pós-fala** (~300 ms) — logo depois de `speaking=False` o
    primeiro bloco ainda pode ter cauda/eco da última palavra do TTS.
  - **(b) barge-in** — hoje, *porque* o áudio é descartado enquanto fala, o
    usuário **não consegue interromper** a fala falando por cima (só com
    Ctrl+Alt+J). Os vídeos (Maestros) mostram barge-in como diferencial.
    Precisaria de um caminho leve: detectar energia de voz alta durante
    `mouth.speaking` → `mouth.stop()` (matar o processo do Piper) e voltar a ouvir.

### 2. Confirmação para ações que gastam / não voltam  🟢 *(prioridade — vai pro Robson)*
- Hacksmith: **pediu uma pizza de verdade sem querer** porque o sistema de
  pedido "não tinha freio de mão". Depois pediu **outra** por ruído de conversa.
- Zubair: o design certo — *"eu monto tudo, mostro o trabalho, e paro no botão
  que gasta seu dinheiro. O último clique é trabalho de humano."* Sempre deixa
  em **rascunho**.
- **Ação:** hoje `[danger]` só cobre desligar/reiniciar/digitar. Generalizar:
  **qualquer** skill que mande mensagem, compre, poste, apague, ou gaste →
  passa por `Result.confirm`. O `remote.py` já recusa comando destrutivo do
  celular (`_BLOCK`); trazer a mesma lista pro núcleo.

### 3. Versão do Python  🟢 *(já resolvido — validado)*
- FatihMakes gasta **metade do vídeo** explicando 3.11 vs Python global,
  "couldn't resolve", `py -3.11 -m pip install …`. É **exatamente** o que
  quebrou na máquina do Robson.
- **Validação:** o Pacote B (Python embarcado e assinado) mata isso. Manter.
- **Extra:** o `DIAGNOSTICO.bat` já roda o console; garantir que ele imprime
  **versão do Python + libs faltando** em texto claro, não um traceback cru.

### 4. Fixação em palavra exata  🟡
- Hacksmith: o modelo travou na palavra **"generate"** e não entendia
  "draw/paint/render/create".
- O Jarvis tem o mesmo risco: a torre de regex do `skills.py` é finita. `_MK`
  cobre `cria|faz|gera|desenha|mostra|abre…` mas nunca vai cobrir tudo.
- **Ação:** o roteador LLM (fallback) tem que pegar os sinônimos que a regex
  perde — e o `_ROUTER_PROMPT` tem que **listar exemplos variados** por skill.
  A ideia do `KIMI_IDEAS.md` (catálogo declarativo que **gera** o prompt do
  roteador) resolve isso de vez: a doc nunca desatualiza.

### 5. Pontes web frágeis  🔴
- Cyberbot: a ponte do WhatsApp **cai ao vivo** 4–5 vezes no vídeo ("time out
  de novo", "a conexão tá oscilando").
- **Regra:** se um dia entrar WhatsApp/browser-automation, precisa de
  reconexão automática + estado visível ("caiu, reconectando…") — nunca falha
  silenciosa. O `_atomic_write` + threads-com-guarda já seguem essa filosofia.

### 6. Buffer de áudio vazando contexto  🟡
- Hacksmith de novo: "gravou os últimos 2 minutos e mandou". 
- **Ação:** confirmar que `pre_roll_seconds` (0.6 s hoje) e
  `max_utterance_seconds` (7 s) **cortam** a fala e que o buffer é limpo entre
  comandos. Um comando não pode arrastar áudio do anterior.

---

## Novas ferramentas e como aplicar (resumo executivo)

O `KIMI_IDEAS.md` já defende **MCP client** + **catálogo de skills declarativo**
+ **camada de abstração de LLM**. Estes vídeos **confirmam** e priorizam:

1. **Conectores que importam (ordem de valor real):** Agenda Google → Telegram
   → Gmail → (WhatsApp, se der pra estabilizar). Não é "todos os MCPs do
   mundo" — é esses 3–4.
2. **Camada de política de ação** (o "freio de mão" universal) antes de
   qualquer conector que escreva. É o pré-requisito de segurança.
3. **Trocar de modelo em runtime** — o `Router` já quase faz; expor por voz
   destrava "modo barato" (2b local) vs "modo pro" (API paga) sem reiniciar.
   É a peça que deixa o pacote do Robson **crescer** sem retrabalho.
4. **Olhos/Tela** — já temos câmera + OCR no app. O que falta é o Jarvis
   *raciocinar* sobre o que vê ("essa postura tá ruim", "você tá na aba errada").
   Escopo curto (regra fixa) funciona hoje; escopo aberto precisa de LLM maior.
5. **"Modo Foco"** é o recurso de maior impacto × menor risco da lista inteira.
   Começaria por ele.

---

## O que **NÃO** copiar

- **Voz na nuvem (ElevenLabs / OpenAI TTS) como padrão.** O próprio Tom Melo
  diz: *"é lerdo, tem delay grande, é caro, gasta muito token — não compensa
  ficar conversando, é só pra experiência."* O Piper local continua sendo a
  escolha certa. (ElevenLabs opcional pra quem quiser pagar, ok — mas nunca
  default.)
- **Correr atrás de benchmark.** Mateus Dias: as empresas otimizam o modelo
  *pro benchmark*, não pro uso real. O que vale é teste prático.
- **Teatro de "single prompt".** Os vídeos que mostram "fiz X com 1 prompt"
  quase sempre têm skills/rotinas escondidas. Mateus testou e não reproduziu.
- **Dependência de nuvem.** O vídeo do Home Assistant deixa claro: Wi-Fi/Tuya =
  servidor na China/Coreia/EUA; local = melhor, mais rápido, mais privado. O
  Jarvis é local-first — manter.
- **Modelo "assina minha comunidade pra baixar o zip".** Não é o nosso caso.
- **Ligação telefônica paga (Retell/Twilio)** — custo recorrente, não-local.
  Fora do escopo do Jarvis do Robson.

---

## Sugestão de ondas (encaixando no ROADMAP_2.md)

**Onda J — robustez de áudio + segurança (antes de qualquer feature nova)**
- J1. Mic não escuta enquanto o Piper fala + barge-in (corta o TTS).  🟡
- J2. `[danger]` universal: toda skill que gasta/apaga/envia → `confirm`.  🟢
- J3. `DIAGNOSTICO.bat` imprime versão do Python + libs faltando legível.  🟢
- J4. Confirmar limpeza de buffer de áudio entre comandos.  🟡

**Onda K — Modo Foco + Briefing**
- K1. Modo Foco: trava tarefa, timer, detecta troca de janela, conta drift,
  alfineta.  🟡
- K2. Briefing ampliado: + tarefas abertas + agenda do dia.  🟢
- K3. Mute rápido (tecla + gesto 👎).  🟢

**Onda L — 2º cérebro navegável**
- L1. Indexar pastas escolhidas (`[study] materials_dir` já existe; ampliar).
- L2. View "galáxia" no app (nós = arquivos, cor por tipo).  🟡
- L3. Citar a fonte: ao responder de um arquivo, o app destaca o nó.  🟡

**Onda M — conectores (precisa da fundação do KIMI_IDEAS)**
- M1. Trocar modelo por voz (`Router` em runtime).  🟢
- M2. Agenda Google (ler + criar evento).  🔴
- M3. Telegram bot (comando + resposta + arquivo).  🟡

**Depois (pós LLM maior):** takeover de tela com narração, Gmail com ação,
WhatsApp, "cria um app" de verdade.
