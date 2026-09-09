# Jarvis

Assistente pessoal por voz + "cérebro" holográfico, rodando 100% local no PC do Arthur.

| Parte | Pasta | O que é |
|---|---|---|
| **Voz** | [`voice/`](voice/README.md) | daemon que ouve o mic, entende comandos e responde falando |
| **App** | [`jarvis-app/`](jarvis-app/README.md) | janela com o holograma azul que pulsa quando o Jarvis fala |
| **Arquitetura** | [`ARCHITECTURE.md`](ARCHITECTURE.md) | como as duas partes conversam, fluxo, pontos de extensão |

Infra local (fora do git): `src/` (OpenJarvis + venv), `hf-cache/` (Whisper), `ollama-models/` (qwen3.5:2b).

## Começar

```bat
REM assistente de voz (também sobe sozinho no logon)
E:\OpenJarvis\src\.venv\Scripts\python.exe E:\OpenJarvis\voice\jarvis_voice.py

REM app holográfico
E:\OpenJarvis\jarvis-app\dist\JarvisApp.exe
```

Pausar tudo: **Ctrl+Alt+J**, botão no app, ou "jarvis, modo cinema".

## Histórico

Repositório unificado a partir de dois repos separados (`voice` + `jarvis-app`).
O histórico completo de ambos está preservado no `git log` e também em
`_archive/*.bundle` (recuperável com `git clone _archive/voice-history.bundle`).
