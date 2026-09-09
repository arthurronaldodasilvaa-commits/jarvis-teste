# Jarvis — arquitetura

Dois programas independentes que conversam por **2 arquivos JSON** numa pasta compartilhada.

```
E:\OpenJarvis\
├─ voice\            ← assistente de voz (daemon Python, sempre rodando)
│  ├─ jarvis_voice.py   loop: mic → Whisper → intenção → ação/voz
│  ├─ skills.py         o que ele sabe fazer (abrir, escrever, sistema, ...)
│  ├─ common.py         utilitários (teclado, clipboard, arquivos compartilhados)
│  ├─ config.toml       TUDO que se ajusta
│  └─ test_audio.py     diagnósticos
├─ jarvis-app\       ← "cérebro" holográfico (janela pywebview + Three.js)
│  ├─ app.py            janela + ponte JS↔Python
│  ├─ ui\hologram.js    a cena 3D
│  └─ dist\JarvisApp.exe   build (PyInstaller, ~13 MB, 1 arquivo)
├─ src\              ← OpenJarvis + venv (motor: Ollama/qwen3.5:2b, faster-whisper)
├─ hf-cache\         ← modelos Whisper (tiny + small)
└─ ollama-models\    ← qwen3.5:2b (~2,6 GB)
```

## Fluxo da voz (jarvis_voice.py)

```
mic (16 kHz, blocos de 100 ms)
  → VAD por energia (detecta início/fim de fala)
  → ESTÁGIO 1: Whisper tiny  (rápido, roda em TODA fala)
        contém "jarvis" / frase de chegada / confirmação pendente?
        ├─ não → descarta (barato)
        └─ sim → ESTÁGIO 2: Whisper small (preciso)
                   → is_arrival_phrase?        → rotina de chegada
                   → "jarvis <x>"              → skills.dispatch(x)
                        ├─ regra bate  → executa (abrir, volume, sistema, ...)
                        ├─ ação sensível → confirmação falada ("sim")
                        └─ nada bate   → Brain.ask() (Ollama)
                   → fala a resposta (TTS worker persistente)
```

## Os 2 arquivos de estado (`jarvis-app\`)

| Arquivo | Quem escreve | Quem lê | Conteúdo |
|---|---|---|---|
| `state.json` | daemon | app | `{speaking, amplitude, status}` — o que o Jarvis está fazendo agora |
| `control.json` | app / atalho / voz | daemon + app | `{paused}` — escuta ligada ou não |

O app faz **1 chamada** `get_status()` ~4×/s que devolve os dois juntos.

## Otimizações aplicadas (v4)

| | ganho |
|---|---|
| STT em 2 estágios (tiny filtra, small só quando chamado) | ~4× menos CPU ocioso |
| `keep_alive=1h` + ping a cada 10 min no Ollama | mata o cold start de ~36 s |
| TTS worker PowerShell persistente | ~0,4 s por fala |
| App: 1 IPC no lugar de 2, ~30 fps quando parado | menos CPU/GPU da janela |
| Whisper `beam_size=1`, sem `vad_filter` no estágio 1 | estágio 1 ~350 ms |
| exe com `--exclude-module` (numpy/pandas/tk/...) | 14 → 13 MB |

## Pontos de extensão (para o que vem a seguir)

- **Nível de voz real → `amplitude`**: hoje `state.json.amplitude` é fixo. Ligar no volume
  do áudio que o SAPI produz faz o cérebro "falar junto".
- **Novos estados visuais**: `state.json.status` já é livre — `PENSANDO`, `PESQUISANDO`, `ERRO`…
  basta o `hologram.js` reagir a cada string.
- **Webcam / gestos**: um 3º processo que escreve em `control.json` (ou um novo `vision.json`).
- **Novas skills**: só adicionar um `if re.search(...)` em `skills.py::dispatch` retornando um `Result`.
- **Fila de pedidos por voz**: "jarvis, pedido: ..." grava em `voice\PEDIDOS.md`.

## Rodando

- Voz: autostart no logon (`shell:startup` → `run_jarvis_voice.vbs`). Instância única (mutex).
- App: abre por voz ("jarvis" / "bom dia neném o papai chegou") ou 2 cliques no `.exe`. Instância única.
- Pausar tudo: **Ctrl+Alt+J**, botão no app, ou "jarvis, modo cinema".
