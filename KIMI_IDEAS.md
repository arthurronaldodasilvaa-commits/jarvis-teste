# Jarvis 2.0 — ideias tiradas do Kimi CLI

Fonte: <https://github.com/MoonshotAI/kimi-cli> (agente de terminal da Moonshot AI,
open-source). É um "primo" do Claude Code: agente que lê/edita código, roda shell,
busca na web, planeja sozinho. **O domínio é outro** (ele é dev tool, o Jarvis é
assistente de voz + estudo holográfico), mas a **arquitetura dele resolve
problemas que o Jarvis também tem**. Este documento separa o que vale copiar,
ranqueado por impacto × risco.

Data: 2026-09-09.

---

## O que o Kimi tem de bom (e que o Jarvis não tem)

| Peça do Kimi | O que é | Vale pro Jarvis? |
|---|---|---|
| **Agent spec em YAML** | tools, subagentes e prompt do agente são **dados**, não código | ✅ muito — hoje `skills.py` tem 1200 linhas de regex |
| **Subagentes** (`coder`, `explore`, `plan`) | "modos" especializados com prompt e permissões próprias | ✅ vira "modo Enem", "modo redação", "modo prova" |
| **Hooks** (13 eventos de ciclo de vida) | `PreToolUse`, `SessionStart`, `Notification`… rodam um comando shell com contexto JSON no stdin; exit code controla o fluxo | ✅✅ capacita o não-programador a automatizar |
| **MCP client** | fala Model Context Protocol → pluga em QUALQUER servidor MCP (arquivos, browser, casa inteligente…) sem código | ✅✅✅ é o "evoluir absurdamente" — mas depende de LLM maior |
| **kosong** | camada de abstração de LLM (Kimi / Anthropic / Gemini) — troca de provedor sem mexer no agente | ✅ Jarvis hoje é 100% preso no Ollama |
| **Approval runtime** | camada de política: o que precisa de confirmação, o que é bloqueado | ✅ generaliza o "diga sim" do desligamento |
| **Background task manager** | `TaskList` / `TaskOutput` / `TaskStop` como ferramentas | ✅ unifica os threads soltos (lembrete, HUD, scan) + tarefas-watch |
| **Custom tools** | `module:Classe` no spec, Pydantic pros parâmetros | ✅ é assim que uma skill nova entra sem editar o core |
| **ACP server** (`kimi acp`) | vira servidor pra Zed / JetBrains dirigirem | ❌ não serve pro caso do Jarvis |
| **Shell mode** (`Ctrl-X`) | alterna pra shell sem sair do app | ⚠️ perigoso num assistente sempre-ouvindo; talvez "modo terminal" opt-in |
| **Streaming JSON / wire messages** | IPC estruturado | ✅ substitui o polling de `state.json` a cada 250 ms |

---

## Plano — 3 ondas

### 🌊 Onda 1 — fundação (baixo risco, alto ganho, dá pra fazer já)

#### 1A. Catálogo de skills declarativo  `voice/skills/*.toml`
Hoje toda skill é um `if re.search(...)` no meio de um arquivo gigante. Vira:

```toml
[clima]
patterns = ["como (está|ta) o tempo", "vai chover", "temperatura em (?P<cidade>.+)"]
router_hint = "clima / tempo / previsão / chuva"
handler = "weather:report"
confirm = false
examples = ["tá calor lá fora?", "vai chover amanhã em Recife?"]
```

- Handlers continuam em Python (pros casos complexos), mas o **matching, o
  roteador e a doc viram dados**.
- O `_ROUTER_PROMPT` passa a ser **gerado** do catálogo (nunca mais desatualiza).
- `COMANDOS.md` passa a ser **gerado** do catálogo.
- Robson/Arthur adicionam comando editando um `.toml` — zero Python.
- Ganho imediato: testes triviais, sem regressão silenciosa.

**Esforço:** médio (2–3 h). **Risco:** baixo (migração incremental, skill a skill).

#### 1B. Sistema de hooks  `voice/hooks.toml`
Eventos do Jarvis: `on_startup`, `on_wake`, `on_command`, `on_command_done`,
`on_error`, `on_idle`, `on_reminder_due`, `on_profile_switch`, `on_shutdown`.

```toml
[[hooks]]
event = "on_wake"
when = "06:00-09:00"          # opcional
speak = "Bom dia, senhor. Deixa eu te passar o resumo."
then = "briefing"             # dispara uma skill

[[hooks]]
event = "on_idle"
after_seconds = 1800
run = "nircmd.exe monitor off" # ou um comando shell

[[hooks]]
event = "on_error"
speak = "Tive um problema aqui, senhor. Já anotei no log."
```

Isso é o que transforma o Jarvis de "responde comando" pra "tem
comportamento". Um não-programador liga rotinas editando um arquivo.

**Esforço:** médio (2 h). **Risco:** baixo (fail-open — hook que quebra não
derruba o Jarvis).

