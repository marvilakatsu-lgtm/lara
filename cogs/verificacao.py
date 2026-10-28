"""Módulo Verificação: Painéis de auto-cargos, regras e boas-vindas."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils import upsert_panel, get_text_channel
import config

log = logging.getLogger("colizeu.verificacao")


class Verificacao(commands.Cog):
    """Gerencia onboarding, verificação de membros e painéis de cargos."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        log.info("Módulo Verificação carregado.")

    # ------------------------------------------------------------------ Comandos Admin
    @app_commands.command(name="painel_verificacao", description="[MOD] Publica o painel de verificação e boas-vindas.")
    @app_commands.describe(canal="Canal onde o painel será publicado")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def painel_verificacao(self, interaction: discord.Interaction, canal: discord.TextChannel):
        embed = discord.Embed(
            title="📌 Bem-vindo ao Servidor",
            description=(
                "Para acessar todas as áreas do servidor, você precisa se verificar.\n\n"
                "**1.** Leia as regras em <#{}>\n"
                "**2.** Clique no botão abaixo para confirmar que leu e aceita as regras\n"
                "**3.** Escolha seus cargos opcionais no canal de cargos\n\n"
                "_A equipe está à disposição na Central de Ajuda._"
            ).format(config.MOD_CHANNEL_ID or 0),
            color=config.COR_OURO,
        )
        embed.set_footer(text="Colizeu • Sistema de Verificação")

        view = VerificacaoView()

        try:
            msg = await upsert_panel(
                self.bot, canal, "panel:verificacao",
                marker="verificacao:hub", content="", embeds=[embed], view=view
            )
            await interaction.response.send_message(f"✅ Painel publicado em {canal.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para enviar mensagens naquele canal.", ephemeral=True)

    @app_commands.command(name="painel_cargos", description="[MOD] Publica o painel de auto-atribuição de cargos.")
    @app_commands.describe(canal="Canal onde o painel será publicado")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def painel_cargos(self, interaction: discord.Interaction, canal: discord.TextChannel):
        embed = discord.Embed(
            title="🎭 Escolha Seus Cargos",
            description=(
                "Personalize sua experiência selecionando os cargos abaixo.\n\n"
                "• **Notificações:** Receba avisos de vídeos e lives\n"
                "• **Jogos Soulslike:** Acesse categorias privadas de jogos específicos\n\n"
                "_Clique nos botões para adicionar ou remover cargos._"
            ),
            color=config.COR_PRATA,
        )
        embed.set_footer(text="Colizeu • Auto-Cargos")

        view = CargosView()

        try:
            msg = await upsert_panel(
                self.bot, canal, "panel:cargos",
                marker="cargos:hub", content="", embeds=[embed], view=view
            )
            await interaction.response.send_message(f"✅ Painel publicado em {canal.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para enviar mensagens naquele canal.", ephemeral=True)


class VerificacaoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Verificar-me", style=discord.ButtonStyle.success, custom_id="verificacao:confirmar")
    async def verificar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Use este botão dentro do servidor.", ephemeral=True)

        # Buscar cargo "✅・Membro" ou similar
        cargo_membro = discord.utils.get(interaction.guild.roles, name="✅・Membro")
        if cargo_membro is None:
            # Fallback: tentar encontrar por alias
            for role in interaction.guild.roles:
                if "membro" in role.name.lower() and "trial" not in role.name.lower():
                    cargo_membro = role
                    break

        if cargo_membro is None:
            return await interaction.response.send_message(
                "⚠️ Cargo de membro não encontrado. Avise a equipe.", ephemeral=True
            )

        if cargo_membro in interaction.user.roles:
            return await interaction.response.send_message("ℹ️ Você já está verificado.", ephemeral=True)

        try:
            await interaction.user.add_roles(cargo_membro, reason="Verificação pelo painel")
            await interaction.response.send_message(
                f"✅ Verificado! Agora você tem acesso ao servidor. Bem-vindo, **{interaction.user.display_name}**!",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Não consegui adicionar o cargo. Verifique a hierarquia de cargos do bot.", ephemeral=True
            )


class CargosView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔔 Avisos", style=discord.ButtonStyle.primary, emoji="🔔", custom_id="cargos:avisos")
    async def toggle_avisos(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, "🔔・Avisos", ["avisos", "notificações"])

    @discord.ui.button(label="🌑 Elden Ring", style=discord.ButtonStyle.secondary, emoji="🌑", custom_id="cargos:elden")
    async def toggle_elden(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, "🌑・Elden Ring", ["elden ring", "elden-ring"])

    @discord.ui.button(label="💀 Dark Souls", style=discord.ButtonStyle.secondary, emoji="💀", custom_id="cargos:ds")
    async def toggle_ds(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, "💀・Dark Souls", ["dark souls", "dark-souls"])

    @discord.ui.button(label="🩸 Bloodborne", style=discord.ButtonStyle.secondary, emoji="🩸", custom_id="cargos:bb")
    async def toggle_bb(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle_role(interaction, "🩸・Bloodborne", ["bloodborne"])

    async def _toggle_role(self, interaction: discord.Interaction, nome_exato: str, aliases: list[str]):
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Use este botão dentro do servidor.", ephemeral=True)

        guild = interaction.guild
        role = discord.utils.get(guild.roles, name=nome_exato)

        # Fallback por alias se nome exato não existir
        if role is None:
            for r in guild.roles:
                norm = r.name.lower().replace(" ", "-")
                if any(a.replace(" ", "-") in norm for a in aliases):
                    role = r
                    break

        if role is None:
            return await interaction.response.send_message(
                f"⚠️ Cargo `{nome_exato}` não encontrado no servidor.", ephemeral=True
            )

        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Auto-cargo removido pelo usuário")
                await interaction.response.send_message(f"➖ Cargo **{role.name}** removido.", ephemeral=True)
            else:
                await interaction.user.add_roles(role, reason="Auto-cargo adicionado pelo usuário")
                await interaction.response.send_message(f"➕ Cargo **{role.name}** adicionado!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Não consegui alterar o cargo. Verifique a hierarquia.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Verificacao(bot))