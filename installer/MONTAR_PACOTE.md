# Montar o pacote do Jarvis (para o Arthur)

Objetivo: gerar uma pasta que o seu pai baixa do Google Drive e instala
com dois cliques, sem terminal, sem sua ajuda.

O resultado é uma pasta assim:

```
Jarvis/
  JarvisSetup.exe            <- ele clica aqui
  LEIA-ME.txt
  payload/
    voice/      JarvisVoice.exe + _internal/ + config.toml + profiles/
    jarvis-app/ JarvisApp.exe
    models/     faster-whisper-tiny/ , faster-whisper-small/
    ollama/     OllamaSetup.exe
```

---

## Pré-requisitos (uma vez)

- Python + `uv` já instalados (você já tem).
- Dependências de build no venv de voz:
  ```
  uv pip install --python ..\src\.venv\Scripts\python.exe pyinstaller huggingface_hub
  ```
- Baixe o instalador do Ollama e salve **nesta pasta** (`installer/`) como
  `OllamaSetup.exe`:
  <https://ollama.com/download/OllamaSetup.exe>
  (Se não fizer isso, o instalador manda o usuário baixar do site — funciona,
  mas é um passo a mais pra ele.)

## Antes de gerar: escolha o perfil

Edite `..\voice\config.toml` e deixe:

```toml
[profile]
active = "robson"
```

Assim o Jarvis instalado já trata seu pai pelo perfil dele (persona de
secretário executivo, conhecimento do Instituto CAM, sem a frase de chegada).
Para outro cliente, crie `..\voice\profiles\<nome>.toml` e ponha o nome dele aqui.

## Gerar (na pasta `installer/`)

```
build_voice.bat            REM  -> dist\JarvisVoice\      (~1 min, pesado)
..\jarvis-app\build.bat    REM  -> ..\jarvis-app\dist\JarvisApp.exe
build_setup.bat            REM  -> dist\JarvisSetup.exe
build_package.bat          REM  -> pacote\Jarvis\   (junta tudo)
```

`build_package.bat` também roda `prep_models.py`, que baixa os modelos de voz
(~500 MB no total) e coloca cópias limpas em `payload/models/`.

## Subir pro Drive

1. Suba a pasta **`pacote\Jarvis`** inteira pro Google Drive (arrastar e soltar).
   São ~1,5–2 GB. Deixe como uma pasta só chamada `Jarvis`.
2. Botão direito na pasta → **Compartilhar** → gere o link ("qualquer pessoa
   com o link pode ver").
3. Mande pro seu pai:
   > "Pai, abre esse link, clica em **Baixar** (vai baixar um .zip),
   > extrai, entra na pasta e clica em **JarvisSetup.exe**. Depois é só ir
   > clicando em Avançar."

O Google Drive baixa a pasta como um `.zip` automaticamente. Ele extrai
(botão direito → Extrair tudo) e roda o `JarvisSetup.exe` de dentro.

## Teste antes de mandar

Rode `pacote\Jarvis\JarvisSetup.exe` você mesmo, num disco de teste, e vá até
o fim. Confirme que:

- copiou pra `X:\Jarvis\`
- o Ollama instala e o modelo baixa
- o teste de microfone mostra barra verde
- a amostra de voz toca
- no fim, o Jarvis abre e responde a "Jarvis, que horas são"

## Atualizar depois

Regere só o que mudou (`build_voice.bat` se mexeu no código de voz, etc.),
rode `build_package.bat` de novo, e substitua a pasta no Drive. O instalador
por cima reinstala limpo.
