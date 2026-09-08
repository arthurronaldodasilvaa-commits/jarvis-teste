# Jarvis Voz

Assistente de voz local sobre o OpenJarvis. **Escuta contínua** — não precisa de terminal aberto nem de apertar nada.

## Como usar

### Ativar (rotina de chegada)
Fale (com ou sem bater 2 palmas antes):

> **"bom dia neném o papai chegou"**

Ele responde *"Bom dia, senhor. Com o que posso te ajudar?"*, **abre a Steam** e **toca *Highway to Hell* no Spotify**.

Bater **2 palmas** também ativa na hora (atalho).

### Comandos e perguntas
Só responde se a fala **começar com "jarvis"**. Qualquer outra fala é ignorada em silêncio.

| Você fala | Ele faz |
|---|---|
| "jarvis, abrir steam / spotify / youtube / calculadora / gmail / whatsapp / explorador" | abre o app/site |
| "jarvis, pesquisar no google \<termo\>" | abre a busca no Google |
| "jarvis, tocar \<música\>" | abre a busca no Spotify |
| "jarvis, \<qualquer pergunta\>" | responde pela IA local (te tratando por **Senhor**) |
| "jarvis" (sozinho) | *"Pois não, senhor?"* |
| "jarvis, pode ir / obrigado / para" | *"Às ordens, senhor."* |

Ele te chama **sempre de "Senhor"**. Sabe que seu nome é **Arthur** (se você perguntar, ele diz — mas continua te chamando de Senhor).

## Arquivos

| Arquivo | Função |
|---|---|
| `config.toml` | **tudo que você ajusta** |
| `jarvis_voice.py` | o programa |
| `run_jarvis_voice.vbs` | inicia sem janela |
| `test_audio.py` | diagnósticos |
| `jarvis_voice.log` | histórico |

## Rodar

```bat
E:\OpenJarvis\src\.venv\Scripts\python.exe E:\OpenJarvis\voice\jarvis_voice.py
```
ou 2 cliques em `run_jarvis_voice.vbs` (roda escondido; feche pelo Gerenciador de Tarefas → `pythonw.exe`).

### Iniciar com o Windows
`Win+R` → `shell:startup` → cole um **atalho** para `run_jarvis_voice.vbs`.

## Testes

```bat
cd /d E:\OpenJarvis\voice
set PY=E:\OpenJarvis\src\.venv\Scripts\python.exe

%PY% test_audio.py voice            REM  a voz do Windows fala
%PY% test_audio.py llm              REM  testa as respostas da IA
%PY% test_audio.py meter            REM  volume do mic (fale / bata palma e veja a barra)
%PY% test_audio.py whisper          REM  fale 5s -> mostra o que ele entendeu
%PY% test_audio.py wake "bom dia nenei o papai chegou"   REM  testa se um texto ativaria
%PY% test_audio.py actions          REM  dispara Steam + Spotify
```

## Ajustes no `config.toml`

| Sintoma | Ajuste |
|---|---|
| Não entende a frase de ativação | já está bem tolerante; se ainda falhar, baixe `[wake] match_threshold` para `0.45` |
| Ativa sozinho | suba `match_threshold` para `0.65` |
| Demora pra responder | `[wake] whisper_model = "base"` (mais rápido, menos preciso) |
| Não te ouve / corta o começo da fala | baixe `[audio] speech_level` (ex: `0.012`) e suba `pre_roll_seconds` (ex: `0.8`) |
| Palmas não pegam | baixe `clap_sensitivity` (ex: `5.0`) e `clap_min_level` (ex: `0.02`) |
| Palmas disparam sozinhas | suba os dois; ou `clap_enabled = false` |
| Ele se ouve falando e reage | use fone, ou baixe o volume da caixa |
| Trocar a voz / velocidade | `[tts] sapi_voice` / `sapi_rate` |
| Mudar a música de chegada | `[arrival] sequence` — troque o `spotify:track:ID` |
| Mudar como ele te chama / seu nome | `[assistant] address` / `user_name` |

## Limitações

- **Whisper + LLM rodam na CPU** → "jarvis, pergunta" leva ~6–8 s. A GTX 1650 tem só 4 GB; dá pra tentar `whisper_device = "cuda"` mas pode precisar de libs CUDA extras.
- **"tocar \<música\>"** abre a *busca* no Spotify, não dá play sozinho (o Spotify não permite isso sem login de API). A música de chegada funciona 100% porque é uma faixa fixa.
- Detecção de palma é heurística.
- O modelo local (`qwen3.5:2b`) é pequeno — respostas curtas e às vezes imprecisas. É o que cabe nos 16 GB de RAM / GPU de 4 GB.