#### 1C. Abstração de LLM  `voice/brain/` (estilo kosong)
`Brain` vira interface; implementações: `OllamaBrain` (atual), `OpenAICompatBrain`
(LM Studio / llama.cpp / vLLM / OpenRouter), `AnthropicBrain`.

```toml
[assistant]
provider = "ollama"           # ollama | openai_compat | anthropic
model = "qwen2.5:3b"
fallback_provider = "openai_compat"   # se o local não responder em N s
```

Mantém o "tudo local por padrão", mas dá a alavanca: pergunta difícil de
física/química → estoura pro modelo grande; resto → local.

**Esforço:** médio (2–3 h). **Risco:** baixo.

---

### 🌊 Onda 2 — capacidade (médio risco, ganho grande)

#### 2A. Cliente MCP  `voice/mcp.toml`  ← a jóia da coroa
O Jarvis ganha uma camada genérica de ferramentas. Quando o roteador não casa
nenhuma skill, ele pode chamar uma **tool MCP**:

```toml
[[mcp]]
name = "arquivos"
transport = "stdio"
command = "npx -y @modelcontextprotocol/server-filesystem E:\\Estudos"

[[mcp]]
name = "casa"
transport = "http"
url = "http://192.168.0.50:8080/mcp"
```

De repente o Jarvis controla casa inteligente, sistema de arquivos, calendário,
navegador, Home Assistant, Notion… **sem uma linha de integração**. É
literalmente "evoluir absurdamente".

**O bloqueio honesto:** o `qwen 2b` é fraco demais pra decidir tool-calls em JSON
de forma confiável. Precisa de:
- roteador num modelo maior (qwen 7b / 14b — precisa de RAM/GPU), **ou**
- roteador num modelo cloud pequeno e barato só pra classificar (quebra o
  "100% local", mas só o *roteamento* sai, não o conteúdo).

**Esforço:** alto (1–2 dias). **Risco:** médio. **Recomendo fazer depois da Onda 1
e junto com 1C (provider grande).**

#### 2B. Gerenciador de tarefas em background
Unifica os threads soltos num registro só, com status falável:
- "Jarvis, o que você tá fazendo?" → lista tarefas ativas
- "me avisa quando a pasta Downloads parar de crescer" → cria uma watch-task
- "cancela o monitoramento" → `TaskStop`

**Esforço:** médio. **Risco:** baixo-médio.

#### 2C. Camada de política  `voice/policy.toml`
Generaliza o "diga sim" pra uma tabela:

```toml
[desligar]      ; confirm + cooldown
confirm = true
cooldown_seconds = 30
[bloquear_tela]
confirm = true         ; <- conserta o acidente da tela travada de vez
[tocar_musica]
rate_limit = "3/min"
```

**Esforço:** baixo. **Risco:** baixo. **Bônus:** fecha o buraco que travou a tela.

---

### 🌊 Onda 3 — arquitetura (fazer quando o resto estabilizar)

- **3A. IPC por evento** — troca o polling de `state.json`/`control.json` (4×/s em
  disco) por um named pipe / websocket local com mensagens JSON. Menos latência,
  menos I/O, dá pra ter push ("holograma pronto") em vez de poll.
- **3B. Subagentes / modos de estudo** — `agents/enem.yaml`, `agents/redacao.yaml`:
  cada um com prompt, conjunto de skills e comportamento de HUD próprios.
  "Jarvis, modo Enem" = carrega uma configuração inteira.
- **3C. "Souls" plugáveis** — o loop do agente (ouvir→rotear→agir→falar) vira
  plugável, pra dar pra ter um loop "tutor" (que puxa assunto, faz perguntas
  sozinho) diferente do loop "assistente" (reativo).

---

## Recomendação

1. **Agora:** Onda 1 inteira (1A + 1B + 1C). É fundação, baixo risco, e o Jarvis
   já fica muito mais capaz e editável por não-programador.
2. **Depois que o protótipo do Robson voltar com feedback:** Onda 2 (MCP + provider
   grande + política). Aí sim o "evoluir absurdamente".
3. **Onda 3** é refactor de infra — só quando não tiver nada mais urgente.

O que **não** copiar do Kimi: ACP server, shell mode sempre-ligado (perigo num
assistente de voz), e a dependência de um LLM grande pra *tudo* (o Jarvis tem que
continuar útil offline com o modelo pequeno).

---

## Status de implementação

- [ ] 1A — catálogo de skills declarativo
- [ ] 1B — sistema de hooks
- [ ] 1C — abstração de LLM (provider)
- [ ] 2A — cliente MCP
- [ ] 2B — task manager em background
- [ ] 2C — camada de política (+ conserta bloquear_tela)
- [ ] 3A — IPC por evento
- [ ] 3B — subagentes / modos de estudo
- [ ] 3C — souls plugáveis
