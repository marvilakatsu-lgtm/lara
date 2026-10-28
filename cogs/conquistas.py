"""Módulo Conquistas: Unificação de Platinas (com aprovação) e Zerados (sem aprovação)."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import date

import config
from utils import upsert_panel, get_text_channel

log = logging.getLogger("colizeu.conquistas")


class Conquistas(commands.Cog):
    """Gerencia registro de platinas e jogos zerados, ranking e galeria."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        log.info("Módulo Conquistas carregado.")

    # ------------------------------------------------------------------ Comandos de Registro
    @app_commands.command(name="platina", description="Registra uma platina conquistada (requer aprovação).")
    @app_commands.describe(
        jogo="Nome do jogo",
        plataforma="Plataforma onde obteve (PS5, PC, Xbox...)",
        comentario="Comentário breve sobre a conquista (opcional)"
    )
    @app_commands.guild_only()
    async def registrar_platina(self, interaction: discord.Interaction, jogo: str, plataforma: str, comentario: str = ""):
        await self._registrar(interaction, "platina", jogo, plataforma, comentario)

    @app_commands.command(name="zerado", description="Registra um jogo finalizado (aprovação automática).")
    @app_commands.describe(
        jogo="Nome do jogo",
        plataforma="Plataforma onde zerou",
        comentario="Impressões finais (opcional)"
    )
    @app_commands.guild_only()
    async def registrar_zerado(self, interaction: discord.Interaction, jogo: str, plataforma: str, comentario: str = ""):
        await self._registrar(interaction, "zerado", jogo, plataforma, comentario)

    async def _registrar(self, interaction: discord.Interaction, tipo: str, jogo: str, plataforma: str, comentario: str):
        db = self.bot.db
        user_id = interaction.user.id

        # Verificar limite diário para zerados (se configurado)
        if tipo == "zerado":
            hoje = date.today().isoformat()
            row = await db._one(
                "SELECT COUNT(*) as c FROM plat_conquistas WHERE user_id=? AND tipo='zerado' AND date(criado_em)=?",
                (user_id, hoje)
            )
            if row and row["c"] >= config.ZERADOS_XP_LIMITE_DIARIO:
                return await interaction.response.send_message(
                    f"⚠️ Você atingiu o limite diário de {config.ZERADOS_XP_LIMITE_DIARIO} registros de jogos zerados.",
                    ephemeral=True
                )

        status = "pending" if tipo == "platina" else "approved"

        await db.conn.execute(
            """INSERT INTO plat_conquistas(user_id, tipo, game, platform, comentario, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, tipo, jogo.strip(), plataforma.strip(), comentario.strip(), status)
        )
        await db.conn.commit()

        if status == "approved":
            # Conceder XP/Denários imediatamente para zerados
            xp_ganho = config.XP_ZERADO
            denarios_ganhos = config.DENARIOS_ZERADO

            await db.conn.execute(
                """INSERT INTO usr_users(user_id, xp, denarios) VALUES (?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     xp = xp + excluded.xp,
                     denarios = denarios + excluded.denarios""",
                (user_id, xp_ganho, denarios_ganhos)
            )
            await db.conn.execute(
                "UPDATE plat_conquistas SET xp_awarded=?, denarios_awarded=? WHERE user_id=? AND game=? AND status='approved' ORDER BY id DESC LIMIT 1",
                (xp_ganho, denarios_ganhos, user_id, jogo.strip())
            )
            await db.conn.commit()

            await db.log(user_id, f"{tipo}_registrado", f"jogo={jogo} auto_aprovado")
            embed = discord.Embed(
                title=f"✅ {jogo} Registrado!",
                description=f"**{jogo}** foi adicionado aos seus **{tipo}s**.\nVocê ganhou **+{xp_ganho} XP** e **+{denarios_ganhos} Denários**.",
                color=config.COR_PRATA
            )
        else:
            await db.log(user_id, "platina_pendente", f"jogo={jogo}")
            embed = discord.Embed(
                title="⏳ Platina Enviada para Análise",
                description=f"Sua conquista em **{jogo}** ({plataforma}) está aguardando aprovação da equipe.\nAssim que aprovada, você receberá sua recompensa.",
                color=config.COR_OURO
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ Consultas
    @app_commands.command(name="minhas_conquistas", description="Lista suas platinas e jogos zerados.")
    @app_commands.guild_only()
    async def minhas_conquistas(self, interaction: discord.Interaction):
        db = self.bot.db
        rows = await db._all(
            "SELECT tipo, game, platform, status, criado_em FROM plat_conquistas WHERE user_id=? ORDER BY criado_em DESC LIMIT 10",
            (interaction.user.id,)
        )

        if not rows:
            return await interaction.response.send_message("Você ainda não registrou conquistas.", ephemeral=True)

        linhas = []
        for r in rows:
            emoji = "💎" if r["tipo"] == "platina" else "🏁"
            status_icon = {"approved": "✅", "pending": "⏳", "rejected": "❌"}.get(r["status"], "?")
            linhas.append(f"{emoji} **{r['game']}** ({r['platform']}) — {status_icon}")

        embed = discord.Embed(
            title="🏆 Suas Conquistas Recentes",
            description="\n".join(linhas),
            color=config.COR_PRATA
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ Painel Público (Coliseu)
    @app_commands.command(name="painel_coliseu", description="[MOD] Publica o painel de conquistas no canal designado.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def painel_coliseu(self, interaction: discord.Interaction, canal: discord.TextChannel):
        embed = discord.Embed(
            title="🏆 Coliseu de Conquistas",
            description=(
                "Bem-vindo ao hall dos guerreiros!\n\n"
                "Use `/platina` para submeter suas platinas à aprovação.\n"
                "Use `/zerado` para registrar jogos finalizados instantaneamente.\n"
                "Use `/minhas_conquistas` para ver seu histórico."
            ),
            color=config.COR_OURO
        )
        try:
            msg = await upsert_panel(
                self.bot, canal, "panel:coliseu",
                marker="coliseu:hub", content="", embeds=[embed], view=None
            )
            await interaction.response.send_message(f"✅ Painel publicado em {canal.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para enviar mensagens naquele canal.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Conquistas(bot))