# Jarvis — Roadmap 2 (melhorias sem depender de upgrade)

Guardado em 2026-09-09 (noite). O Arthur saiu e pediu pra aplicar TUDO desta
lista, autonomamente, commitando a cada passo, sem teste destrutivo, parando só
quando ele mandar. Ao acabar: criar tarefas novas, revisar/otimizar/polir o
código, melhorar design, ter e aplicar mais ideias.

**Máquina:** 16 GB RAM (~4 livres), GTX 1650 4 GB, sem LLM grande, sem cert pago.
**O que funciona bem e está subaproveitado:** renderizador Three.js, MediaPipe
mãos + face-api, Whisper + Piper, APIs web sem chave, automação Windows, e os
sistemas declarativos (hooks / skills_extra / study / invent).

Regras que eu (Claude) sigo: só local, nada sai da máquina, commit por feature,
nada de comando destrutivo em teste (lição da tela travada), `secrets.toml`
nunca versionado.

---

## Onda A — Hologramas interativos  ← COMEÇAR AQUI

O maior salto de "sensação de Iron Man". Renderizador + mãos já dão conta.

- [ ] **A1. Sliders no ar** — um controle que você pega com a pinça e arrasta;
      cada modelo animado expõe 1–3 parâmetros (`params`) e o `update(t)` passa a
      ler os valores atuais. Ex: plano inclinado → ângulo; lançamento → v₀ e θ;
      onda → frequência e amplitude; átomo → nº de camadas.
- [ ] **A2. Painel de parâmetros por voz** — "muda o ângulo pra 30 graus",
      "aumenta a massa", "diminui a frequência" ajustam o slider correspondente.
- [ ] **A3. Leitura ao vivo** — o modelo mostra os valores derivados mudando
      (ex: alcance do projétil, período do pêndulo) enquanto você mexe.
- [ ] **A4. Comparar dois modelos** — "põe outro lançamento do lado" e os dois
      rodam em paralelo com params diferentes.

## Onda B — Jarvis lê os SEUS materiais (RAG-lite, local)

- [ ] **B1. Índice de estudos** — `[study] materials_dir` no config; um módulo
      varre .txt/.md/.pdf (pdf via pypdf, leve), quebra em parágrafos, guarda
      num índice simples (palavra→parágrafos).
- [ ] **B2. Pergunta com fonte** — "o que meu resumo diz sobre X" → acha os 2–3
      parágrafos mais relevantes (BM25/keyword), joga pro LLM com "responda SÓ
      com base nisto", e cita o arquivo.
- [ ] **B3. "resume meu resumo de X"** / "faz um flashcard disso".
- [ ] **B4. Reindexar** — "atualiza meus materiais" e no startup.

## Onda C — Integrações web sem chave (grátis)

- [ ] **C1. Bolsa B3** — brapi.dev (keyless) — "quanto tá a Petrobras/Vale/Itaú".
- [ ] **C2. CEP → endereço** — ViaCEP.
- [ ] **C3. Próximo feriado / feriados do ano** — BrasilAPI.
- [ ] **C4. Qualidade do ar** — Open-Meteo air-quality (já uso Open-Meteo).
- [ ] **C5. Fase da lua + nascer/pôr do sol** — Open-Meteo daily / sunrise-sunset.org.
- [ ] **C6. "Hoje na história"** — Wikipedia On this day REST (com UA compliant).
- [ ] **C7. Resumir um link** — "resume esse site: <url>" → fetch + extrai texto +
      LLM resume curto.
- [ ] **C8. Frase do dia / citação** — API keyless de quotes (pt se der).

## Onda D — Mais poder no Windows (local)

- [ ] **D1. Lista de tarefas por voz** — `tasks.md`; "adiciona X na lista",
      "quais minhas tarefas", "risca a X", "limpa a lista". HUD mostra as 3 próximas.
- [ ] **D2. "o que tá pesado"** — top 3 processos por CPU/RAM (psutil).
- [ ] **D3. Cronômetro / pomodoro no HUD** — "cronômetro de 25 minutos" com
      barra e alarme, independente do modo prova.
- [ ] **D4. Modo apresentação** — gesto de varrer = seta direita/esquerda
      (PowerPoint/PDF); "modo apresentação" liga isso e desliga o resto.
- [ ] **D5. Memo de voz** — "grava um memo" → grava wav + transcreve com Whisper
      → salva `memos/AAAA-MM-DD_HHMM.txt`; "meus memos" lista.
- [ ] **D6. Ler em voz alta** — "lê isso" (clipboard) / "lê esse arquivo" /
      "lê essa página" → Piper narra, "para de ler" interrompe.
- [ ] **D7. Esvaziar lixeira / limpar temp** — com confirmação falada.

## Onda E — Mais modelos de estudo + Modo Aula

