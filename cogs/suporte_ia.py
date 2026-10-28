"""Módulo Suporte IA: Central de Ajuda contextualizada com LLM."""
import asyncio
import logging
import time
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import config

log = logging.getLogger("colizeu.suporte_ia")

# Contexto estático do bot para injeção no prompt
BOT_CONTEXT = """
Você é o assistente oficial do servidor Colizeu. Seu papel é responder dúvidas sobre as funcionalidades do bot e regras do servidor.
NÃO responda perguntas fora deste escopo (política, religião, código externo, etc.). Recuse educadamente.

FUNCIONALIDADES DISPONÍVEIS:
- Gamificação: XP por mensagem (cooldown 60s), níveis, patentes (/nivel, /ranking-xp).
- Conquistas: todas as ações do usuário são feitas pelos botões do painel: Registrar platina (sujeita à aprovação), Registrar jogo zerado (registro automático, respeitando o limite diário) e Minhas conquistas (histórico). Não oriente usuários a digitar /platina, /zerado ou /minhas_conquistas.
- Soulslike: Speedruns com prova via DM (/run_registrar). Ranking por jogo/desafio (/ranking_souls).
- Santuário: Perfis pessoais em threads privadas (/meu_perfil, /editar_perfil).
- YouTube: Notificações de vídeos/lives. Adicionar canais: /yt_adicionar (MOD).
- Ofertas: Jogos grátis (GamerPower) e promoções Steam automáticas.
- Catálogo: Busca de jogos/mods (/catalogo_buscar). Mods adicionados por staff (/catalogo_adicionar).
- Verificação: Painel de regras e auto-cargos (/painel_verificacao, /painel_cargos).
- Infraestrutura: Reconciliação de canais (/infra_analisar, /infra_aplicar).

REGRAS IMPORTANTES:
- Platinas precisam de comprovante e aprovação da equipe.
- Runs precisam de vídeo/foto e tempo válido.
- O bot não responde DMs; use os canais públicos ou tickets.
- Seja conciso, útil e sempre em português.
"""


