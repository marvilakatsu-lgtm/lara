"""Módulo Core: Health check, status e painel administrativo central."""
import discord
from discord import app_commands
from discord.ext import commands
import logging

log = logging.getLogger("colizeu.core")


class Core(commands.Cog):
    """Comandos essenciais de administração e verificação do bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="status", description="Verifica se o bot está online e mostra estatísticas básicas.")
    async def status(self, interaction: discord.Interaction):
        db = self.bot.db
        users = await db._one("SELECT COUNT(*) as c FROM usr_users")
        conquistas = await db._one("SELECT COUNT(*) as c FROM plat_conquistas WHERE status='approved'")
        runs = await db._one("SELECT COUNT(*) as c FROM sl_runs WHERE status='approved'")

        embed = discord.Embed(
            title="🟢 Colizeu Online",
            description="Sistema operacional e respondendo a comandos.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Usuários no DB", value=str(users["c"] if users else 0))
        embed.add_field(name="Conquistas Aprovadas", value=str(conquistas["c"] if conquistas else 0))
        embed.add_field(name="Runs Validadas", value=str(runs["c"] if runs else 0))
        embed.set_footer(text="Bot Unificado • Fase 3 Scaffold")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="painel_admin", description="[MOD] Abre o painel de controle do bot unificado.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def painel_admin(self, interaction: discord.Interaction):
        # Placeholder para o painel administrativo completo (Fase 4+)
        embed = discord.Embed(
            title="🛠️ Painel Administrativo",
            description=(
                "Este painel será expandido nas próximas fases para incluir:\n"
                "• Gestão de módulos (ativar/desativar)\n"
                "• Configuração de canais e IDs\n"
                "• Logs e auditoria\n"
                "• Ferramentas de moderação unificadas\n\n"
                "_Atualmente em desenvolvimento (Fase 3 concluída)._"
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))