"""Módulo Catálogo: Gestão de jogos e mods com busca e tags."""
import json
import discord
from discord import app_commands
from discord.ext import commands
import logging

log = logging.getLogger("colizeu.catalogo")


class Catalogo(commands.Cog):
    """Gerencia o catálogo de jogos e mods do servidor."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        log.info("Módulo Catálogo carregado.")

    # ------------------------------------------------------------------ Comandos Admin
    @app_commands.command(name="catalogo_adicionar", description="[MOD] Adiciona um jogo ou mod ao catálogo.")
    @app_commands.describe(
        nome="Nome do jogo/mod",
        descricao="Descrição breve",
        plataformas="Plataformas separadas por vírgula (ex: PC, PS5)",
        tags="Tags separadas por vírgula (ex: soulslike, rpg, mod)",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def catalogo_adicionar(
        self,
        interaction: discord.Interaction,
        nome: str,
        descricao: str,
        plataformas: str = "",
        tags: str = "",
    ):
        db = self.bot.db
        plat_list = [p.strip() for p in plataformas.split(",") if p.strip()]
        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]

        await db.conn.execute(
            "INSERT INTO cat_jogos(nome, descricao, plataformas, tags, adicionado_por) VALUES (?,?,?,?,?)",
            (
                nome.strip(),
                descricao.strip(),
                json.dumps(plat_list, ensure_ascii=False),
                json.dumps(tag_list, ensure_ascii=False),
                interaction.user.id,
            ),
        )
        await db.conn.commit()
        await db.log(interaction.user.id, "catalogo_adicionar", nome.strip())

        embed = discord.Embed(
            title="✅ Item Adicionado ao Catálogo",
            description=f"**{nome.strip()}** foi registrado com sucesso.",
            color=discord.Color.green(),
        )
        if descricao:
            embed.add_field(name="Descrição", value=descricao[:300], inline=False)
        if plat_list:
            embed.add_field(name="Plataformas", value=", ".join(plat_list), inline=True)
        if tag_list:
            embed.add_field(name="Tags", value=", ".join(tag_list), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="catalogo_remover", description="[MOD] Remove um item do catálogo pelo ID.")
    @app_commands.describe(item_id="ID do item no catálogo")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def catalogo_remover(self, interaction: discord.Interaction, item_id: int):
        db = self.bot.db
        row = await db._one("SELECT nome FROM cat_jogos WHERE id=?", (item_id,))
        if not row:
            return await interaction.response.send_message(
                "❌ Item não encontrado no catálogo.", ephemeral=True
            )

        await db.conn.execute("DELETE FROM cat_jogos WHERE id=?", (item_id,))
        await db.conn.commit()
        await db.log(interaction.user.id, "catalogo_remover", f"id={item_id} nome={row['nome']}")

        await interaction.response.send_message(
            f"✅ **{row['nome']}** removido do catálogo.", ephemeral=True
        )

    # ------------------------------------------------------------------ Consulta Pública
    @app_commands.command(name="catalogo_buscar", description="Busca jogos ou mods no catálogo.")
    @app_commands.describe(termo="Nome, tag ou parte da descrição para buscar")
    @app_commands.guild_only()
    async def catalogo_buscar(self, interaction: discord.Interaction, termo: str):
        db = self.bot.db
        like = f"%{termo.strip()}%"
        rows = await db._all(
            """SELECT id, nome, descricao, plataformas, tags FROM cat_jogos
               WHERE status='ativo' AND (
                   nome LIKE ? OR descricao LIKE ? OR tags LIKE ?
               ) ORDER BY nome LIMIT 10""",
            (like, like, like),
        )

        if not rows:
            return await interaction.response.send_message(
                f"🔍 Nenhum resultado encontrado para **{termo}**.", ephemeral=True
            )

        linhas = []
        for r in rows:
            try:
                tags = json.loads(r["tags"]) if r["tags"] else []
            except (json.JSONDecodeError, TypeError):
                tags = []
            tag_str = ", ".join(tags[:5]) if tags else "—"
            desc = (r["descricao"] or "Sem descrição.")[:120]
            linhas.append(f"`#{r['id']}` **{r['nome']}**\n_{desc}_\n🏷️ {tag_str}")

        embed = discord.Embed(
            title=f"🔍 Resultados para \"{termo}\"",
            description="\n\n".join(linhas),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"{len(rows)} resultado(s) encontrado(s)")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="catalogo_listar", description="Lista todos os itens do catálogo.")
    @app_commands.guild_only()
    async def catalogo_listar(self, interaction: discord.Interaction):
        db = self.bot.db
        rows = await db._all(
            "SELECT id, nome, plataformas FROM cat_jogos WHERE status='ativo' ORDER BY nome LIMIT 20"
        )

        if not rows:
            return await interaction.response.send_message(
                "📭 O catálogo está vazio. A equipe pode adicionar itens com `/catalogo_adicionar`.",
                ephemeral=True,
            )

        linhas = []
        for r in rows:
            try:
                plats = json.loads(r["plataformas"]) if r["plataformas"] else []
            except (json.JSONDecodeError, TypeError):
                plats = []
            plat_str = ", ".join(plats) if plats else "—"
            linhas.append(f"`#{r['id']}` **{r['nome']}** — {plat_str}")

        embed = discord.Embed(
            title="🎮 Catálogo de Jogos e Mods",
            description="\n".join(linhas),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Use /catalogo_buscar <termo> para pesquisar")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Catalogo(bot))