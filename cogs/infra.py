"""Módulo Infra: Reconciliação declarativa de canais, categorias e cargos."""
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
import logging

log = logging.getLogger("colizeu.infra")


def _norm(s: str) -> str:
    """Normaliza nomes para comparação semântica (sem emojis, acentos ou pontuação)."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"<a?:[^:]+:\d+>", "", s)  # remove emojis customizados
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


# Template declarativo baseado na Fase 2 (Versão Otimizada)
TEMPLATE_CATEGORIES = [
    {
        "name": "📌・INFORMAÇÕES",
        "aliases": ["comece-aqui", "informacoes", "boas-vindas"],
        "channels": [
            ("📜・regras-e-boas-vindas", "text", ["regras", "boas-vindas", "onboarding"]),
            ("✅・verificação", "text", ["verificacao", "verify"]),
            ("🎭・cargos", "text", ["cargos", "roles", "auto-cargos"]),
        ],
    },
    {
        "name": "⚔️・SOULSLIKE",
        "aliases": ["universo-soulslike", "soulslike", "jogos-souls"],
        "channels": [
            ("🔥・runs-e-desafios", "text", ["runs", "desafios", "speedrun"]),
            ("🎮・jogos-soulslike", "text", ["geral-souls", "discussao-souls"]),
        ],
    },
    {
        "name": "🏆・CONQUISTAS",
        "aliases": ["conquistas", "platinas", "trofeus"],
        "channels": [
            ("🏆・coliseu", "text", ["coliseu", "colizeu", "hall"]),
            ("📊・rankings", "text", ["ranking", "leaderboard", "top"]),
        ],
    },
    {
        "name": "👤・COMUNIDADE",
        "aliases": ["comunidade", "social", "membros"],
        "channels": [
            ("⛩️・santuários", "text", ["santuarios", "perfis-hub"]),
            ("💬・bate-papo", "text", ["chat", "geral", "conversa"]),
        ],
    },
    {
        "name": "🤖・CATÁLOGO",
        "aliases": ["catalogo", "jogos-e-mods", "mods"],
        "channels": [
            ("🎮・jogos-e-mods", "text", ["catalogo-jogos", "lista-mods"]),
            ("🆓・ofertas", "text", ["promocoes", "jogos-gratis", "descontos"]),
        ],
    },
    {
        "name": "📢・ANÚNCIOS",
        "aliases": ["anuncios", "novidades", "avisos"],
        "channels": [
            ("📢・anúncios", "text", ["anuncios", "feed", "noticias-oficiais"]),
        ],
    },
    {
        "name": "❓・SUPORTE",
        "aliases": ["suporte", "ajuda", "central-de-ajuda"],
        "channels": [
            ("🤖・central-de-ajuda", "text", ["pergunte-a-ia", "suporte", "tickets"]),
        ],
    },
    {
        "name": "🛡️・STAFF",
        "aliases": ["staff", "equipe", "moderacao"],
        "channels": [
            ("🔒・chat-da-equipe", "text", ["staff-chat", "chat-equipe"]),
            ("📋・logs", "text", ["logs", "auditoria", "log-mod"]),
        ],
    },
]

CARGOS_PADRAO = [
    ("🛡️・Administrador", discord.Colour.dark_red()),
    ("🔨・Moderador", discord.Colour.orange()),
    ("🧪・Trial-Mod", discord.Colour.gold()),
    ("✅・Membro", discord.Colour.green()),
    ("🔔・Avisos", discord.Colour.blue()),
]


@dataclass
class InfraAction:
    kind: str  # create_category, rename_category, create_channel, move_channel, reorder
    description: str
    target_name: str
    obj_id: Optional[int] = None
    parent_name: Optional[str] = None
    risk: str = "safe"  # safe, review


class Infra(commands.Cog):
    """Gerencia a estrutura do servidor: canais, categorias e cargos básicos."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="infra_analisar", description="[MOD] Analisa a estrutura atual e propõe ajustes conforme o template.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def infra_analisar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        actions, notes = self._plan(interaction.guild)

        if not actions and not notes:
            return await interaction.edit_original_response(
                content="✅ A estrutura do servidor já está alinhada com o template. Nenhuma ação necessária."
            )

        embed = discord.Embed(
            title="🔍 Análise de Infraestrutura",
            description=f"**{len(actions)}** ação(ões) proposta(s). Nada foi alterado ainda.",
            color=discord.Color.blurple(),
        )

        safe = [a for a in actions if a.risk == "safe"]
        review = [a for a in actions if a.risk == "review"]

        if safe:
            linhas = "\n".join(f"• {a.description}" for a in safe[:10])
            if len(safe) > 10:
                linhas += f"\n_… e mais {len(safe) - 10}_"
            embed.add_field(name=f"🟢 Seguras ({len(safe)})", value=linhas[:1024], inline=False)

        if review:
            linhas = "\n".join(f"• {a.description}" for a in review[:10])
            if len(review) > 10:
                linhas += f"\n_… e mais {len(review) - 10}_"
            embed.add_field(name=f"🟡 Revisão ({len(review)})", value=linhas[:1024], inline=False)

        if notes:
            embed.add_field(name="⚠️ Avisos", value="\n".join(f"• {n}" for n in notes)[:1024], inline=False)

        embed.set_footer(text="Use /infra_aplicar para executar as mudanças aprovadas.")
        await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="infra_aplicar", description="[MOD] Aplica ações seguras do template de infraestrutura.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def infra_aplicar(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        actions, _ = self._plan(interaction.guild)
        safe_actions = [a for a in actions if a.risk == "safe"]

        if not safe_actions:
            return await interaction.edit_original_response(
                content="ℹ️ Nenhuma ação segura pendente. Use `/infra_analisar` para ver todas as propostas."
            )

        done, failed = await self._apply(interaction.guild, safe_actions)
        msg = f"**Concluído:** {len(done)} operação(ões).\n"
        msg += "\n".join(f"✅ {d}" for d in done[:15])
        if len(done) > 15:
            msg += f"\n_… e mais {len(done) - 15}_"
        if failed:
            msg += f"\n\n**Falhas ({len(failed)}):**\n" + "\n".join(f"⚠️ {f}" for f in failed[:10])

        await self.bot.db.log(interaction.user.id, "infra_aplicada", f"safe={len(done)} failed={len(failed)}")
        await interaction.edit_original_response(content=msg[:1900])

    @app_commands.command(name="infra_cargos", description="[MOD] Cria os cargos padrão ausentes no servidor.")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def infra_cargos(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        existing = {_norm(r.name) for r in guild.roles}
        missing = [(n, c) for n, c in CARGOS_PADRAO if _norm(n) not in existing]

        if not missing:
            return await interaction.edit_original_response(
                content="✅ Todos os cargos padrão já existem."
            )

        created = []
        for name, colour in missing:
            try:
                await guild.create_role(name=name, colour=colour, reason="Infra Colizeu: cargo padrão")
                created.append(name)
            except discord.HTTPException as e:
                log.warning("Falha ao criar cargo %s: %s", name, e)

        if created:
            await self.bot.db.log(interaction.user.id, "infra_cargos_criados", ", ".join(created))
            msg = f"✅ **{len(created)}** cargo(s) criado(s):\n" + "\n".join(f"• {c}" for c in created)
        else:
            msg = "⚠️ Nenhum cargo pôde ser criado. Verifique permissões e hierarquia."

        await interaction.edit_original_response(content=msg)

    # ------------------------------------------------------------------ Lógica interna
    def _plan(self, guild: discord.Guild) -> tuple[list[InfraAction], list[str]]:
        actions: list[InfraAction] = []
        notes: list[str] = []
        used_channels: set[int] = set()
        cat_map: dict[str, Optional[discord.CategoryChannel]] = {}

        all_categories = list(guild.categories)
        all_channels = [c for c in guild.channels if not isinstance(c, discord.CategoryChannel)]

        # 1. Mapear/Criar Categorias
        for spec in TEMPLATE_CATEGORIES:
            target = spec["name"]
            match = next((c for c in all_categories if _norm(c.name) == _norm(target)), None)
            if match is None:
                match = next(
                    (c for c in all_categories if any(_norm(c.name) == _norm(a) for a in spec["aliases"])),
                    None,
                )

            if match is None:
                actions.append(InfraAction("create_category", f"Criar categoria {target}", target))
                cat_map[target] = None
            else:
                cat_map[target] = match
                if _norm(match.name) != _norm(target):
                    actions.append(
                        InfraAction("rename_category", f"Renomear '{match.name}' → '{target}'", target, match.id)
                    )

        # 2. Mapear/Criar Canais
        for spec in TEMPLATE_CATEGORIES:
            cat_name = spec["name"]
            for ch_name, ch_type, aliases in spec["channels"]:
                candidates = [
                    c
                    for c in all_channels
                    if c.id not in used_channels
                    and (
                        (ch_type == "voice" and isinstance(c, (discord.VoiceChannel, discord.StageChannel)))
                        or (ch_type == "text" and isinstance(c, (discord.TextChannel, discord.ForumChannel)))
                    )
                ]
                match = next((c for c in candidates if _norm(c.name) == _norm(ch_name)), None)
                if match is None:
                    match = next(
                        (c for c in candidates if any(_norm(c.name) == _norm(a) for a in aliases)),
                        None,
                    )

                if match is None:
                    actions.append(
                        InfraAction("create_channel", f"Criar canal {ch_name} em {cat_name}", ch_name, parent_name=cat_name)
                    )
                else:
                    used_channels.add(match.id)
                    if _norm(match.name) != _norm(ch_name):
                        actions.append(
                            InfraAction("rename_channel", f"Renomear '{match.name}' → '{ch_name}'", ch_name, match.id)
                        )
                    target_cat = cat_map.get(cat_name)
                    if target_cat and match.category_id != target_cat.id:
                        actions.append(
                            InfraAction(
                                "move_channel",
                                f"Mover '{ch_name}' para '{cat_name}'",
                                ch_name,
                                match.id,
                                cat_name,
                                risk="review",
                            )
                        )

        # 3. Ordenação (sempre revisão pois muda posições)
        actions.append(InfraAction("reorder", "Ordenar categorias e canais conforme template", "structure", risk="review"))

        unmapped = [c for c in all_channels if c.id not in used_channels]
        if unmapped:
            notes.append(f"{len(unmapped)} canal(is) existente(s) não mapeado(s) serão preservados.")

        return actions, notes

    async def _apply(self, guild: discord.Guild, actions: list[InfraAction]) -> tuple[list[str], list[str]]:
        done: list[str] = []
        failed: list[str] = []
        created_cats: dict[str, discord.CategoryChannel] = {c.name: c for c in guild.categories}

        # Passo 1: Categorias
        for a in actions:
            if a.kind == "create_category":
                try:
                    cat = await guild.create_category(a.target_name, reason="Template Colizeu")
                    created_cats[a.target_name] = cat
                    done.append(a.description)
                except discord.HTTPException as e:
                    failed.append(f"{a.description}: {e.__class__.__name__}")
            elif a.kind == "rename_category":
                obj = guild.get_channel(a.obj_id)
                if isinstance(obj, discord.CategoryChannel):
                    try:
                        await obj.edit(name=a.target_name, reason="Template Colizeu")
                        created_cats[a.target_name] = obj
                        done.append(a.description)
                    except discord.HTTPException as e:
                        failed.append(f"{a.description}: {e.__class__.__name__}")

        # Passo 2: Canais
        for a in actions:
            if a.kind == "create_channel":
                cat = created_cats.get(a.parent_name)
                try:
                    await guild.create_text_channel(a.target_name, category=cat, reason="Template Colizeu")
                    done.append(a.description)
                except discord.HTTPException as e:
                    failed.append(f"{a.description}: {e.__class__.__name__}")
            elif a.kind == "rename_channel" and a.obj_id:
                obj = guild.get_channel(a.obj_id)
                if obj:
                    try:
                        await obj.edit(name=a.target_name, reason="Template Colizeu")
                        done.append(a.description)
                    except discord.HTTPException as e:
                        failed.append(f"{a.description}: {e.__class__.__name__}")

        return done, failed


async def setup(bot: commands.Bot):
    await bot.add_cog(Infra(bot))