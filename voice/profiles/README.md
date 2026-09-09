# Perfis

Cada arquivo `<nome>.toml` aqui é um **perfil**: sobrescreve só o que muda
em relação ao `../config.toml` (mesma ideia do `secrets.toml`).

Ativar um perfil:

- no `config.toml`:  `[profile] active = "pai"`
- ou na linha de comando:  `pythonw jarvis_voice.py --profile pai`
- ou por variável de ambiente:  `JARVIS_PROFILE=pai`

Ordem de carga:  `config.toml`  →  `profiles/<ativo>.toml`  →  `secrets.toml`

## O que um perfil pode mudar

Qualquer chave do `config.toml`. Os pontos mais úteis:

| Seção | Pra quê |
|---|---|
| `[assistant]` | persona, `system_prompt`, `wake_word`, `address`, `attention_reply` |
| `[skills]` | ligar/desligar blocos: `games`, `holograms`, `music`, `maps`, `media_keys`, `compose`, `web_search` |
| `[arrival]` | `enabled = false` desliga a frase de chegada |
| `[apps]` | adiciona apps; `drop_apps = ["steam"]` remove os herdados do base |
| `[tts]` | outra voz (`sapi_voice`) |

`drop_apps` é uma lista especial (não é chave normal): remove do índice de
apps os nomes herdados do `config.toml` que não fazem sentido no perfil.

## Perfis atuais

- **`arthur.toml`** — pessoal, tudo ligado (praticamente igual ao base).
- **`pai.toml`** — instituto de desenvolvimento pessoal, foco trabalho:
  sem jogos, sem hologramas, sem música/entrada temática.
