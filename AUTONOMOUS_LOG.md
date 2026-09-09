# Registro do trabalho autônomo

Arthur saiu do escritório e pediu pra eu aplicar TODAS as ideias do
`ROADMAP.md`, sozinho, em loop, até ele voltar e mandar parar.

Início: 2026-09-09 ~15h. Ambiente: repo local `E:\OpenJarvis` (sem remote —
nada sai da máquina), daemon de voz rodando, Ollama no ar.

Regras que eu me impus:
- Só trabalho local. Nada de enviar/publicar/gastar/contatar ninguém.
- Não toco no pacote que está sendo enviado pro pai (`installer/pacote/`).
- Commit a cada feature que passa nos testes.
- Cada item ganha uma nota aqui: o que é, como testei, o que ficou pendente.
- O que precisa de conta externa / chave paga / hardware: documento, não finjo.

---

## Feito nesta sessão

### Seção C — assistente mais capaz  ✅ (menos notícias)

- **Lembretes e timers** (`voice/reminders.py`, `9e32b69`+)
  - "me lembra de X em 20 minutos" / "às 15h" / "amanhã às 9" / "uma hora e meia"
  - "timer de 10 minutos", "meus lembretes", "cancela os lembretes"
  - persiste em `voice/reminders.json`; thread no daemon fala quando vence
  - testado: parsing de ~15 formas de tempo, ciclo add→due→fala
- **Clima** (`voice/weather.py`) — Open-Meteo, sem chave
  - "como está o tempo", "vai chover amanhã", "temperatura em São Paulo"
  - localização por `[location].city` do config ou pelo IP
  - testado ao vivo: Blumenau, SP, Recife, Londres, Florianópolis
- **Contas + conversão** (`voice/calc.py`)
  - "15 por cento de 240", "342 vezes 12", "raiz de 169", "dobro/metade de X"
  - comprimento / massa / temperatura (C-F-K) / câmbio (frankfurter.dev + er-api)
  - direção da conversão pela posição do número na frase
  - testado ao vivo com câmbio real
- **Briefing na chegada** — depois da saudação: "São 15 e 20. 23 graus,
  nublado. 1 lembrete pra hoje, senhor." (`[arrival].briefing`)
- **Ditado direcionado** — "escreve no bloco de notas: comprar leite"
  abre o app e cola o texto

Pendente da seção C: **notícias** (dá pra fazer com RSS keyless — vou voltar).
