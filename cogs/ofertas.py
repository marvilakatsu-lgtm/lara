"""Módulo Ofertas: Monitoramento de jogos grátis (GamerPower) e promoções Steam."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils import get_text_channel

log = logging.getLogger("colizeu.ofertas")


def money_brl(cents: Any) -> str | None:
    try:
        return f"R$ {int(cents) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return None


async def fetch_gamerpower(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    try:
        async with session.get(
            "https://www.gamerpower.com/api/giveaways",
            params={"type": "game"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status == 429:
                log.warning("GamerPower limitou requisições.")
                return []
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        log.exception("Falha consultando GamerPower.")
        return []
    if not isinstance(data, list):
        return []
    items = []
    for g in data:
        title = g.get("title")
        url = g.get("open_giveaway_url") or g.get("gamerpower_url")
        if not title or not url:
            continue
        end_date = str(g.get("end_date") or "").strip()
        if not end_date or end_date.upper() == "N/A":
            end_date = "Sem data informada"
        items.append({
            "key": f"gamerpower:{g.get('id') or title}",
            "title": title,
            "url": url,
            "image": g.get("thumbnail"),
            "description": (g.get("description") or "Jogo gratuito por tempo limitado.").strip(),
            "category": "JOGO GRÁTIS",
            "platform": g.get("platforms", "Plataforma não informada"),
            "price": "Grátis",
            "source": "GamerPower",
            "end_date": end_date,
            "kind": "game",
        })
    return items


async def fetch_steam_offers(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    try:
        async with session.get(
            "https://store.steampowered.com/api/featuredcategories/",
            params={"cc": "br", "l": "brazilian"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status == 429:
                log.warning("Steam Store limitou requisições.")
                return []
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        log.exception("Falha consultando Steam Store.")
        return []
    if not isinstance(data, dict):
        return []
    items = []
    for section_name in ("freegames", "specials"):
        section = data.get(section_name) or {}
        for game in section.get("items", []) if isinstance(section, dict) else []:
            app_id = game.get("id")
            title = game.get("name")
            if not app_id or not title:
                continue
            discount = int(game.get("discount_percent") or 0)
            final_cents = game.get("final_price")
            initial_cents = game.get("original_price")
            actually_free = bool(game.get("is_free")) or final_cents == 0
            if not actually_free and (final_cents is None or discount <= 0):
                continue
            final_price = "Grátis" if actually_free else money_brl(final_cents)
            original_price = None if actually_free else money_brl(initial_cents)
            if not final_price:
                continue
            items.append({
                "key": f"steam:{app_id}:{discount}:{final_cents}",
                "title": title,
                "url": f"https://store.steampowered.com/app/{app_id}/?cc=br",
                "image": game.get("header_image"),
                "description": "Oferta regional da Steam. Confira a página da loja para condições e validade.",
                "category": "JOGO GRÁTIS NA STEAM" if actually_free else f"PROMOÇÃO STEAM • {discount}% OFF",
                "platform": "Steam",
                "price": final_price,
                "original_price": original_price,
                "discount": discount,
                "source": "Steam Store Brasil",
                "end_date": "Consulte a página da loja",
                "kind": "game" if actually_free else "promo",
            })
    return items


def make_offer_embed(item: dict[str, Any]) -> discord.Embed:
    titulo = str(item["title"])[:250]
    descricao = str(item.get("description") or "Confira os detalhes na página da oferta.")[:950]
    tipo = str(item.get("category", "Oferta"))[:120]
    plataforma = str(item.get("platform", "Não informada"))[:120]
    preco = str(item.get("price", "Consulte a loja"))
    original = item.get("original_price")
    if original and original != preco:
        preco = f"~~{original}~~ → **{preco}**"
    validade = str(item.get("end_date") or "Consulte a loja")[:120]
    fonte = str(item.get("source", "Fonte não informada"))[:100]
    url = str(item.get("url", ""))
    imagem = item.get("image")

    cor = discord.Color.green() if item.get("kind") == "game" else discord.Color.orange()
    embed = discord.Embed(title=titulo, url=url or None, description=descricao, color=cor)
    embed.add_field(name="Tipo", value=tipo, inline=True)
    embed.add_field(name="Plataforma", value=plataforma, inline=True)
    embed.add_field(name="Preço", value=preco, inline=True)
    embed.add_field(name="Validade", value=validade, inline=False)
    embed.set_footer(text=f"Fonte: {fonte}")
    if imagem and str(imagem).startswith("https://"):
        embed.set_image(url=str(imagem))
    return embed


class Ofertas(commands.Cog):
    """Jogos grátis (GamerPower/Steam) e promoções da Steam."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.http_session: aiohttp.ClientSession | None = None
        self._first_run = True

    async def cog_load(self):
        self.http_session = aiohttp.ClientSession(headers={"User-Agent": "ColizeuBot/1.0"})
        self.offers_loop.start()

    async def cog_unload(self):
        self.offers_loop.cancel()
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()

    @tasks.loop(minutes=config.OFFERS_CHECK_MINUTES)
    async def offers_loop(self):
        if not self.http_session:
            return
        db = self.bot.db
        try:
            offers = await asyncio.gather(
                fetch_gamerpower(self.http_session),
                fetch_steam_offers(self.http_session),
                return_exceptions=True,
            )
            items = []
            for result in offers:
                if isinstance(result, list):
                    items.extend(result)
                elif isinstance(result, Exception):
                    log.error("Erro consultando uma fonte de ofertas: %r", result)

            unique = {item["key"]: item for item in items}

            # Primeira execução: seed sem postar para evitar spam histórico
            if self._first_run:
                count = await db._one("SELECT COUNT(*) as c FROM cfg_sent_offers")
                if count and count["c"] == 0 and unique:
                    for key in unique:
                        await db.conn.execute(
                            "INSERT OR IGNORE INTO cfg_sent_offers(item_key, sent_at) VALUES (?, ?)",
                            (key, datetime.now(timezone.utc).isoformat()),
                        )
                    await db.conn.commit()
                    log.info("Primeira execução: %d ofertas registradas sem postar.", len(unique))
                    self._first_run = False
                    return
                self._first_run = False

            sent_this_cycle = 0
            for item in unique.values():
                exists = await db._one("SELECT 1 FROM cfg_sent_offers WHERE item_key=?", (item["key"],))
                if exists:
                    continue
                if item["kind"] == "promo" and item.get("discount", 0) < config.MIN_PROMO_DISCOUNT:
                    continue

                target_id = config.GAMES_CHANNEL_ID if item["kind"] == "game" else config.PROMOS_CHANNEL_ID
                # Fallback para canal unificado de ofertas se IDs específicos não estiverem configurados
                if not target_id:
                    for ch in self.bot.get_all_channels():
                        if isinstance(ch, discord.TextChannel) and ch.name == "ofertas":
                            target_id = ch.id
                            break
                if not target_id:
                    continue

                channel = await get_text_channel(self.bot, target_id)
                if channel is None:
                    continue
                try:
                    await channel.send(embed=make_offer_embed(item))
                    await db.conn.execute(
                        "INSERT OR IGNORE INTO cfg_sent_offers(item_key, sent_at) VALUES (?, ?)",
                        (item["key"], datetime.now(timezone.utc).isoformat()),
                    )
                    await db.conn.commit()
                    sent_this_cycle += 1
                    await asyncio.sleep(1.2)
                    if sent_this_cycle >= config.MAX_OFFERS_PER_CHECK:
                        break
                except discord.HTTPException:
                    log.exception("Falha publicando oferta: %s", item.get("title"))
            log.info("Ofertas verificadas: %s; novas publicadas: %s", len(unique), sent_this_cycle)
        except Exception:
            log.exception("Erro na rotina de ofertas.")

    @offers_loop.before_loop
    async def before_offers_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="status_ofertas", description="Mostra se o monitoramento de ofertas está configurado.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def status_ofertas(self, interaction: discord.Interaction):
        games = f"<#{config.GAMES_CHANNEL_ID}>" if config.GAMES_CHANNEL_ID else "Padrão (#ofertas)"
        promos = f"<#{config.PROMOS_CHANNEL_ID}>" if config.PROMOS_CHANNEL_ID else "Padrão (#ofertas)"
        await interaction.response.send_message(
            f"**Jogos grátis:** {games}\n**Promoções:** {promos}\n"
            f"**Verificação:** a cada {config.OFFERS_CHECK_MINUTES} minutos.\n"
            f"**Desconto mínimo:** {config.MIN_PROMO_DISCOUNT}%",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Ofertas(bot))