"""Módulo Santuário: Perfis pessoais em threads privadas."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import config
from utils import get_text_channel

log = logging.getLogger("colizeu.santuario")

TEMAS_DISPONIVEIS = ["Ouro", "Prata", "Bronze", "Sombra", "Carmesim"]


class Santuario(commands.Cog):
    """Gerencia perfis de membros via threads privadas no canal de santuários."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        log.info("Módulo Santuário carregado.")

    @app_commands.command(name="meu_perfil", description="Cria ou edita seu perfil pessoal (thread privada).")
    @app_commands.guild_only()
    async def meu_perfil(self, interaction: discord.Interaction):
        db = self.bot.db
        user_id = interaction.user.id

        row = await db._one("SELECT * FROM usr_perfis WHERE user_id=?", (user_id,))
        canal_hub = await get_text_channel(self.bot, config.PERFIS_CHANNEL_ID)

        if not canal_hub:
            return await interaction.response.send_message(
                "❌ Canal de santuários não configurado. Avise a equipe.", ephemeral=True
            )

        if row and row["thread_id"]:
            try:
                thread = await self.bot.fetch_channel(row["thread_id"])
                if isinstance(thread, discord.Thread):
                    await interaction.response.send_message(
                        f"📜 Seu perfil já existe: {thread.mention}", ephemeral=True
                    )
                    return
            except (discord.NotFound, discord.HTTPException):
                pass  # Thread deletada; recriar

        # Criar nova thread privada
        try:
            thread = await canal_hub.create_thread(
                name=f"⛩️・{interaction.user.display_name}",
                type=discord.ChannelType.private_thread,
                reason="Santuário: criação de perfil pessoal",
            )
            await thread.add_user(interaction.user)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ Sem permissão para criar threads no canal de santuários.", ephemeral=True
            )

        embed = self._build_profile_embed(interaction.user, row)
        msg = await thread.send(embed=embed)

        await db.conn.execute(
            """INSERT INTO usr_perfis(user_id, thread_id, card_msg_id) VALUES (?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET thread_id=excluded.thread_id, card_msg_id=excluded.card_msg_id""",
            (user_id, thread.id, msg.id),
        )
        await db.conn.commit()

        await interaction.response.send_message(
            f"✅ Perfil criado! Acesse: {thread.mention}\nUse `/editar_perfil` para personalizar.",
            ephemeral=True,
        )

    @app_commands.command(name="editar_perfil", description="Edita bio, jogo favorito, tema e links do seu perfil.")
    @app_commands.describe(
        tagline="Frase curta que aparece abaixo do nome (máx 80 chars)",
        bio="Descrição sobre você (máx 500 chars)",
        fav_game="Jogo favorito atual",
        tema="Tema visual do card de perfil",
    )
    @app_commands.choices(tema=[app_commands.Choice(name=t, value=t) for t in TEMAS_DISPONIVEIS])
    @app_commands.guild_only()
    async def editar_perfil(
        self,
        interaction: discord.Interaction,
        tagline: str | None = None,
        bio: str | None = None,
        fav_game: str | None = None,
        tema: str | None = None,
    ):
        db = self.bot.db
        user_id = interaction.user.id

        row = await db._one("SELECT * FROM usr_perfis WHERE user_id=?", (user_id,))
        if not row or not row["thread_id"]:
            return await interaction.response.send_message(
                "❌ Você ainda não tem um perfil. Use `/meu_perfil` primeiro.", ephemeral=True
            )

        updates = {}
        if tagline is not None:
            updates["tagline"] = tagline.strip()[:80]
        if bio is not None:
            updates["bio"] = bio.strip()[:500]
        if fav_game is not None:
            updates["fav_game"] = fav_game.strip()[:100]
        if tema is not None and tema in TEMAS_DISPONIVEIS:
            updates["theme"] = tema

        if not updates:
            return await interaction.response.send_message(
                "ℹ️ Nenhum campo válido foi informado.", ephemeral=True
            )

        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [user_id]
        await db.conn.execute(
            f"UPDATE usr_perfis SET {set_clause} WHERE user_id=?", tuple(values)
        )
        await db.conn.commit()

        # Atualizar card na thread
        new_row = await db._one("SELECT * FROM usr_perfis WHERE user_id=?", (user_id,))
        embed = self._build_profile_embed(interaction.user, new_row)

        try:
            thread = await self.bot.fetch_channel(row["thread_id"])
            if isinstance(thread, discord.Thread) and row["card_msg_id"]:
                msg = await thread.fetch_message(row["card_msg_id"])
                await msg.edit(embed=embed)
        except (discord.NotFound, discord.HTTPException):
            pass

        campos = ", ".join(updates.keys())
        await interaction.response.send_message(
            f"✅ Perfil atualizado! Campos modificados: **{campos}**.", ephemeral=True
        )

    def _build_profile_embed(self, user: discord.Member | discord.User, row) -> discord.Embed:
        cores = {
            "Ouro": config.COR_OURO,
            "Prata": config.COR_PRATA,
            "Bronze": 0xCD7F32,
            "Sombra": 0x2C2C2C,
            "Carmesim": 0xDC143C,
        }
        tema = row["theme"] if row and row["theme"] else "Ouro"
        cor = cores.get(tema, config.COR_OURO)

        embed = discord.Embed(color=cor)
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)

        tagline = row["tagline"] if row and row["tagline"] else ""
        if tagline:
            embed.description = f"*{tagline}*"

        bio = row["bio"] if row and row["bio"] else "_Sem biografia definida._"
        embed.add_field(name="📝 Sobre", value=bio[:1024], inline=False)

        fav = row["fav_game"] if row and row["fav_game"] else "Não definido"
        embed.add_field(name="🎮 Jogo Favorito", value=fav, inline=True)
        embed.add_field(name="🎨 Tema", value=tema, inline=True)

        embed.set_footer(text="Use /editar_perfil para modificar • ⛩️ Santuário Colizeu")
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(Santuario(bot))