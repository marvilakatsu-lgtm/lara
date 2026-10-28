"""Funções utilitárias compartilhadas entre os módulos do Bot Colizeu."""
import discord
from discord.ext import commands
import logging

log = logging.getLogger("colizeu.utils")


async def get_text_channel(bot: commands.Bot, channel_id: int) -> discord.TextChannel | None:
    """Retorna um canal de texto pelo ID, ou None se não existir/for acessível."""
    if not channel_id:
        return None
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
    return channel if isinstance(channel, discord.TextChannel) else None


async def upsert_panel(
    bot: commands.Bot,
    channel: discord.TextChannel,
    key: str,
    *,
    marker: str,
    content: str,
    embeds: list[discord.Embed],
    view: discord.ui.View | None = None,
) -> discord.Message:
    """Cria ou edita uma mensagem de painel persistente.

    Usa a tabela cfg_painels para rastrear message_id e evitar duplicatas.
    O 'marker' é usado como custom_id prefixo nos componentes da view.
    """
    db = bot.db
    row = await db._one("SELECT message_id FROM cfg_painels WHERE key=?", (key,))
    msg = None
    if row and row["message_id"]:
        try:
            msg = await channel.fetch_message(row["message_id"])
        except (discord.NotFound, discord.HTTPException):
            msg = None

    if msg:
        await msg.edit(content=content, embeds=embeds, view=view)
    else:
        msg = await channel.send(content=content, embeds=embeds, view=view)
        await db.conn.execute(
            "INSERT OR REPLACE INTO cfg_painels(key, channel_id, message_id, marker) VALUES (?, ?, ?, ?)",
            (key, channel.id, msg.id, marker),
        )
        await db.conn.commit()
    return msg


async def erro_comando(interaction: discord.Interaction, error: Exception):
    """Handler padrão de erros para comandos slash."""
    log.exception("Erro em comando slash", exc_info=error)
    texto = "Ocorreu um erro ao executar este comando. A equipe já foi notificada."
    if isinstance(error, discord.app_commands.MissingPermissions):
        texto = "Você não tem permissão para usar este comando."
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        texto = f"Este comando está em cooldown. Tente novamente em {error.retry_after:.0f}s."

    if interaction.response.is_done():
        await interaction.followup.send(texto, ephemeral=True)
    else:
        await interaction.response.send_message(texto, ephemeral=True)