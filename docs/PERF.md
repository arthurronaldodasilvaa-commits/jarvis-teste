# Jarvis — notas de performance

Máquina alvo: 16 GB RAM (~4 livres), GTX 1650 4 GB, sem nuvem.

## Caminho ouvir → responder

```
mic (sounddevice) → VAD de energia → Whisper tiny (estágio 1, "é pra mim?")
  → [só se passar] Whisper small (estágio 2) → skills.dispatch (regex + roteador)
  → [se cair no LLM] ollama qwen3.5:2b → Piper TTS
```

Custos típicos (CPU): estágio 1 ~150–300 ms · estágio 2 ~400–900 ms ·
dispatch < 5 ms · LLM 1–3 s · Piper ~400–900 ms (sobe o modelo a cada fala).

## Já otimizado

- **Whisper `small` sob demanda** (`Ears.cmd` é property lazy + thread de
  prewarm 6 s pós-boot). Corta ~2–3 s do arranque.
- **2 estágios de STT** — o modelo bom só roda quando o tiny viu "jarvis".
  Economiza MUITA CPU quando ninguém está falando com ele.
- **`norm()` cacheado** (`lru_cache` 2048) — está no caminho quente do dispatch.
- **`_atomic_write`** — o app lê `state.json` 4×/s sem pegar arquivo pela metade.
- **HUD**: `_media_snapshot` fecha o event loop do asyncio (vazava 1/2 s);
  `renderFeed` reconcilia por chave (não repinta a cada poll).
- **App/câmera**: MediaPipe Hands roda 1 a cada 3 frames quando não há mão há
  > 2 s (`handtrack.feed` downshift); face-api a cada 1,4 s; OCR sob demanda.
- **LLM keep-warm** a cada 10 min.

## Ainda dá pra fazer (não feito — risco vs. ganho)

- **Piper em processo vivo** (`--json-input` streaming) em vez de spawnar a cada
  fala. Ganho ~300–500 ms/fala. Risco: reescrever o `Mouth._piper_say`; deixar
  pra quando dá pra testar ao vivo.
- **Whisper na GPU** (`whisper_device = "cuda"`) — precisa das libs CUDA/cuDNN.
  A GTX 1650 daria pra rodar o `small` bem mais rápido.
- Quebrar `skills.py` (1700+ linhas) em módulos por área. Hoje a ORDEM do
  dispatch é a lógica — mexer sem teste ao vivo é arriscado.
