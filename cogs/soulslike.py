"""Módulo Soulslike: Sistema de runs, desafios e Hall da Fama."""
import io
import re
import discord
from discord import app_commands
from discord.ext import commands
import logging
import config
from utils import get_text_channel

log = logging.getLogger("colizeu.soulslike")

JOGOS_PADRAO = ["Elden Ring", "Dark Souls", "Dark Souls II", "Dark Souls III", "Bloodborne", "Sekiro", "Lies of P"]
DESAFIOS_PADRAO = [
    ("Any%", "Zerar o jogo o mais rápido possível, sem restrições extras."),
    ("Nível 1", "Zerar o jogo sem subir de nível."),
    ("Sem tomar dano", "Zerar o jogo sem levar nenhum golpe (no-hit)."),
    ("Todos os chefes", "Derrotar todos os chefes do jogo."),
]
MIN_SEGUNDOS = 30
MAX_SEGUNDOS = 1000 * 3600
MEDALHAS = ["🥇", "🥈", "🥉"]


def parse_tempo(txt: str) -> int | None:
    """Aceita 1:30:45, 90:15, 1h30m45s, 1h30, 45m12s. Devolve segundos ou None."""
    t = txt.strip().lower().replace(" ", "")
    if not t:
        return None
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)(?:min|m))?(?:(\d+)s)?", t)
    if m and any(m.groups()):
        h, mi, s = (int(x or 0) for x in m.groups())
    elif (m := re.fullmatch(r"(\d+)h(\d{1,2})", t)):
        h, mi, s = int(m[1]), int(m[2]), 0
    elif re.fullmatch(r"\d+(:\d{1,2}){1,2}", t):
        p = [int(x) for x in t.split(":")]
        if len(p) == 2:
            h, mi, s = 0, p[0], p[1]
        else:
            h, mi, s = p
            if mi > 59:
                return None
        if s > 59:
            return None
    else:
        return None
    total = h * 3600 + mi * 60 + s
    return total if MIN_SEGUNDOS <= total <= MAX_SEGUNDOS else None


def fmt_tempo(seg: int) -> str:
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}"


