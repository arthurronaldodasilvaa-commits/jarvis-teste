# Jarvis — deploy, empacotamento e itens bloqueados

## Rodar em desenvolvimento

- **Daemon de voz:** `wscript voice/run_jarvis_voice.vbs` (roda oculto) ou
  `python voice/jarvis_voice.py`. Trava de instância única (mutex
  `Global\JarvisVozSingleton`).
  > A venv do `uv` usa um *trampolim* — no Gerenciador de Tarefas aparecem
  > `pythonw.exe` (fino, o trampolim) **e** `pythonw3.11.exe` (o interpretador
  > real). É **um** daemon só.
- **App do cérebro:** `python jarvis-app/app.py` (fonte) ou
  `jarvis-app/dist/JarvisApp.exe` (congelado).
- **Tudo junto:** `start.bat`.

## Recompilar os executáveis congelados

- Daemon: `installer/JarvisVoice.spec` (PyInstaller). Tem `hiddenimports` pros
  módulos carregados tarde (`facts`, `materials`, `study`, `aula`, `invent`,
  `teach`, `tasks`, `read_aloud`, `face`, `hooks`, `llm`, `skills_extra`).
- App: `jarvis-app/build.bat` (`--add-data "ui;ui"`).
- Pacote do instalador: `installer/` → gera `installer/pacote/Jarvis/`.

## Trocar o modelo de linguagem (quando tiver RAM/GPU ou nuvem)

`voice/llm.py` já abstrai o provedor. No `config.toml [assistant]`:

```toml
provider = "ollama"          # ollama | openai | anthropic
model = "qwen3.5:2b"         # troque por um maior: qwen2.5:7b, llama3.1:8b…
# fallback_provider = "openai"
# openai_url = "https://api.openai.com/v1"
# openai_model = "gpt-4o-mini"
# openai_key = "sk-..."       # ou em secrets.toml (fora do git)
```

`fallback_provider` entra quando o primário falha/demora. Um modelo local maior
que 2B **trava** a máquina atual (16 GB RAM, GTX 1650 4 GB) — testado com phi3.5
(30–86 s por resposta) e removido.

## Itens BLOQUEADOS (precisam de algo que não temos)

| Item | Motivo | O que fazer |
|---|---|---|
| Assinar `JarvisSetup.exe` | Certificado de code-signing é **pago** + verificação de identidade (EV ~US$300/ano). | Comprar o cert (DigiCert/Sectigo), rodar `signtool sign /fd sha256 /tr <timestamp> /td sha256 /a JarvisSetup.exe`. Sem isso, o SmartScreen avisa "editor desconhecido". |
| Temperatura da **CPU** no HUD | `psutil.sensors_temperatures` não existe no Windows; WMI `MSAcpi_ThermalZoneTemperature` exige **admin**. | Rodar o daemon como admin, ou embutir `LibreHardwareMonitorLib.dll` (não precisa de admin em alguns chipsets). GPU já funciona (NVML). |
| LLM local maior | RAM/GPU. | Ver seção acima. A camada de troca já está pronta. |
