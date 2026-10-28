# Organizador Quase-Pro (MVP)

Bot de Discord com **um único comando slash: `/painel`**. Todas as operações do organizador são feitas por botões e confirmações efêmeras.

## Segurança implementada

- Não apaga canais, categorias, mensagens ou cargos.
- Analisa a estrutura e apresenta uma prévia antes de alterar.
- Cria apenas categorias/canais ausentes e propõe renomeações.
- Movimentações são marcadas como revisão porque a categoria pode alterar permissões herdadas.
- Cargos básicos só são criados após confirmação; não recebem permissões administrativas automaticamente.
- Exige `Gerenciar servidor` para usar o painel e `Gerenciar cargos` para criar cargos.
- Mantém os IDs dos canais existentes quando renomeia/move; não edita mensagens dos outros bots.

## Limites conhecidos deste MVP

- Não existe garantia absoluta de ausência de erros: a API do Discord pode negar operações, atingir limites ou falhar por rede.
- O planejador por nome/alias é uma primeira aproximação. Revise o plano, principalmente os canais `coliseu`, `santuários`, `platinas`, `runs`, `lives`, `novos-vídeos` e canais de catálogo, antes de aprovar.
- Permissões, tópicos, mensagens fixadas, cargos de patente, tópicos privados e integrações não são reconfigurados automaticamente. Isso é intencional para evitar quebrar Soulsbot e Catálogo.
- Não apaga nem arquiva canais que não estejam no template; eles aparecem como não mapeados para revisão manual.
- O painel cria canais ausentes, renomeia e move canais reconhecidos. Sempre confira a prévia e o resultado.
- A lista de cargos é um ponto de partida. Cargos do Soulsbot/patentes são preservados e não são recriados por este fluxo.

## Instalação local

1. Instale Python 3.10 ou mais recente.
2. Extraia o ZIP e abra um terminal nesta pasta.
3. Crie um ambiente virtual (opcional, recomendado):

   ```bash
   python -m venv .venv
   ```

4. Ative o ambiente virtual e instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

5. Copie `.env.example` para `.env` e preencha `DISCORD_TOKEN` e `GUILD_ID`.
6. No Discord Developer Portal, habilite o bot e gere um convite com os escopos `bot` e `applications.commands`.
7. Conceda permissões mínimas necessárias: `Manage Channels`, `Manage Roles`, `View Channels`, `Send Messages`, `Embed Links`, `Read Message History`. Não conceda `Administrator` ao bot.
8. Convide o bot para o servidor e execute:

   ```bash
   python bot.py
   ```

9. No Discord, use `/painel` e clique primeiro em **Analisar servidor**. Leia a prévia antes de aplicar qualquer alteração.

## Recomendações antes de usar no servidor principal

- Faça primeiro um teste em um servidor de teste.
- Registre/guarde os IDs dos canais utilizados pelos bots atuais.
- Não mova canais de painéis especiais sem verificar a configuração dos bots. Mover um canal preserva o ID, mas pode mudar permissões herdadas.
- Faça backup das bases de dados e configurações do Soulsbot e Catálogo.
- Se o bot não conseguir executar uma ação, verifique sua posição na hierarquia de cargos e as permissões do canal.

## O que não fazer

- Não coloque o token do bot no código-fonte nem compartilhe o arquivo `.env`.
- Não execute este bot com o token do Soulsbot ou do Catálogo. Crie um bot Discord separado.