- [ ] **E1. Óptica** — lente convergente/divergente, raios, foco, imagem.
- [ ] **E2. Álgebra linear** — matriz como transformação do plano (aplica numa
      figura), determinante como área.
- [ ] **E3. Biologia** — mitose/meiose (fases), neurônio + sinapse.
- [ ] **E4. Física** — colisão elástica/inelástica (2 blocos), MRU×MRUV (gráficos
      s-t e v-t lado a lado), circuito em paralelo.
- [ ] **E5. Matemática** — árvore de probabilidade, função exponencial×log,
      comparação sen/cos/tan num gráfico só.
- [ ] **E6. Química** — pilha eletroquímica, curva de titulação/pH, ligações
      iônica×covalente.
- [ ] **E7. Modo Aula** — "me dá uma aula sobre X" → o LLM faz um roteiro curto e
      o Jarvis vai FALANDO e criando os hologramas na hora, passo a passo, com
      pausa ("diga continua").

## Onda F — Precisa baixar (grátis, o Arthur autorizou)

- [ ] **F1. OCR** — tesseract.js + `por.traineddata` (~13 MB) em `ui/lib/tess/`.
      "Jarvis, lê o texto" na câmera → detecta e fala / copia. Também
      "lê esse print".
- [ ] **F2. Anatomia** — procurar modelos glTF CC0 (esqueleto, coração 3D,
      cérebro). Se achar bom: bundlar e carregar via `THREE.GLTFLoader`.
      Se não achar: melhorar os procedurais (esqueleto de linhas rotulado).

## Onda G — Pendências do ROADMAP.md antigo

- [x] Reconhecer você vs outra pessoa (feito — face-api).
- [ ] **G1. Temperatura CPU/GPU no HUD** — tentar `LibreHardwareMonitorLib`
      (DLL grátis, sem precisar de admin em alguns casos) ou WMI
      `MSAcpi_ThermalZoneTemperature`; se nada der, `nvidia-smi` já dá a da GPU.
- [ ] **G2. Anatomia** — ver F2.
- [ ] Assinar o instalador — **BLOQUEADO** (cert pago + verificação de identidade).
      Documentar o passo pro Arthur fazer.
- [ ] Modelo LLM maior — **BLOQUEADO** por RAM/GPU. A camada de troca já existe;
      documentar como ligar quando tiver hardware/nuvem.

## Onda H — Otimização, revisão e polimento

- [ ] **H1. Revisão de código** — passar por skills.py (2000+ linhas), quebrar em
      módulos por área se fizer sentido; remover código morto; pyflakes limpo.
- [ ] **H2. Performance do daemon** — perfilar o caminho ouvir→responder; reduzir
      latência (STT, dispatch, TTS). Cache do que dá.
- [ ] **H3. Performance do app** — o loop da câmera roda hands + face + vision +
      holo por frame. Medir FPS, escalonar (face já é 1,4 s; hands podia cair
      pra 20 fps quando não tem gesto). Reduzir garbage no tick.
- [ ] **H4. Design do HUD** — revisão visual: consistência de fontes/espaços,
      transições mais suaves, o feed sumindo com fade, o painel de estudo,
      estados de erro. Modo claro? (provavelmente não, mas revisar contraste.)
- [ ] **H5. Design do cérebro** — a esfera holográfica: mais viva, reage à voz
      melhor, partículas, cor por fase.
- [ ] **H6. Robustez** — todo `write_control`/`write_app_state` à prova de disco
      cheio/lock; todo thread com try/except que loga e continua; nenhum caminho
      que trave o daemon.
- [ ] **H7. Arranque mais rápido** — carregar Whisper `small` sob demanda (só
      quando precisa da 2ª passada) em vez de no boot? medir.
- [ ] **H8. COMANDOS.md e docs** — regenerar com tudo que existe agora.

## Onda I — Ideias novas (preencher e aplicar conforme sobrar tempo)

- [ ] Modo "co-piloto de código" leve — lê um arquivo, explica, sugere (2b limitado).
- [ ] "Diário de bordo" — o Jarvis registra o que você fez no dia (comandos,
      tempo de estudo) e faz um resumo à noite.
- [ ] Gestos configuráveis (`gestures.toml`).
- [ ] Temas de cor do holograma (`[app] theme`).
- [ ] Atalho de teclado global pra "print + OCR + copia".
- [ ] Reconhecimento de gesto de "positivo/negativo" (👍/👎) pra confirmar sem voz.
- [ ] Jarvis reage a silêncio longo com uma frase (hook on_idle já permite).
- [ ] Modo "foco" que bloqueia sites/apps distração por X minutos.
- [ ] Integração com o Google Agenda (o MCP/connector já existe no ambiente do
      Claude, mas no Jarvis seria via API — avaliar).

---

## Log de execução

Ver `AUTONOMOUS_LOG.md` — vou anotando cada onda concluída lá.
