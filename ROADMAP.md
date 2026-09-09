# Jarvis — roadmap de ideias

Guardado em 2026-09-09. Não é ordem de prioridade — é o balde de ideias.

> **09/09 (tarde):** Claude aplicou sozinho ~todas as seções A–F enquanto o
> Arthur estava fora. Ver `AUTONOMOUS_LOG.md`. Os `[ ]` que sobraram têm o
> motivo escrito (asset que falta, chave paga, hardware).

---

## A. Módulos de estudo holográficos (linha "Homem de Ferro")   — `ui/models.js`

- [x] **Círculo trigonométrico** animado — ângulo varrendo, sen/cos como projeções em tempo real
- [x] **Sólidos + fórmulas** — "fórmula do volume da esfera" → sólido girando + V/A ao lado
- [x] **Física** — corpo livre, lançamento oblíquo (bola animada na parábola), plano inclinado (decomposição de P)
- [x] **Química** — H₂O, CH₄, benzeno (ball-and-stick) + tabela periódica (painel)
- [x] **Plotter de função** — "plota x ao quadrado − 4" → curva neon com eixos
- [x] **Biologia** — célula animal (membrana, núcleo, mitocôndrias rotuladas)
- [ ] **Anatomia** — esqueleto / coração / cérebro (precisa de assets glTF — não dá procedural bom)
- [x] Triângulo retângulo 3·4·5, tabela de ângulos notáveis, tabela de relações

## B. Interação de mão (câmera)   — `ui/holograms.js`

- [x] pinça seleciona/arrasta (âmbar) · 2 mãos escala · ✌️ gira · ✊ move tudo · ☝️ toca = apaga
- [x] **Desenhar no ar** — "modo desenho" + ☝️ deixa rastro neon; "limpa o desenho"
- [x] **Medir** — "modo medida" + pinça 2 pontos → linha + distância
- [x] **Travar/soltar** — "trava essa forma" (fica verde, não move) / "solta isso"
- [x] **Duplicar** — "copia isso" / "duplica essa forma"
- [x] **Explodir** — "explode a molécula" (afasta as peças; de novo volta)
- [x] **Rotação com uma mão só** — ✌️ da mão seletora gira pela inclinação da palma

## C. Assistente mais capaz (sem holograma)

- [x] **Timers e lembretes** — `voice/reminders.py`, persistente, thread que fala no vencimento
- [x] **Clima** (Open-Meteo, sem chave) — `voice/weather.py` · **contas** ("15% de 240") — `voice/calc.py`
  - [x] **notícias** — `voice/news.py` (RSS do Google Notícias, sem chave; "quais as notícias de hoje")
- [x] **Conversão** de unidades / moeda — `voice/calc.py` (comprimento, massa, temp, câmbio)
- [x] **Briefing na chegada** — `_briefing()` em jarvis_voice.py (hora + clima + lembretes do dia)
- [x] Ditado direcionado a um app específico — "escreve no bloco de notas: ..."

## D. HUD de verdade no cérebro   — `voice/hud.py` + `ui/hud.js`

- [x] Relógio + data + clima
- [x] **Música tocando** — faixa + barra de progresso (winsdk, qualquer player)
- [x] **Gauges neon** de CPU / RAM / GPU (psutil + pynvml) — falta só temperatura (precisa lib admin)
- [x] Estados visuais: PENSANDO / PESQUISANDO / ERRO (campo `phase` no state.json)
- [x] Feed de notificações (`push_note` → HUD)

## E. Câmera / visão   — `ui/vision.js`

- [x] **Modo presença** (leve) — `[camera] auto_return_seconds`: volta pro cérebro se
  ninguém aparece (mãos ausentes + frame estático). Presença "sai da sala" real
  precisaria de câmera sempre ligada + face detection.
- [x] **Ler QR** — "Jarvis, lê o QR code" → BarcodeDetector nativo do WebView2;
  link abre no navegador, texto é falado.
  - [ ] **OCR de texto** — precisa bundlar tesseract.js + por.traineddata (~13 MB);
    decisão de tamanho pro pacote. QR cobre o caso comum.
- [ ] **Reconhecer você vs outra pessoa** — precisa face-api.js + modelos (~6 MB) + enrollment
- [x] **Gestos fora do modo holograma** — mão aberta varre = ⏮/⏭, punho ~1s = ⏯,
  palma subindo/descendo = volume (só quando não há hologramas na tela)

## F. Plataforma / infra

- [x] **Sistema de perfis** — `voice/profiles/<nome>.toml` sobrescreve o `config.toml`
  só na PERSONA (nome, tratamento, `system_prompt`, voz, frase de chegada). Todas as
  funções continuam iguais em qualquer perfil. Ativa por `[profile] active`,
  `--profile` ou `JARVIS_PROFILE`. Perfis: `arthur`, `robson`.
- [x] **Instalador gráfico** (`installer/`) — assistente estilo "instalar um jogo",
  sem terminal: escolhe disco, copia, instala Ollama + baixa modelo, configura
  mic/câmera/voz, autostart. `MONTAR_PACOTE.md` = como montar a pasta do Drive.
  Falta: testar o clique-a-clique numa máquina limpa antes de mandar pro cliente.
- [x] **Painel de configurações no app** — ícone ⚙ ou "Jarvis, abre as configurações".
  Edita perfil/voz/mic/câmera/cidade/chegada/danger; salva no `config.toml` e reinicia
  o daemon (via `reload.flag`). `ui/settings.js`, `app.py` Api.get_config/set_config.
- [x] Fila `PEDIDOS.md` → "quais meus pedidos" lista, "processa meus pedidos" abre o arquivo.
- [ ] Assinar o `JarvisSetup.exe` (tirar aviso SmartScreen) — precisa cert de code-signing (pago, identidade)
- [x] **TTS melhor (Piper)** — voz neural local `pt_BR-faber-medium` (RTF 0.07, muito
  mais natural que a SAPI Maria). `[tts] engine = "piper"`; `Mouth._piper_say()` gera
  wav e toca com winsound; fallback automático pro SAPI. `voice/piper/` (~98 MB, fora
  do git, entra no pacote e no `_internal/` do exe congelado).
- [ ] Modelo local maior (qwen 7b/14b) — só trocar `[assistant] model`; precisa de RAM/GPU

---

## G. Versão comercial — cliente: instituto de desenvolvimento pessoal

Contexto: instituto focado em **treinamentos corporativos** (cultura organizacional).
Usa no **notebook**, focado no trabalho. Sem os jogos / brincadeiras pessoais.

Pedidos do cliente (do mais simples ao mais complexo):

1. **Google Maps** — abrir para viajar (rotas), achar empresas, achar restaurantes
   bem avaliados (5 estrelas)  ← **COMEÇAR POR AQUI**
2. **Meta (Ads)** — criar campanhas de tráfego  → precisa Meta Marketing API + app review
3. **HostGator** — criar sites  → API/cPanel + provavelmente um gerador de site
4. **IA de vídeo** — gerar vídeos  → integrar uma API (ex: pika/runway/heygen)
5. "e assim vai" — mais integrações sob demanda

Notas de escopo:
- 1 é URL scheme (fácil, sem chave). 2–4 são projetos reais, cada um com auth OAuth + custo de API.
- Provável arquitetura: Jarvis "base" + módulos plugáveis por assinatura.
- Vender como: instalação personalizada (one-time) + suporte/atualizações (mensal).
