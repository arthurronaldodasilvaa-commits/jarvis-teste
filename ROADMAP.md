# Jarvis — roadmap de ideias

Guardado em 2026-09-09. Não é ordem de prioridade — é o balde de ideias.

---

## A. Módulos de estudo holográficos (linha "Homem de Ferro")

- [ ] **Círculo trigonométrico** animado — ângulo varrendo, sen/cos como projeções em tempo real
- [ ] **Sólidos + fórmulas** — "mostra o volume da esfera" → 4/3·π·r³ ao lado da forma
- [ ] **Física** — vetores de força, lançamento oblíquo, plano inclinado, diagrama de corpo livre
- [ ] **Química** — moléculas 3D (H₂O, CH₄, benzeno) ball-and-stick + tabela periódica
- [ ] **Anatomia** — esqueleto / coração / cérebro (glTF), girar, cortar ao meio (plano de corte), rótulos
- [ ] **Plotter de função** — "plota y = x²" → curva/superfície neon 3D
- [x] Triângulo retângulo 3·4·5, tabela de ângulos notáveis, tabela de relações

## B. Interação de mão (câmera)

- [x] pinça seleciona/arrasta (âmbar) · 2 mãos escala · ✌️ gira · ✊ move tudo · ☝️ toca = apaga
- [ ] **Desenhar no ar** — indicador deixa rastro 3D neon
- [ ] **Medir** — pinça 2 pontos → distância
- [ ] **Travar/soltar** uma forma · **duplicar** ("copia isso")
- [ ] **Explodir** um modelo (separar peças com as 2 mãos)
- [ ] Rotação com uma mão só (twist)

## C. Assistente mais capaz (sem holograma)

- [x] **Timers e lembretes** — `voice/reminders.py`, persistente, thread que fala no vencimento
- [x] **Clima** (Open-Meteo, sem chave) — `voice/weather.py` · **contas** ("15% de 240") — `voice/calc.py`
  - [ ] **notícias** (falta — precisa de um feed/RSS; RSS de portal BR é keyless, dá pra fazer)
- [x] **Conversão** de unidades / moeda — `voice/calc.py` (comprimento, massa, temp, câmbio)
- [x] **Briefing na chegada** — `_briefing()` em jarvis_voice.py (hora + clima + lembretes do dia)
- [x] Ditado direcionado a um app específico — "escreve no bloco de notas: ..."

## D. HUD de verdade no cérebro

- [ ] Relógio + data + clima
- [ ] **Música tocando** (faixa + progresso do Spotify)
- [ ] **Gauges neon** de CPU / GPU / RAM / temperatura
- [ ] Estados visuais: pensando / pesquisando / erro
- [ ] Feed de notificações

## E. Câmera / visão

- [ ] **Modo presença** — pausa quando você sai, volta quando senta (rosto detectado)
- [ ] **Ler texto / QR** apontado pra câmera (OCR)
- [ ] Reconhecer você vs outra pessoa
- [ ] Gestos fora do modo holograma (pular música, etc.)

## F. Plataforma / infra

- [x] **Sistema de perfis** — `voice/profiles/<nome>.toml` sobrescreve o `config.toml`
  só na PERSONA (nome, tratamento, `system_prompt`, voz, frase de chegada). Todas as
  funções continuam iguais em qualquer perfil. Ativa por `[profile] active`,
  `--profile` ou `JARVIS_PROFILE`. Perfis: `arthur`, `robson`.
- [x] **Instalador gráfico** (`installer/`) — assistente estilo "instalar um jogo",
  sem terminal: escolhe disco, copia, instala Ollama + baixa modelo, configura
  mic/câmera/voz, autostart. `MONTAR_PACOTE.md` = como montar a pasta do Drive.
  Falta: testar o clique-a-clique numa máquina limpa antes de mandar pro cliente.
- [ ] Assinar o `JarvisSetup.exe` (tirar o aviso SmartScreen) — cert de code signing
- [ ] Painel de configurações no app (em vez de editar `config.toml` na mão)
- [ ] TTS melhor (Piper — voz neural local, rápida) ou ElevenLabs
- [ ] Modelo local maior quando tiver hardware (qwen 7b/14b)
- [ ] Fila `PEDIDOS.md` → "processa meus pedidos" abre uma sessão de dev

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
