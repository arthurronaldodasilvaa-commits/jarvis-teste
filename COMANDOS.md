# Jarvis — tudo que dá pra pedir

Diga **"Jarvis"** no começo da frase. "Jarvis" sozinho → ele responde e espera.
As mil formas de pedir a mesma coisa funcionam — o Jarvis entende o pedido e
executa o comando certo (roteador por IA).

Para ele **parar de ouvir**: "Jarvis, modo cinema". Para **voltar**: `Ctrl+Alt+J`.

**Trava de segurança:** se algo (TV, conversa ao telefone, a própria música do
Jarvis) fizer ele receber vários comandos parecidos em sequência, ele **pausa a
escuta sozinho** e avisa. Volte com `Ctrl+Alt+J`. Ajuste em `[safety]` no config.

---

## Conversa e conhecimento

| Você diz | O que acontece |
|---|---|
| "quem foi Santos Dumont" / "o que é fotossíntese" | resumo da Wikipédia |
| "o que meu resumo diz sobre a Revolução Francesa" | **responde a partir dos SEUS materiais** (pasta em `[study] materials_dir`), citando o arquivo |
| "resume o que eu tenho sobre X nos meus materiais" · "atualiza meus materiais" | resumo / reindexar |
| "me dá uma aula sobre ondas" | **modo aula**: explica em passos e cria os hologramas; diga "continua" |
| "me faz uma pergunta sobre a 2ª guerra" | quiz por voz — você responde falando, ele corrige |
| "me conta uma piada" / "o que você acha de X" | resposta do modelo local |
| "e a população dela?" | ele lembra o assunto anterior (últimas 3 trocas) |
| "repete" · "esquece" · "fala mais devagar / rápido" | controle da fala |
| "traduz bom dia pra inglês" · "soletra necessário" | tradução / soletração |
| "me dá uma frase motivacional" | citação do dia |
| "o que eu fiz hoje" · "resumo do dia" | diário de bordo — o que o senhor pediu ao Jarvis hoje (lê o log) |
| "como você pode me ajudar" · "como você funciona" · "abre o manual" | abre o **manual completo** (site html) no navegador |

## Ensinar o Jarvis (ele se estende sozinho)

| Você diz | O que acontece |
|---|---|
| "aprende: quando eu disser 'modo foco' você fala 'concentrado' e abre o YouTube" | ele monta o comando, confirma com você e passa a obedecer |
| "esquece o comando modo foco" · "quais comandos você aprendeu" | remove / lista |
| "cria um holograma de um átomo de carbono" · "desenha um esquema de uma alavanca" | ele **inventa** o holograma na hora (esquemático) |

## Tempo, contas, informação

| Você diz | O que acontece |
|---|---|
| "que horas são" · "que horas são em Tóquio" · "que dia é hoje" · "quantos dias faltam pro Natal" | relógio / data / contagem |
| "como está o tempo" · "vai chover amanhã" · "o tempo em Recife" | previsão (Open-Meteo) |
| "quanto é 15% de 240" · "raiz de 144" · "100 dólares em reais" · "quanto tá o bitcoin" | contas / conversão / cripto |
| "quanto tá a ação da Petrobras / Vale / Itaú" · "como tá o Ibovespa" | bolsa B3 |
| "que endereço é o CEP 01001-000" | ViaCEP |
| "quando é o próximo feriado" · "feriados de 2027" | BrasilAPI |
| "como tá a qualidade do ar" · "a que horas o sol nasce" · "qual a fase da lua" | Open-Meteo |
| "o que aconteceu num dia como hoje" | efemérides |
| "resume esse site: <cola a URL>" | baixa e resume |
| "quais as notícias" · "notícias de tecnologia" | manchetes do dia |
| "qual a temperatura da GPU" · "o PC tá quente?" | temperatura da placa (a da CPU o Windows não deixa ler sem admin) |
| "o que tá pesado" | top 3 processos por CPU e por RAM |

## Lembretes, tarefas, notas, memos

| Você diz | O que acontece |
|---|---|
| "me lembra de tirar o bolo em 20 minutos" · "me lembra às 15h" · "me lembra todo dia às 8" | lembrete pontual / horário / **recorrente** |
| "timer de 10 minutos" · "pomodoro de 25 minutos" | cronômetro com contagem no HUD; "cancela o cronômetro" |
| "quais lembretes eu tenho" · "cancela os lembretes" | ver / limpar |
| "adiciona estudar química na lista" · "quais minhas tarefas" · "risca a de química" · "limpa a lista" | lista de tarefas (aparece no HUD) |
| "anota: comprar leite" · "quais minhas notas" | notas em NOTAS.md |
| "grava um memo" | grava até 60s, transcreve e salva em `voice/memos/`; "meus memos" |
| "lê isso" (área de transferência) · "lê esse arquivo E:/…/resumo.txt" · "lê essa página" | narra em voz alta; "para de ler" |

## Música e mídia

