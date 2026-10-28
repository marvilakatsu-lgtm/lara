"""Módulo YouTube: Monitoramento de vídeos e lives via RSS + API Data v3."""
import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils import get_text_channel

log = logging.getLogger("colizeu.youtube")

RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
YT_API_URL = "https://www.googleapis.com/youtube/v3"


class YouTube(commands.Cog):
    """Monitora canais do YouTube e publica notificações de vídeos/lives."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        self.check_youtube.start()
        log.info("YouTube cog carregado. Loop iniciado.")

    async def cog_unload(self):
        self.check_youtube.cancel()
        if self.session and not self.session.closed:
            await self.session.close()

    # ------------------------------------------------------------------ Loop
    @tasks.loop(minutes=config.YOUTUBE_CHECK_MINUTES)
    async def check_youtube(self):
        db = self.bot.db
        rows = await db._all("SELECT * FROM cfg_youtube_state")
        if not rows:
            return

        for row in rows:
            channel_id = row["channel_id"]
            last_video = row["last_video_id"]
            try:
                new_videos = await self._fetch_rss(channel_id)
            except Exception as e:
                log.warning("Falha RSS para %s: %s", channel_id, e)
                continue

            for video in reversed(new_videos):
                if video["id"] == last_video:
                    break
                # Publicar apenas se for novo
                await self._notify(video)
                last_video = video["id"]

            await db.conn.execute(
                "UPDATE cfg_youtube_state SET last_video_id=?, checked_at=? WHERE channel_id=?",
                (last_video, datetime.now(timezone.utc).isoformat(), channel_id),
            )
            await db.conn.commit()

    @check_youtube.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ RSS
    async def _fetch_rss(self, channel_id: str) -> list[dict]:
        url = RSS_URL.format(channel_id)
        async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return []
            text = await resp.text()

        root = ET.fromstring(text)
        ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
        items = []
        for entry in root.findall("atom:entry", ns):
            vid = entry.find("yt:videoId", ns)
            title = entry.find("atom:title", ns)
            link = entry.find("atom:link", ns)
            if vid is None or title is None:
                continue
            items.append({
                "id": vid.text,
                "title": title.text[:256],
                "url": link.attrib.get("href", f"https://youtu.be/{vid.text}") if link is not None else f"https://youtu.be/{vid.text}",
                "channel": channel_id,
            })
        return items

    async def _notify(self, video: dict):
        canal = await get_text_channel(self.bot, config.GAMES_CHANNEL_ID)  # Reusar canal de anúncios se configurado
        if not canal:
            # Fallback: tentar canal de anúncios padrão do template
            for ch in self.bot.get_all_channels():
                if isinstance(ch, discord.TextChannel) and ch.name == "anúncios":
                    canal = ch
                    break
        if not canal:
            return

        embed = discord.Embed(
            title=f"🎥 Novo Vídeo: {video['title']}",
            url=video["url"],
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=f"https://i.ytimg.com/vi/{video['id']}/hqdefault.jpg")
        embed.set_footer(text="Notificação automática • YouTube")
        try:
            await canal.send(embed=embed)
        except discord.HTTPException as e:
            log.error("Falha ao notificar vídeo %s: %s", video["id"], e)

    # ------------------------------------------------------------------ Comandos Admin
    @app_commands.command(name="yt_adicionar", description="[MOD] Adiciona um canal do YouTube para monitoramento.")
    @app_commands.describe(channel_id="ID do canal do YouTube (ex: UCxxxxxxx)")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def yt_adicionar(self, interaction: discord.Interaction, channel_id: str):
        db = self.bot.db
        existing = await db._one("SELECT 1 FROM cfg_youtube_state WHERE channel_id=?", (channel_id,))
        if existing:
            return await interaction.response.send_message("⚠️ Canal já está sendo monitorado.", ephemeral=True)

        await db.conn.execute(
            "INSERT INTO cfg_youtube_state(channel_id, last_video_id) VALUES (?, ?)",
            (channel_id, ""),
        )
        await db.conn.commit()
        await db.log(interaction.user.id, "yt_canal_adicionado", channel_id)
        await interaction.response.send_message(f"✅ Canal `{channel_id}` adicionado ao monitoramento.", ephemeral=True)

    @app_commands.command(name="yt_listar", description="[MOD] Lista canais monitorados.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def yt_listar(self, interaction: discord.Interaction):
        rows = await self.bot.db._all("SELECT channel_id, checked_at FROM cfg_youtube_state ORDER BY channel_id")
        if not rows:
            return await interaction.response.send_message("Nenhum canal configurado.", ephemeral=True)
        linhas = "\n".join(f"• `{r['channel_id']}` — última verificação: {r['checked_at'] or 'nunca'}" for r in rows)
        await interaction.response.send_message(f"**Canais Monitorados:**\n{linhas}", ephemeral=True)

    @app_commands.command(name="status_youtube", description="Verifica status do monitoramento YouTube.")
    @app_commands.guild_only()
    async def status_youtube(self, interaction: discord.Interaction):
        count = await self.bot.db._one("SELECT COUNT(*) as c FROM cfg_youtube_state")
        embed = discord.Embed(title="📺 Status YouTube", color=discord.Color.blurple())
        embed.add_field(name="Canais Monitorados", value=str(count["c"] if count else 0))
        embed.add_field(name="Intervalo", value=f"{config.YOUTUBE_CHECK_MINUTES} min")
        embed.add_field(name="API Key", value="✅ Configurada" if config.YOUTUBE_API_KEY else "❌ Ausente (apenas RSS)")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(YouTube(bot))