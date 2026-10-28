"""Módulo Sentinela: Sistema de XP, níveis, patentes e sincronização de cargos."""
import time
import math
import discord
from discord import app_commands
from discord.ext import commands, tasks
import logging

import config

log = logging.getLogger("colizeu.sentinela")

# Fórmula de progressão: XP necessário para o próximo nível
def xp_para_nivel(nivel: int) -> int:
    """Calcula XP total necessário para atingir um nível (base 100, crescimento exponencial suave)."""
    return int(100 * (nivel ** 1.5))

def nivel_por_xp(xp: int) -> int:
    """Retorna o nível correspondente a uma quantidade de XP."""
    if xp <= 0:
        return 1
    # Estimativa inicial e ajuste fino
    n = max(1, int((xp / 100) ** (2/3)))
    while xp_para_nivel(n + 1) <= xp:
        n += 1
    while n > 1 and xp < xp_para_nivel(n):
        n -= 1
    return n

PATENTES = [
    (1, "🌱 Novato"),
    (5, "⚔️ Guerreiro"),
    (10, "🛡️ Cavaleiro"),
    (20, "🔥 Campeão"),
    (35, "💀 Lenda"),
    (50, "👑 Soberano"),
]

def patente_por_nivel(nivel: int) -> str:
    """Retorna a patente correspondente ao nível."""
    titulo = PATENTES[0][1]
    for lvl_min, nome in PATENTES:
        if nivel >= lvl_min:
            titulo = nome
    return titulo


class Sentinela(commands.Cog):
    """Gerencia progressão de membros: XP, níveis, patentes e cargos automáticos."""

    COOLDOWN_SEGUNDOS = 60  # XP apenas uma vez por minuto por usuário

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cooldowns: dict[int, float] = {}

    async def cog_load(self):
        log.info("Sentinela carregada com cooldown de %ds.", self.COOLDOWN_SEGUNDOS)

    # ------------------------------------------------------------------ Eventos
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        user_id = message.author.id
        agora = time.time()
        ultimo = self._cooldowns.get(user_id, 0)
        if agora - ultimo < self.COOLDOWN_SEGUNDOS:
            return

        db = self.bot.db
        row = await db._one(
            "SELECT xp, nivel FROM usr_users WHERE user_id=?", (user_id,)
        )
        xp_atual = row["xp"] if row else 0
        nivel_atual = row["nivel"] if row else 1

        # Ganho base por mensagem (10-20 XP aleatório simplificado para fixo 15)
        ganho = 15
        novo_xp = xp_atual + ganho
        novo_nivel = nivel_por_xp(novo_xp)

        await db.conn.execute(
            """INSERT INTO usr_users(user_id, xp, nivel, last_xp_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET
                 xp=excluded.xp, nivel=excluded.nivel, last_xp_at=datetime('now')""",
            (user_id, novo_xp, novo_nivel),
        )
        await db.conn.commit()
        self._cooldowns[user_id] = agora

        # Level up
        if novo_nivel > nivel_atual:
            nova_patente = patente_por_nivel(novo_nivel)
            await db.log(user_id, "level_up", f"lvl={novo_nivel} patente={nova_patente}")

            try:
                embed = discord.Embed(
                    title="🎉 Nível Alcançado!",
                    description=(
                        f"**{message.author.mention}** subiu para o **Nível {novo_nivel}**!\n"
                        f"Patente atual: **{nova_patente}**"
                    ),
                    color=config.COR_OURO,
                )
                await message.channel.send(embed=embed)
            except discord.HTTPException:
                pass

            # Sincronizar cargo de patente se existir no servidor
            await self._sync_patente_role(message.author, nova_patente)

    # ------------------------------------------------------------------ Comandos
    @app_commands.command(name="nivel", description="Mostra seu nível, XP e patente atuais.")
    @app_commands.guild_only()
    async def nivel(self, interaction: discord.Interaction):
        db = self.bot.db
        row = await db._one(
            "SELECT xp, nivel FROM usr_users WHERE user_id=?", (interaction.user.id,)
        )
        if not row:
            return await interaction.response.send_message(
                "Você ainda não tem progresso registrado. Envie mensagens para começar!",
                ephemeral=True,
            )

        xp = row["xp"]
        lvl = row["nivel"]
        patente = patente_por_nivel(lvl)
        proximo_xp = xp_para_nivel(lvl + 1)
        progresso = min(100, int((xp / proximo_xp) * 100)) if proximo_xp > 0 else 100

        embed = discord.Embed(title="📊 Seu Progresso", color=config.COR_PRATA)
        embed.add_field(name="Nível", value=str(lvl), inline=True)
        embed.add_field(name="Patente", value=patente, inline=True)
        embed.add_field(name="XP Total", value=f"{xp:,}", inline=True)
        embed.add_field(
            name="Progresso",
            value=f"{progresso}% para o Nível {lvl + 1} ({xp:,}/{proximo_xp:,} XP)",
            inline=False,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ranking-xp", description="Top 10 membros por XP no servidor.")
    @app_commands.guild_only()
    async def ranking_xp(self, interaction: discord.Interaction):
        db = self.bot.db
        rows = await db._all(
            "SELECT user_id, xp, nivel FROM usr_users ORDER BY xp DESC LIMIT 10"
        )
        if not rows:
            return await interaction.response.send_message(
                "Ainda não há dados de XP registrados.", ephemeral=True
            )

        linhas = []
        medalhas = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(rows):
            pos = medalhas[i] if i < 3 else f"`{i+1}.`"
            patente = patente_por_nivel(r["nivel"])
            linhas.append(
                f"{pos} <@{r['user_id']}> — **Lvl {r['nivel']}** · {patente} · {r['xp']:,} XP"
            )

        embed = discord.Embed(
            title="🏆 Ranking de XP",
            description="\n".join(linhas),
            color=config.COR_OURO,
        )
        embed.set_footer(text="Atualizado em tempo real")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------ Internos
    async def _sync_patente_role(self, member: discord.Member, patente_nome: str):
        """Adiciona o cargo da patente e remove os anteriores, se existirem no servidor."""
        guild = member.guild
        todos_cargos_patente = [p[1] for p in PATENTES]

        cargo_alvo = discord.utils.get(guild.roles, name=patente_nome)
        if cargo_alvo is None:
            return  # Cargo não foi criado ainda; infra_cargos pode ser usado depois

        cargos_remover = []
        for nome in todos_cargos_patente:
            if nome == patente_nome:
                continue
            role = discord.utils.get(guild.roles, name=nome)
            if role and role in member.roles:
                cargos_remover.append(role)

        try:
            if cargos_remover:
                await member.remove_roles(*cargos_remover, reason="Sentinela: troca de patente")
            if cargo_alvo not in member.roles:
                await member.add_roles(cargo_alvo, reason="Sentinela: nova patente alcançada")
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning("Falha sincronizando patente para %s: %s", member.id, e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Sentinela(bot))