| Você diz | O que acontece |
|---|---|
| "toca Bohemian Rhapsody" · "toca uma do Queen" | Spotify |
| "que música é essa" · "do começo" · "adianta 30 segundos" | info / seek |
| "pausa" · "próxima música" · "aumenta o volume" · "muta" | controle |

## Programas e computador

| Você diz | O que acontece |
|---|---|
| "abre o navegador / a steam / o spotify / a calculadora" · "joga <jogo>" | abre |
| "abre o navegador **e** pesquisa gatos" | encadeia 2 comandos |
| "pesquisa X no Google" · "como chegar em Itapema" · "restaurantes bem avaliados em Blumenau" | busca / Maps |
| "escreve um texto sobre X" · "digita: reunião amanhã vírgula confirma" | redige / digita com pontuação ditada |
| "tira um print" · "o que tem na área de transferência" | tela / clipboard |
| "minimiza tudo" · "maximiza a janela" · "joga pra outra tela" | janelas |
| "modo apresentação" | varrer a mão na câmera = próximo/anterior slide (PowerPoint/PDF) |
| "esvazia a lixeira" · "bloqueia a tela" · "suspende" · "desliga / reinicia" | (pedem "sim") |

## Câmera e hologramas (Homem de Ferro)

Diga **"Jarvis, ativar câmera"**. Depois:

| Você diz | Aparece |
|---|---|
| "cria um cubo / esfera / cone / cilindro / pirâmide / toro / octaedro" | a forma 3D |
| "círculo trigonométrico" · "plota x ao quadrado menos 4" · "fórmula do volume da esfera" | matemática |
| "reta tangente de x²" · "integral de 0.5x + 1" · "soma de vetores" · "superfície 3D" | cálculo / álgebra linear |
| "diagrama de corpo livre" · "lançamento oblíquo" · "plano inclinado" · "onda" · "pêndulo" | física (com **sliders**) |
| "circuito em série / em paralelo" · "campo elétrico" · "lente convergente" · "colisão elástica" | física |
| "molécula da água / metano / benzeno / CO2 / amônia" · "geometria molecular tetraédrica" | química |
| "tabela periódica" · "pilha eletroquímica" | química |
| "célula animal" · "DNA" · "coração" · "neurônio" · "esqueleto" · "cérebro" | biologia |
| "sistema solar" · "gráfico de barras 4 7 3 9" · "árvore de probabilidade" | outros |
| "limpar tudo" | apaga os hologramas |

**Com as mãos** (na câmera):
- 👌 pinça perto de uma forma = seleciona (fica âmbar) e arrasta
- 👌 num **slider** do modelo = arrasta pra mudar o parâmetro (ângulo, massa, frequência…)
- ✊✊ (dois punhos) ou ✋✋ = gira como uma bola (trackball)
- ✋ da outra mão sobre uma animação = **congela e navega no tempo**
- ✋ **parada ~0,5s** = menu; empurra a mão pra escolher (Limpar / Travar / Duplicar / Explodir)
- ☝️ encosta numa forma = apaga

**Por voz**: "trava essa forma" · "copia isso" · "explode a molécula" · "modo desenho" ·
"modo medida" · "muda o ângulo pra 30" · "aumenta a massa" · "diminui a frequência".

**Gestos sem holograma**: mão aberta varrendo = ⏮/⏭ · punho ~1s = ⏯ · palma sobe/desce = volume.

Também: **"lê o QR code"** · **"lê o texto"** (OCR — ele lê e copia pra área de transferência) ·
**"aprende meu rosto"** (reconhecimento facial — depois ele te cumprimenta pelo nome).

## Estudo, perfis e configuração

| Você diz | O que acontece |
|---|---|
| "modo estudo" · "modo redação" · "modo prova" | sessão com professor: cronômetro, matéria e placar no HUD |
| "próxima questão" · "me explica melhor" · "uma dica" · "quanto tempo" · "como tô indo" | dentro do modo estudo |
| "sair do modo estudo" / "modo normal" | encerra com resumo (tempo + acertos) |
| "qual perfil está ativo" · "muda para o perfil robson" | troca quem o Jarvis trata (reinicia) |
| "abre as configurações" (ou o ícone ⚙ no app) | painel pra editar tudo |

---

## HUD do cérebro (a tela do app)

Mostra sozinho: relógio + data + clima · cronômetro/pomodoro · painel de estudo ·
próximos lembretes · lista de tarefas · CPU/RAM/GPU + temperatura da GPU ·
música com barra de progresso · feed de avisos (some sozinho) ·
estado (PENSANDO / PESQUISANDO / ERRO / FALANDO).

## Automações (`voice/hooks.toml`) e comandos próprios (`voice/skills_extra.toml`)

Edite esses `.toml` pra ligar eventos a ações (ex: "toda manhã, fala o resumo")
ou criar comandos sem programar. Recarregam sozinhos ao salvar.

## Chegada

Diga a frase de chegada (config `[arrival] phrase`) → toca a música + saudação +
briefing (hora, clima, lembretes do dia) + o app vem pra frente.
