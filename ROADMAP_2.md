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

## Onda A — Hologramas interativos  ✅

O maior salto de "sensação de Iron Man". Renderizador + mãos já dão conta.

- [x] **A1. Sliders no ar** — pinça arrasta; lancamento/planoInclinado/onda/
      pendulo/lente expõem `params` e leem os valores no `update(t)`.
- [x] **A2. Painel de parâmetros por voz** — "muda o ângulo pra 30",
      "aumenta a massa", "diminui a frequência" (`_holo_param` + `matchParam`).
- [x] **A3. Leitura ao vivo** — labels dos modelos mostram alcance/período/etc.
      recalculados a cada frame.
- [ ] **A4. Comparar dois modelos** — adiado (baixo valor vs. custo; o usuário
      pode pedir 2 lançamentos e mover um com ✊). Fica na gaveta.

## Onda B — Jarvis lê os SEUS materiais (RAG-lite, local)  ✅

- [x] **B1. Índice de estudos** — `[study] materials_dir`; `materials.py` varre
      .txt/.md/.pdf (pypdf), `_split()` em blocos, índice df + cache json.
- [x] **B2. Pergunta com fonte** — "o que meu resumo diz sobre X" → BM25-lite →
      LLM "responda SÓ com base nisto" + cita o arquivo.
- [x] **B3. "resume ... nos meus materiais"** (`resume()`).
- [x] **B4. Reindexar** — "atualiza meus materiais" + no startup.

## Onda C — Integrações web sem chave (grátis)  ✅  (`facts.py`)

- [x] **C1. Bolsa B3** — brapi.dev.  - [x] **C2. CEP** — ViaCEP.
- [x] **C3. Feriados** — BrasilAPI.  - [x] **C4. Qualidade do ar** — Open-Meteo.
- [x] **C5. Fase da lua + sol** — Open-Meteo daily + cálculo próprio.
- [x] **C6. "Hoje na história"** — pt.wikipedia onthisday (UA compliant).
- [x] **C7. Resumir um link** — "resume esse site: <url>".
- [x] **C8. Frase do dia** — ZenQuotes.

## Onda D — Mais poder no Windows (local)  ✅

- [x] **D1. Lista de tarefas por voz** — `tasks.py` / `tasks.json`; HUD mostra.
- [x] **D2. "o que tá pesado"** — top 3 por CPU e por RAM (psutil).
- [x] **D3. Cronômetro / pomodoro no HUD** — "pomodoro de 25 minutos" + contagem.
- [x] **D4. Modo apresentação** — varrer a mão = seta ←/→ (`vision.js` presentMode).
- [x] **D5. Memo de voz** — `_record_memo` → `voice/memos/AAAA-MM-DD_HHMM.txt`.
- [x] **D6. Ler em voz alta** — `read_aloud.py`, clipboard/arquivo/URL, "para de ler".
- [x] **D7. Esvaziar lixeira** — com confirmação falada (bloco recycle-bin).

## Onda E — Mais modelos de estudo + Modo Aula  ✅

- [x] **E1. Óptica** — lente convergente (com sliders foco/objeto).
- [x] **E2. Álgebra linear** — matriz como transformação do plano (`transformacoes`).
- [x] **E3. Biologia** — neurônio + sinapse.
- [x] **E4. Física** — colisão elástica (2 blocos), circuito em paralelo.
- [x] **E5. Matemática** — árvore de probabilidade.
- [x] **E6. Química** — pilha eletroquímica.
- [x] **E7. Modo Aula** — `aula.py`, "me dá uma aula sobre X", passo a passo.
      (modo Enem foi criado e depois REMOVIDO a pedido do Arthur.)

## Onda F — Precisa baixar (grátis, o Arthur autorizou)  ✅

- [x] **F1. OCR** — tesseract.js 5.1 + `por.traineddata.gz` (6,7 MB) em
      `ui/lib/tesseract/`. "lê o texto" → fala + copia pra área de transferência.
- [x] **F2. Anatomia** — não achei glTF CC0 confiável offline; fiz procedural
      bom: `esqueleto` e `cerebro` rotulados. DNA/coração/neurônio já existiam.

## Onda G — Pendências do ROADMAP.md antigo

- [x] Reconhecer você vs outra pessoa (feito — face-api).
- [x] **G1. Temperatura GPU no HUD** — via NVML (`nvmlDeviceGetTemperature`).
      CPU: `sensors_temperatures` não existe no Windows e o WMI MSAcpi exige
      admin → some com elegância. Documentado como bloqueio de permissão.
- [x] **G2. Anatomia** — ver F2.
- [x] Assinar o instalador — **BLOQUEADO** (cert pago + verificação de
      identidade). Passo documentado em `docs/DEPLOY.md`.
- [x] Modelo LLM maior — **BLOQUEADO** por RAM/GPU. `llm.Router` já troca de
      provedor; como ligar documentado em `docs/DEPLOY.md` + `config.toml`.

## Onda H — Otimização, revisão e polimento

- [x] **H1. Revisão de código** — pyflakes 100% limpo em todo `voice/*.py` +
      `app.py`; código morto removido (`nome`, `tgt_zone`, imports, f-strings).
      skills.py fica monolítico de propósito (ordem do dispatch é a lógica).
- [~] **H2. Performance do daemon** — ver `docs/PERF.md`. Feito: Whisper `small`
      lazy (H7), `norm()` cacheado, `_atomic_write`, event loop do asyncio
      fechado. Pendente (risco vs. ganho, precisa de teste ao vivo): Piper em
      processo vivo, Whisper na GPU.
- [x] **H3. Performance do app** — loop da câmera escalonado: hands a cada frame
      só quando há mão; senão 2 em 3 frames. face 1,4s, ocr sob demanda.
      `hologram.js` poll 250ms mantido. Menos alocação no tick.
- [x] **H4. Design do HUD** — tokens de cor/espaço unificados, fade real no
      feed, painel de estudo e timer alinhados, estado de erro âmbar/vermelho.
- [x] **H5. Design do cérebro** — esfera reage à fase (cor + pulso), partículas
      mais suaves, brilho ao falar.
- [x] **H6. Robustez** — `_atomic_write` com try/except em todo lugar; threads
      com guarda que loga e continua; daemon nunca trava por erro de disco.
- [x] **H7. Arranque mais rápido** — Whisper `small` carrega na 1ª vez que a 2ª
      passada é necessária, não no boot. Boot ~2–3s mais rápido.
- [x] **H8. COMANDOS.md e docs** — `COMANDOS.md` regenerado + `docs/`.

## Onda I — Ideias novas (preencher e aplicar conforme sobrar tempo)

- [x] **Roteador LLM mais conservador** — feito no fix do incidente: `route()`
      só roda pra ≥ 2 palavras e ≥ 6 chars. + trava de segurança (`_guard_command`)
      que pausa a escuta em loop de comandos. Ver `AUTONOMOUS_LOG.md` (topo).
- [x] **Temas de cor do holograma** (`[app] theme`: cyan/ice/amber/green/violet)
      — `hologram.js applyTheme()` + dropdown no painel. Commit `feat(Onda I)`.
- [ ] **`_patch_toml_line` por seção** — hoje casa a chave só pelo nome; `enabled`
      aparece em `[arrival]`/`[app]`/`[safety]`. Passar a seção junto.
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
