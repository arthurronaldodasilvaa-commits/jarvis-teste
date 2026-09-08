# Jarvis Voz

Assistente de voz local (roda sobre o OpenJarvis). **Escuta contínua.**

## Ativar (rotina de chegada)

Fale (com ou sem 2 palmas antes):

> **"bom dia neném o papai chegou"**

→ *"Bom dia, senhor. Com o que posso te ajudar?"* + abre **Steam** + toca **Highway to Hell**.

## Falar com o Jarvis

Só age se a fala **começar com "jarvis"**. Fora isso, silêncio.

- **"jarvis"** (sozinho) → *"Olá senhor, com o que posso ajudar?"* (não roda a rotina de chegada)
- **"jarvis, \<comando ou pergunta\>"** → executa / responde. Ele te trata sempre por **Senhor**.

### Comandos

| Fala | Ação |
|---|---|
| "jarvis, abrir \<app\>" | Steam, Spotify, YouTube, Gmail, calculadora, configurações… (+ qualquer atalho do Menu Iniciar) |
| "jarvis, jogar \<jogo\>" / "abrir \<jogo\>" | abre o jogo da **Steam** pelo nome (Palworld, Hollow Knight, Spider-Man…) |
| "jarvis, pesquisar no google \<termo\>" | busca no Google |
| "jarvis, tocar \<música\>" | abre a busca no Spotify |
| "jarvis, escrever um texto sobre \<assunto\>" | a IA redige e joga no Bloco de Notas |
| "jarvis, digitar \<texto\>" | digita o texto no campo que estiver em foco |
| "jarvis, anota \<algo\>" | salva em `NOTAS.md` |
| "jarvis, aumenta/abaixa o volume", "muta" | teclas de mídia |
| "jarvis, próxima música", "pausa", "toca" | controle de mídia |
| "jarvis, bloqueia a tela" | trava o Windows |
| "jarvis, que horas são" / "que dia é hoje" | responde na hora |
| "jarvis, \<qualquer pergunta\>" | responde pela IA local |
| "jarvis, pedido: \<melhoria\>" | anota um pedido de mudança no próprio Jarvis em `PEDIDOS.md` |

### Ações que pedem confirmação falada ("sim" / "confirma" / "pode")

| Fala | Ação |
|---|---|
| "jarvis, desligar o computador" | `shutdown` com 30 s de margem |
| "jarvis, reiniciar" | reinicia |
| "jarvis, suspender" | suspende |
| "jarvis, fechar \<app\>" | encerra o programa |

Para abortar um desligamento em andamento: **"jarvis, cancelar"**.
"jarvis, fecha isso" fecha a janela em foco (Alt+F4) **sem** confirmação.

## Arquivos

| Arquivo | |
|---|---|
| `config.toml` | tudo que você ajusta |
| `jarvis_voice.py` | loop principal (mic, voz, ativação, confirmação) |
| `skills.py` | os comandos / habilidades |
| `common.py` | utilitários (teclado, clipboard) |
| `run_jarvis_voice.vbs` | inicia sem janela |
| `test_audio.py` | diagnósticos |
| `NOTAS.md` / `PEDIDOS.md` | criados pelo Jarvis |

Versionado com **git** — qualquer mudança é reversível (`git log`, `git revert`).

## Segurança

- Toda ação exige o prefixo **"jarvis"**.
- Desligar / reiniciar / suspender / fechar app → **confirmação falada**.
- `[danger]` no `config.toml` desliga cada categoria (`allow_shutdown = false` etc.).
- O modelo local (`qwen3.5:2b`) não executa shell nem código — as ações são um conjunto fixo e revisado neste `skills.py`.

## Rodar

```bat
E:\OpenJarvis\src\.venv\Scripts\python.exe E:\OpenJarvis\voice\jarvis_voice.py
```
ou 2 cliques em `run_jarvis_voice.vbs`. Início com o Windows: `Win+R` → `shell:startup` → atalho pro `.vbs`.

## Testes

```bat
set PY=E:\OpenJarvis\src\.venv\Scripts\python.exe
%PY% E:\OpenJarvis\voice\test_audio.py index                     REM  lista jogos + atalhos achados
%PY% E:\OpenJarvis\voice\test_audio.py skill "jogar palworld"    REM  testa o roteador de comando
%PY% E:\OpenJarvis\voice\test_audio.py voice
%PY% E:\OpenJarvis\voice\test_audio.py whisper
%PY% E:\OpenJarvis\voice\test_audio.py meter
```

## Ajustes rápidos (`config.toml`)

| Sintoma | Ajuste |
|---|---|
| Não entende a frase de chegada | baixe `[arrival] match_threshold` p/ `0.6` |
| Dispara chegada sem querer | suba `match_threshold` p/ `0.8` |
| Lento pra responder | `[wake] whisper_model = "base"` |
| Corta o início da fala | `[audio] speech_level = 0.012`, `pre_roll_seconds = 0.9` |
| Não quero que desligue por voz | `[danger] allow_shutdown = false` |
| Trocar música de chegada | `[arrival] sequence` → outro `spotify:track:ID` |
| Adicionar app fixo | seção `[apps]` |

## Limitações

- Whisper + IA na CPU → "jarvis, pergunta" leva ~6–8 s.
- "tocar \<música\>" abre a busca no Spotify, não dá play sozinho (limite do Spotify sem API).
- `qwen3.5:2b` é um modelo pequeno — respostas curtas e às vezes imprecisas.
- Detecção de palma é heurística.