class SuporteIA(commands.Cog):
    """Integração com LLM para suporte contextualizado no canal de ajuda."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limits: dict[int, list[float]] = {}  # user_id -> [timestamps]

    async def cog_load(self):
        if not config.LLM_API_KEY:
            log.warning(
                "LLM_API_KEY não configurada. Módulo Suporte IA carregado mas inativo."
            )
            return
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {config.LLM_API_KEY}",
                "Content-Type": "application/json",
            }
        )
        log.info("Suporte IA carregado com modelo %s.", config.LLM_MODEL)

    async def cog_unload(self):
        if self.session and not self.session.closed:
            await self.session.close()

    # ------------------------------------------------------------------ Rate Limiting
    def _check_rate_limit(self, user_id: int) -> bool:
        """Retorna True se o usuário pode fazer uma pergunta agora."""
        agora = time.time()
        janela = 60.0  # 1 minuto
        max_reqs = config.LLM_RATE_LIMIT_PER_MIN

        timestamps = self._rate_limits.get(user_id, [])
        # Remover entradas antigas
        timestamps = [t for t in timestamps if agora - t < janela]
        self._rate_limits[user_id] = timestamps

        if len(timestamps) >= max_reqs:
            return False

        timestamps.append(agora)
        self._rate_limits[user_id] = timestamps
        return True

    # ------------------------------------------------------------------ Consulta LLM
    async def _ask_llm(self, pergunta: str, contexto_extra: str = "") -> Optional[str]:
        """Envia pergunta ao LLM e retorna a resposta ou None em caso de erro."""
        if not self.session or self.session.closed:
            return None

        system_prompt = BOT_CONTEXT
        if contexto_extra:
            system_prompt += f"\n\nCONTEXTO ADICIONAL DO SERVIDOR:\n{contexto_extra}"

        payload = {
            "model": config.LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pergunta},
            ],
            "max_tokens": 800,
            "temperature": 0.4,
        }

        try:
            async with self.session.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    log.error("LLM API erro %s: %s", resp.status, body[:300])
                    return None
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception:
            log.exception("Falha consultando LLM")
            return None

    async def _build_server_context(self, guild: discord.Guild) -> str:
        """Coleta dados dinâmicos do servidor para enriquecer o prompt."""
        db = self.bot.db
        lines = []

        # Contagens básicas
        users = await db._one("SELECT COUNT(*) as c FROM usr_users")
        conquistas = await db._one(
            "SELECT COUNT(*) as c FROM plat_conquistas WHERE status='approved'"
        )
        catalogo = await db._one(
            "SELECT COUNT(*) as c FROM cat_jogos WHERE status='ativo'"
        )

        lines.append(f"- Membros com progresso: {users['c'] if users else 0}")
        lines.append(
            f"- Conquistas aprovadas: {conquistas['c'] if conquistas else 0}"
        )
        lines.append(f"- Itens no catálogo: {catalogo['c'] if catalogo else 0}")

        # Canais configurados
        canal_mod = guild.get_channel(config.MOD_CHANNEL_ID)
        canal_perfis = guild.get_channel(config.PERFIS_CHANNEL_ID)
        if canal_mod:
            lines.append(f"- Canal de moderação: #{canal_mod.name}")
        if canal_perfis:
            lines.append(f"- Canal de santuários: #{canal_perfis.name}")

        return "\n".join(lines)

    # ------------------------------------------------------------------ Comando Público
    @app_commands.command(
        name="perguntar",
        description="Faça uma dúvida sobre o servidor ou funcionalidades do bot.",
    )
    @app_commands.describe(pergunta="Sua dúvida sobre o servidor, comandos ou regras")
    @app_commands.guild_only()
    async def perguntar(self, interaction: discord.Interaction, pergunta: str):
        if not config.LLM_API_KEY:
            return await interaction.response.send_message(
                "⚠️ O suporte por IA está desativado no momento. "
                "Abra um ticket ou fale com a equipe.",
                ephemeral=True,
            )

        if not self._check_rate_limit(interaction.user.id):
            return await interaction.response.send_message(
                f"⏳ Limite de {config.LLM_RATE_LIMIT_PER_MIN} perguntas por minuto atingido. "
                "Aguarde um momento.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=False, thinking=True)

        contexto = await self._build_server_context(interaction.guild)
        resposta = await self._ask_llm(pergunta, contexto)

        if resposta is None:
            await interaction.edit_original_response(
                content="❌ Não consegui obter uma resposta agora. Tente novamente em alguns instantes."
            )
            return

        # Log da interação
        await self.bot.db.log(
            interaction.user.id,
            "ia_pergunta",
            f"p={pergunta[:100]} r_len={len(resposta)}",
        )

        embed = discord.Embed(
            title="🤖 Central de Ajuda",
            description=resposta,
            color=discord.Color.blurple(),
        )
        embed.set_footer(
            text=f"Pergunta de {interaction.user.display_name} • Resposta gerada por IA"
        )

        await interaction.edit_original_response(embed=embed)

    # ------------------------------------------------------------------ Status Admin
    @app_commands.command(
        name="status_ia", description="[MOD] Verifica status da integração com IA."
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def status_ia(self, interaction: discord.Interaction):
        ativo = bool(config.LLM_API_KEY and self.session and not self.session.closed)
        embed = discord.Embed(title="🤖 Status Suporte IA", color=discord.Color.blurple())
        embed.add_field(name="Ativo", value="✅ Sim" if ativo else "❌ Não")
        embed.add_field(name="Modelo", value=config.LLM_MODEL or "Não configurado")
        embed.add_field(
            name="Rate Limit",
            value=f"{config.LLM_RATE_LIMIT_PER_MIN} req/min/usuário",
        )
        embed.add_field(
            name="API Key",
            value="✅ Configurada" if config.LLM_API_KEY else "❌ Ausente",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SuporteIA(bot))