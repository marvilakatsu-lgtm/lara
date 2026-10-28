"""Bot Unificado Colizeu — Entrypoint Principal."""
import asyncio
import logging
import sys
from pathlib import Path

import discord
from discord.ext import commands

import config
from db import Database

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("colizeu.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("colizeu")

# Intents Necessários
intents = discord.Intents.default()
intents.message_content = True  # Para comandos prefixados (se houver) e moderação
intents.members = True          # Para sincronização de cargos e perfis
intents.presences = True        # Opcional: para status de atividade


class ColizeuBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",  # Prefixo legado; foco é em slash commands
            intents=intents,
            help_command=None,
        )
        self.db = Database()

    async def setup_hook(self):
        """Inicializa banco de dados e carrega módulos."""
        await self.db.connect()
        log.info("Banco de dados conectado.")

        # Carregar Cogs (Módulos)
        cogs = [
            "cogs.core",
            "cogs.infra",
            "cogs.sentinela",
            "cogs.conquistas",
            "cogs.soulslike",
            "cogs.santuario",
            "cogs.youtube",
            "cogs.ofertas",
            "cogs.catalogo",
            "cogs.verificacao",
            "cogs.suporte_ia",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info("Módulo carregado: %s", cog)
            except Exception:
                log.exception("Falha ao carregar módulo: %s", cog)

        # Sincronizar comandos slash
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Comandos sincronizados no servidor %s: %s comandos.", config.GUILD_ID, len(synced))
        else:
            log.warning("GUILD_ID não definido. Comandos não foram sincronizados automaticamente.")

    async def on_ready(self):
        log.info("Bot conectado como %s (ID: %s)", self.user, self.user.id)
        log.info("Servidores: %d | Usuários: %d", len(self.guilds), sum(g.member_count or 0 for g in self.guilds))

    async def close(self):
        await self.db.close()
        await super().close()


async def main():
    if not config.DISCORD_TOKEN:
        log.error("DISCORD_TOKEN não encontrado no .env ou variáveis de ambiente.")
        return

    bot = ColizeuBot()
    async with bot:
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot interrompido pelo usuário.")