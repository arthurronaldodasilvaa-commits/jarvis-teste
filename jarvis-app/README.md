# Jarvis App — cérebro holográfico

Janela de fundo preto com um "cérebro" em holograma azul neon (estilo Homem de Ferro)
que gira sozinho e **pulsa / dá zoom quando o Jarvis fala**.

Independente do assistente de voz: abre e fecha por conta própria. O Jarvis
funciona com ou sem ele, e vice-versa.

## Rodar

- **Executável:** `dist\JarvisApp.exe` (14 MB, arquivo único, sem dependências)
- **Dev:** `.venv\Scripts\python.exe app.py`  (ou `app.py --dev` com DevTools)

Instância única: abrir de novo só traz a janela pra frente.

### Teclas
| Tecla | |
|---|---|
| `S` | liga/desliga o modo "falando" (demo do pulso) |
| `espaço` | um pulso rápido |
| `Esc` ou `×` | fecha |
| arrastar | move a janela (sem moldura) |

## Como o Jarvis conversa com ele

O `jarvis_voice.py` escreve `state.json` nesta pasta:

```json
{ "speaking": true, "amplitude": 0.4, "status": "FALANDO" }
```

O app lê esse arquivo ~5×/s (via `Api.get_state`) e reage:
- `speaking: true` → cérebro brilha, pulsa, câmera dá zoom in/out
- `status` → texto no canto inferior ("OUVINDO", "FALANDO"…)
- `amplitude` (0–1) → intensidade do pulso (reservado p/ o nível de voz real)

No `config.toml` do voice, seção `[app]`:
```toml
enabled = true
exe_path = "E:\\OpenJarvis\\jarvis-app\\dist\\JarvisApp.exe"
open_on_arrival = true       # abre por último na rotina "bom dia..."
open_on_wake_word = true     # abre ao dizer só "jarvis"
```

## Estrutura

| | |
|---|---|
| `app.py` | janela pywebview (frameless, preta) + ponte JS↔Python |
| `ui/index.html` | HUD (marca, status, vinheta, scanlines) |
| `ui/hologram.js` | cena Three.js: núcleo, cascas, anéis, partículas, animação |
| `ui/lib/three.min.js` | Three.js r128 (local, sem CDN) |
| `build.bat` | gera `dist\JarvisApp.exe` (PyInstaller) |
| `state.json` | escrito pelo assistente de voz (ignorado pelo git) |

## Reconstruir o .exe

```bat
build.bat
```

## Roadmap

- [x] v0: holograma girando + pulso ao falar (via `state.json`)
- [ ] nível de voz real → `amplitude` (o cérebro "fala" junto)
- [ ] estados visuais: pensando / pesquisando / erro
- [ ] leitura por webcam (gestos de mão) → comandos