class Soulslike(commands.Cog):
    """Gerencia submissão de runs, ranking e moderação de provas."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pending_uploads: dict[int, dict] = {}

    async def cog_load(self):
        db = self.bot.db
        for nome in JOGOS_PADRAO:
            await db.conn.execute("INSERT OR IGNORE INTO sl_games(name) VALUES (?)", (nome,))
        for nome, regras in DESAFIOS_PADRAO:
            await db.conn.execute("INSERT OR IGNORE INTO sl_challenges(name, rules) VALUES (?,?)", (nome, regras))
        await db.conn.commit()
        log.info("Soulslike carregado com %d jogos e %d desafios padrão.", len(JOGOS_PADRAO), len(DESAFIOS_PADRAO))

    # ------------------------------------------------------------------ Comandos
    @app_commands.command(name="run_registrar", description="Inicia o registro de uma run soulslike.")
    @app_commands.describe(jogo="Nome do jogo", desafio="Categoria do desafio")
    @app_commands.guild_only()
    async def run_registrar(self, interaction: discord.Interaction, jogo: str, desafio: str):
        db = self.bot.db
        g = await db._one("SELECT * FROM sl_games WHERE name=?", (jogo.strip(),))
        c = await db._one("SELECT * FROM sl_challenges WHERE name=?", (desafio.strip(),))
        if not g or not c:
            return await interaction.response.send_message(
                "❌ Jogo ou desafio não encontrado. Use `/run_listar` para ver as opções.", ephemeral=True
            )
        if interaction.user.id in self.pending_uploads:
            return await interaction.response.send_message(
                "⚠️ Você já tem um envio pendente. Conclua-o ou aguarde o timeout.", ephemeral=True
            )

        view = RunDadosModalView(self, g["id"], c["id"])
        await interaction.response.send_message(
            f"📝 **Registrar Run:** {g['name']} — {c['name']}\nPreencha os dados abaixo:",
            view=view, ephemeral=True
        )

    @app_commands.command(name="run_listar", description="Lista jogos e desafios disponíveis.")
    @app_commands.guild_only()
    async def run_listar(self, interaction: discord.Interaction):
        db = self.bot.db
        jogos = await db._all("SELECT name FROM sl_games ORDER BY name")
        desafios = await db._all("SELECT name, rules FROM sl_challenges ORDER BY name")

        linhas_jogos = "\n".join(f"• {r['name']}" for r in jogos) or "Nenhum."
        linhas_desafios = "\n".join(f"• **{r['name']}**\n_{r['rules'][:80]}_" if r['rules'] else f"• {r['name']}" for r in desafios) or "Nenhum."

        embed = discord.Embed(title="⚔️ Catálogo Soulslike", color=config.COR_PRATA)
        embed.add_field(name="🎮 Jogos", value=linhas_jogos[:1024], inline=True)
        embed.add_field(name="🏆 Desafios", value=linhas_desafios[:1024], inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ranking_souls", description="Exibe o top 10 de uma categoria.")
    @app_commands.describe(jogo="Nome do jogo", desafio="Categoria")
    @app_commands.guild_only()
    async def ranking_souls(self, interaction: discord.Interaction, jogo: str, desafio: str):
        db = self.bot.db
        g = await db._one("SELECT id, name FROM sl_games WHERE name=?", (jogo.strip(),))
        c = await db._one("SELECT id, name FROM sl_challenges WHERE name=?", (desafio.strip(),))
        if not g or not c:
            return await interaction.response.send_message("Jogo ou desafio não encontrado.", ephemeral=True)

        rows = await db._all(
            """SELECT r.user_id, r.seconds, r.build,
                      (SELECT COUNT(*) FROM sl_runs r2 WHERE r2.user_id=r.user_id AND r2.game_id=r.game_id
                       AND r2.challenge_id=r.challenge_id AND r2.status='approved') as vezes
               FROM sl_runs r
               WHERE r.status='approved' AND r.game_id=? AND r.challenge_id=?
                 AND r.id = (SELECT r3.id FROM sl_runs r3
                             WHERE r3.user_id=r.user_id AND r3.game_id=r.game_id
                               AND r3.challenge_id=r.challenge_id AND r3.status='approved'
                             ORDER BY r3.seconds ASC LIMIT 1)
               ORDER BY r.seconds ASC LIMIT 10""",
            (g["id"], c["id"])
        )

        if not rows:
            desc = "Ainda não há registros aprovados nesta categoria."
        else:
            linhas = []
            for i, r in enumerate(rows):
                pos = MEDALHAS[i] if i < 3 else f"`{i+1}.`"
                build = f" • {r['build']}" if r['build'] else ""
                vezes = f" • 🔁 {r['vezes']}x" if r['vezes'] > 1 else ""
                linhas.append(f"{pos} <@{r['user_id']}> — **{fmt_tempo(r['seconds'])}**{build}{vezes}")
            desc = "\n".join(linhas)

        embed = discord.Embed(
            title=f"⚔️ Ranking: {g['name']} — {c['name']}",
            description=desc,
            color=config.COR_OURO
        )
        embed.set_footer(text="Melhor tempo por jogador • Apenas runs aprovadas")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------ Moderação
    @app_commands.command(name="sl_painel_mod", description="[MOD] Publica painel de revisão de runs.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def sl_painel_mod(self, interaction: discord.Interaction, canal: discord.TextChannel):
        embed = discord.Embed(
            title="🛡️ Central de Moderação Soulslike",
            description="As runs submetidas aparecerão aqui com botões de Aprovar/Rejeitar.",
            color=config.COR_PRATA
        )
        try:
            msg = await canal.send(embed=embed)
            await interaction.response.send_message(f"✅ Painel publicado em {canal.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para enviar mensagens.", ephemeral=True)

    # ------------------------------------------------------------------ Listener DM
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is not None:
            return
        state = self.pending_uploads.get(message.author.id)
        if not state or not message.attachments:
            return

        att = message.attachments[0]
        ctype = (att.content_type or "").lower()
        is_media = ctype.startswith(("image/", "video/")) or att.filename.lower().endswith(
            (".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".webm")
        )
        if not is_media:
            return await message.channel.send("⚠️ Envie uma imagem ou vídeo como comprovante.")
        if att.size > 20 * 1024 * 1024:
            return await message.channel.send("⚠️ Arquivo excede 20MB.")

        try:
            data = await att.read()
            await self._enviar_moderacao(message.author, state, data, att.filename[:100])
            self.pending_uploads.pop(message.author.id, None)
        except Exception as e:
            log.exception("Erro processando prova DM: %s", e)
            await message.channel.send("❌ Falha ao processar. Tente novamente pelo comando.")

    async def _enviar_moderacao(self, user: discord.User, state: dict, data: bytes, filename: str):
        db = self.bot.db
        canal = await get_text_channel(self.bot, config.MOD_CHANNEL_ID)
        if not canal:
            return

        cur = await db.conn.execute(
            "INSERT INTO sl_runs(user_id, game_id, challenge_id, build, seconds) VALUES (?,?,?,?,?)",
            (user.id, state['game_id'], state['challenge_id'], state['build'], state['seconds'])
        )
        await db.conn.commit()
        run_id = cur.lastrowid

        g = await db._one("SELECT name FROM sl_games WHERE id=?", (state['game_id'],))
        c = await db._one("SELECT name FROM sl_challenges WHERE id=?", (state['challenge_id'],))

        embed = discord.Embed(title="⚔️ Nova Run para Análise", color=config.COR_PRATA)
        embed.add_field(name="Membro", value=user.mention)
        embed.add_field(name="Jogo", value=g["name"])
        embed.add_field(name="Desafio", value=c["name"])
        embed.add_field(name="Tempo", value=fmt_tempo(state['seconds']))
        embed.add_field(name="Build", value=state['build'] or "Não informada")
        if filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text=f"SL:{run_id}")

        try:
            msg = await canal.send(embed=embed, file=discord.File(io.BytesIO(data), filename=filename))
            await db.conn.execute("UPDATE sl_runs SET proof_msg_id=?, proof_url=? WHERE id=?",
                                  (msg.id, msg.embeds[0].image.url if msg.embeds else "", run_id))
            await db.conn.commit()
            await user.send(f"✅ Sua run `#{run_id}` foi enviada para moderação!")
        except discord.HTTPException as e:
            log.error("Falha enviando para moderação: %s", e)
            await user.send("❌ Falha ao enviar para moderação. Contate a equipe.")


class RunDadosModalView(discord.ui.View):
    def __init__(self, cog: Soulslike, game_id: int, challenge_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.game_id = game_id
        self.challenge_id = challenge_id

    @discord.ui.button(label="Preencher Dados", style=discord.ButtonStyle.primary)
    async def abrir_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RunModal(self.cog, self.game_id, self.challenge_id))


class RunModal(discord.ui.Modal, title="Dados da Run"):
    tempo = discord.ui.TextInput(label="Tempo (ex: 1:30:45)", placeholder="1h30m45s ou 90:15")
    build = discord.ui.TextInput(label="Build/Arma (opcional)", required=False, default="Não informada")

    def __init__(self, cog: Soulslike, game_id: int, challenge_id: int):
        super().__init__()
        self.cog = cog
        self.game_id = game_id
        self.challenge_id = challenge_id

    async def on_submit(self, interaction: discord.Interaction):
        seg = parse_tempo(str(self.tempo))
        if seg is None:
            return await interaction.response.send_message(
                "❌ Formato inválido. Use `1:30:45`, `1h30m` ou `90:15`.", ephemeral=True
            )

        self.cog.pending_uploads[interaction.user.id] = {
            'game_id': self.game_id,
            'challenge_id': self.challenge_id,
            'seconds': seg,
            'build': str(self.build).strip() or "Não informada"
        }

        try:
            dm = await interaction.user.create_dm()
            await dm.send(
                f"📸 **Etapa Final:** Envie agora a imagem/vídeo comprovante desta run nesta DM.\n"
                f"Tempo registrado: `{fmt_tempo(seg)}`"
            )
            await interaction.response.send_message(
                "✅ Dados salvos! Verifique suas **DMs** para enviar o comprovante.", ephemeral=True
            )
        except discord.Forbidden:
            self.cog.pending_uploads.pop(interaction.user.id, None)
            await interaction.response.send_message(
                "❌ Não consigo enviar DMs para você. Ative-as e tente novamente.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Soulslike(bot))