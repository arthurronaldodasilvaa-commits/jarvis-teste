# Perfis

Um perfil muda só **como o Jarvis chama e trata a pessoa** — nome, tratamento,
persona (`system_prompt`), voz, frase de chegada. **Todas as funcionalidades
continuam disponíveis em qualquer perfil** (hologramas, música, jogos, mapas…).

Cada arquivo `<nome>.toml` sobrescreve só o que muda em relação ao
`../config.toml` (mesma ideia do `secrets.toml`).

Ativar um perfil:

- no `config.toml`:  `[profile] active = "robson"`
- ou na linha de comando:  `pythonw jarvis_voice.py --profile robson`
- ou por variável de ambiente:  `JARVIS_PROFILE=robson`

Ordem de carga:  `config.toml`  →  `profiles/<ativo>.toml`  →  `secrets.toml`

## O que faz sentido um perfil mudar

| Seção | Chaves |
|---|---|
| `[assistant]` | `user_name`, `address`, `wake_word`, `attention_reply`, `system_prompt`, `reply_num_predict`, `knowledge` (base de conhecimento anexada ao prompt — ex: dados da empresa) |
| `[arrival]` | `enabled`, `phrase`, `greeting`, `spotify` (a entrada temática é pessoal) |
| `[tts]` | `sapi_voice` (outra voz) |
| `[apps]` | adicionar atalhos de app extras (merge com os do base) |

## Perfis atuais

- **`arthur.toml`** — pessoal (praticamente igual ao base).
- **`robson.toml`** — pai, **dono do Instituto CAM** (desenvolvimento humano/
  corporativo). Persona de secretário executivo, `knowledge` com os dados da
  empresa (fonte: institutocam.com.br), sem frase de chegada, + atalhos de
  Gmail/Agenda/Drive/Meet/site.
