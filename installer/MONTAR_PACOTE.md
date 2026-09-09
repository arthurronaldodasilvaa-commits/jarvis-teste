# Mandar o Jarvis pro seu pai — o que VOCÊ (Arthur) precisa fazer

## Resumo em 1 parágrafo

Já existe uma pasta pronta em **`installer/pacote/Jarvis/`** (~950 MB). Ela
tem tudo: o Jarvis, o aplicativo, os modelos de voz e o instalador. Você só
precisa **subir essa pasta no Google Drive**, **pegar o link** e **mandar pro
seu pai**. Ele baixa, extrai e clica em `JarvisSetup.exe`. O instalador faz o
resto sozinho, com uma tela por vez.

---

## O que já está feito (eu fiz)

- [x] Congelei o Jarvis num `.exe` que roda **sem Python instalado**
      (`payload/voice/JarvisVoice.exe` — testado, sobe voz + LLM)
- [x] Incluí o aplicativo holográfico (`payload/jarvis-app/JarvisApp.exe`)
- [x] Baixei e empacotei os modelos de voz (`payload/models/`, ~540 MB)
- [x] Piper TTS (voz neural pt-BR, `voice/piper/` ~98 MB) — vai dentro do
  `_internal/` do `JarvisVoice.exe` quando `build_voice.bat` roda
- [x] Gerei o instalador com janela (`JarvisSetup.exe`)
- [x] Deixei o perfil **robson** como padrão no pacote
- [x] Montei a pasta final em `installer/pacote/Jarvis/`

## O que falta — 3 passos, todos SEUS

### 1. Subir no Google Drive

1. Abra o Drive no navegador.
2. Arraste a pasta **`E:\OpenJarvis\installer\pacote\Jarvis`** inteira pra
   dentro do Drive. (São ~950 MB, leva alguns minutos.)
3. Espere terminar de subir (100%).

### 2. Compartilhar

1. Botão direito na pasta `Jarvis` no Drive → **Compartilhar** → **Compartilhar**.
2. Em "Acesso geral", troque pra **"Qualquer pessoa com o link"**.
3. **Copiar link**.

### 3. Mandar pro seu pai

Manda essa mensagem junto com o link:

> Pai, clica no link. Vai abrir uma pasta no Google Drive. No topo tem um
> botão **Baixar** — clica nele, ele vai baixar um arquivo `.zip`.
> Quando terminar, acha o arquivo (fica em Downloads), clica com o botão
> direito → **Extrair tudo** → **Extrair**.
> Abre a pasta que apareceu, entra em `Jarvis`, e dá dois cliques em
> **`JarvisSetup.exe`**.
> Se o Windows mostrar uma tela azul dizendo "protegeu o seu PC", clica em
> **Mais informações** e depois em **Executar assim mesmo** — é seguro.
> Daí é só ir clicando em **Avançar**.

---

## Como ele escolhe o perfil (robson / arthur)

- **Durante a instalação:** tem uma tela "Quem vai usar o Jarvis" — já vem
  com **Robson** marcado. Ele só clica em Avançar.
- **Depois, por voz, a qualquer momento:**
  - "Jarvis, qual perfil está ativo?"
  - "Jarvis, muda para o perfil arthur"  (ou "robson")
  - O Jarvis grava e **reinicia sozinho** já no perfil novo (~5 segundos).

Pra criar um perfil de outra pessoa: copie `voice/profiles/robson.toml`,
renomeie (ex: `maria.toml`), ajuste o nome/persona lá dentro, e rode o
`build_package.bat` de novo — ela vai aparecer na lista da instalação.

---

## Teste antes de mandar (recomendado, 10 min)

Rode `installer\pacote\Jarvis\JarvisSetup.exe` você mesmo:

1. Escolha um disco com espaço (pode ser o mesmo, ele instala em `X:\Jarvis`).
2. Vá até o fim.
3. No passo do Ollama: se você já tem o Ollama, ele detecta e só baixa o
   modelo. Se não, clica em "Instalar o Ollama" (abre o download), instala,
   volta e clica em "Já instalei / verificar".
4. Confirma que no fim o Jarvis abre e responde a "Jarvis, que horas são".
5. Pra desinstalar o teste: apague a pasta `X:\Jarvis` e os atalhos "Jarvis"
   (área de trabalho, menu Iniciar, e `shell:startup`).

## Regerar o pacote (se mudar algo no código)

Na pasta `installer/`:

```
build_voice.bat          REM  o daemon de voz  (~2 min)
..\jarvis-app\build.bat  REM  o aplicativo
build_setup.bat          REM  o instalador
build_package.bat        REM  junta tudo em pacote\Jarvis\
```

(Se `build_package.bat` não rodar direto, os passos manuais estão no
histórico do git, commit do instalador.)

## Sobre o Ollama (1,5 GB)

Não vai no pacote — seria grande demais. O instalador abre o download
oficial no navegador e guia seu pai a instalar (2 cliques: baixar → Install).
Se quiser embutir mesmo assim: baixe
<https://ollama.com/download/OllamaSetup.exe> e salve em
`installer\pacote\Jarvis\payload\ollama\OllamaSetup.exe` antes de subir.
