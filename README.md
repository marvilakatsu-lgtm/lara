# Colizeu — Bot Unificado Discord

Bot modular que integra gamificação, conquistas, speedruns, catálogo, ofertas, YouTube e automação de estrutura em um único sistema persistente e seguro.

## Requisitos

- Python 3.10+
- SQLite (incluso no Python)
- Acesso externo: Discord API, Steam Store, GamerPower, YouTube RSS/API
- Hospedagem recomendada: Fade Host (volume persistente em `/app/data`)

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# ou .venv\Scripts\activate  # Windows

pip install -r requirements.txt
cp .env.example .env
# Edite .env com seu DISCORD_TOKEN e IDs dos canais
```

## Variáveis de Ambiente (.env)

| Variável | Obrigatória | Descrição |
| :--- | :--- | :--- |
| `DISCORD_TOKEN` | ✅ Sim | Token do bot no Developer Portal |
| `DATABASE_PATH` | Não | Caminho do SQLite (padrão: `./data/colizeu.db`) |
| `GUILD_ID` | Recomendado | ID do servidor para sync imediato de comandos |
| `MOD_CHANNEL_ID` | ✅ Sim | Canal onde runs/platinas são aprovadas |
| `PERFIS_CHANNEL_ID` | ✅ Sim | Canal hub dos santuários (threads privadas) |
| `YOUTUBE_API_KEY` | Não | Opcional; sem ela usa apenas RSS |
| `LLM_API_KEY` | Não | Para suporte IA (desativado por padrão) |
| `OFFERS_CHECK_MINUTES` | Não | Intervalo de verificação de ofertas (padrão: 30) |

## Execução

```bash
python bot.py
```

O bot cria automaticamente o banco de dados e as tabelas na primeira execução.

## Módulos Ativos

| Módulo | Comando Principal | Função |
| :--- | :--- | :--- |
| Core/Painel | `/painel` | Interface central por botões, formulários e submenus |
| Infra | `/infra_analisar`, `/infra_aplicar` | Reconciliação declarativa de canais/cargos |
| Sentinela | `/nivel`, `/ranking-xp` | XP, níveis, patentes e cargos automáticos |
| Conquistas | `/platina`, `/zerado`, `/minhas_conquistas` | Platinas (com aprovação) e zerados (auto) |
| Soulslike | `/run_registrar`, `/ranking_souls` | Speedruns com prova via DM e moderação |
| Santuário | `/meu_perfil`, `/editar_perfil` | Threads privadas de perfil pessoal |
| YouTube | `/yt_adicionar`, `/status_youtube` | Notificações de vídeos/lives via RSS |
| Ofertas | `/status_ofertas` | Jogos grátis (GamerPower) e promoções Steam |
| Catálogo | `/catalogo_buscar`, `/catalogo_adicionar` | Gestão de jogos/mods com busca por tags |
| Verificação | `/painel_verificacao`, `/painel_cargos` | Onboarding e auto-cargos persistentes |

## Painel único por botões

No Discord, execute somente `/painel`. O painel é privado para quem o abriu e apresenta áreas de jogador e administração. As ações reutilizam os módulos existentes e pedem os dados necessários por formulários; ações que publicam painéis pedem a seleção do canal.

A sincronização do bot remove os demais comandos da lista de comandos slash do servidor e publica apenas `/painel`. Na primeira inicialização após a atualização, o Discord pode levar alguns instantes para refletir a lista nova. Ações administrativas continuam protegidas por permissões do Discord.

## Reconstrução do Servidor

1. Adicione o bot ao servidor com permissões: `Manage Channels`, `Manage Roles`, `Send Messages`, `Embed Links`, `Read Message History`.
2. Abra `/painel` → **Servidor** → **Analisar estrutura** para ver o plano de reconciliação.
3. Revise as ações propostas (nenhuma alteração é feita automaticamente).
4. No painel, abra **Servidor** → **Aplicar estrutura analisada** para criar/renomear canais e categorias conforme o template otimizado.
5. No painel, abra **Servidor** → **Criar cargos padrão** para criar os cargos padrão ausentes.
6. Publique os painéis nos canais correspondentes:
   - Use `/painel` → **Servidor** para publicar cada painel e selecionar o canal.

## Persistência e Backup

- O banco SQLite é criado em `DATABASE_PATH` (padrão: `./data/colizeu.db`).
- Na Fade Host, monte um volume persistente em `/app/data`.
- Backup recomendado: cópia diária do arquivo `.db`.
- Views e painéis sobrevivem a reinícios via `custom_id` persistente e tabela `cfg_painels`.

## Segurança

- Todos os comandos administrativos exigem `Manage Guild` ou `Manage Roles`.
- Runs e platinas passam por moderação antes de entrar no ranking.
- Logs de auditoria em `sys_logs` para todas as ações críticas.
- Rate limit em IA (3 req/min/usuário) e cooldown de XP (60s/mensagem).
- Nenhum canal ou cargo é apagado automaticamente pelo módulo Infra.

## Limitações Conhecidas

- **YouTube:** Sem API key, depende exclusivamente de RSS (atraso de até 15 min).
- **Santuários:** Threads privadas exigem permissão `Create Private Threads` no canal hub.
- **Ofertas:** Steam pode retornar 429 sob carga; retry não implementado nesta versão.
- **IA Suporte:** Desativada por padrão; requer `LLM_API_KEY` e ativação manual em `bot.py`.
- **Catálogo:** Busca por LIKE simples; sem full-text search ou paginação avançada.

## Estrutura de Arquivos

```
bot_unificado/
├── bot.py              # Entrypoint principal
├── config.py           # Configuração centralizada
├── db.py               # Banco de dados SQLite assíncrono
├── utils.py            # Funções auxiliares compartilhadas
├── requirements.txt    # Dependências Python
├── .env.example        # Template de variáveis de ambiente
├── README.md           # Este arquivo
└── cogs/
    ├── core.py         # Health check e painel admin
    ├── infra.py        # Reconciliação de estrutura
    ├── sentinela.py    # XP, níveis e patentes
    ├── conquistas.py   # Platinas e zerados
    ├── soulslike.py    # Runs e desafios
    ├── santuario.py    # Perfis em threads
    ├── youtube.py      # Monitoramento YouTube
    ├── ofertas.py      # Jogos grátis e promoções
    ├── catalogo.py     # Gestão de jogos/mods
    └── verificacao.py  # Onboarding e auto-cargos
```

## Suporte

Para dúvidas sobre funcionalidades, use `/painel` no Discord ou consulte este README.
Erros são registrados em `colizeu.log` e na tabela `sys_logs`.

---

*Projeto gerado na Fase 4 • Arquitetura definida na Fase 2 • Inventário completo na Fase 1*
*Exclusão confirmada: módulo de Notícias/RSS não faz parte deste sistema.*