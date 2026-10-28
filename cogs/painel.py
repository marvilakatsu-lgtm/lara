"""Painel central do Colizeu: interface por botões e formulários."""
import logging
import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("colizeu.painel")

# Cada ação aponta para a implementação já existente nos Cogs.
PAGES = {
    "Jogador": [
        ("Meu nível e XP", "Sentinela", "nivel"),
        ("Ranking de XP", "Sentinela", "ranking-xp"),
        ("Criar / abrir perfil", "Santuario", "meu_perfil"),
        ("Editar perfil", "Santuario", "editar_perfil"),
        ("Minhas conquistas", "Conquistas", "minhas_conquistas"),
        ("Registrar platina", "Conquistas", "platina"),
        ("Registrar jogo zerado", "Conquistas", "zerado"),
        ("Registrar run soulslike", "Soulslike", "run_registrar"),
        ("Ver jogos e desafios", "Soulslike", "run_listar"),
        ("Ranking soulslike", "Soulslike", "ranking_souls"),
        ("Buscar no catálogo", "Catalogo", "catalogo_buscar"),
        ("Ver catálogo", "Catalogo", "catalogo_listar"),
        ("Consultar ofertas", "Ofertas", "status_ofertas"),
        ("Status do YouTube", "YouTube", "status_youtube"),
        ("Perguntar ao suporte IA", "SuporteIA", "perguntar"),
    ],
    "Servidor": [
        ("Analisar estrutura", "Infra", "infra_analisar"),
        ("Aplicar estrutura analisada", "Infra", "infra_aplicar"),
        ("Criar cargos padrão", "Infra", "infra_cargos"),
        ("Publicar painel de verificação", "Verificacao", "painel_verificacao"),
        ("Publicar painel de cargos", "Verificacao", "painel_cargos"),
        ("Publicar painel de conquistas", "Conquistas", "painel_coliseu"),
        ("Publicar painel de moderação de runs", "Soulslike", "sl_painel_mod"),
    ],
    "Catálogo": [
        ("Adicionar jogo ou mod", "Catalogo", "catalogo_adicionar"),
        ("Remover item por ID", "Catalogo", "catalogo_remover"),
        ("Buscar itens", "Catalogo", "catalogo_buscar"),
        ("Listar itens", "Catalogo", "catalogo_listar"),
    ],
    "YouTube e ofertas": [
        ("Adicionar canal do YouTube", "YouTube", "yt_adicionar"),
        ("Listar canais monitorados", "YouTube", "yt_listar"),
        ("Status YouTube", "YouTube", "status_youtube"),
        ("Status de ofertas", "Ofertas", "status_ofertas"),
    ],
    "Administração": [
        ("Status geral do bot", "Core", "status"),
        ("Status do suporte IA", "SuporteIA", "status_ia"),
        ("Analisar estrutura", "Infra", "infra_analisar"),
        ("Aplicar estrutura", "Infra", "infra_aplicar"),
        ("Criar cargos padrão", "Infra", "infra_cargos"),
        ("Adicionar canal YouTube", "YouTube", "yt_adicionar"),
        ("Listar canais YouTube", "YouTube", "yt_listar"),
    ],
}

ADMIN_COMMANDS = {
    "infra_analisar", "infra_aplicar", "infra_cargos", "painel_verificacao",
    "painel_cargos", "painel_coliseu", "sl_painel_mod", "catalogo_adicionar",
    "catalogo_remover", "yt_adicionar", "yt_listar", "status_ia", "status_ofertas",
}
ROLE_ADMIN_COMMANDS = {"infra_cargos"}
CHANNEL_COMMANDS = {"painel_verificacao", "painel_cargos", "painel_coliseu", "sl_painel_mod"}


def is_admin(interaction: discord.Interaction, command_name: str) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    if not perms:
        return False
    if command_name in ROLE_ADMIN_COMMANDS:
        return perms.manage_roles or perms.administrator
    return perms.manage_guild or perms.administrator


class ActionModal(discord.ui.Modal):
    def __init__(self, panel: "PanelView", cog_name: str, command_name: str, command):
        super().__init__(title=panel.label_for(command_name)[:45], timeout=180)
        self.panel = panel
        self.cog_name = cog_name
        self.command_name = command_name
        self.command = command
        self.inputs = {}
        for param in command.parameters[:5]:
            # Channel options are handled by a channel selector, not a text field.
            if str(param.type) == "AppCommandOptionType.channel":
                continue
            label = (param.description or param.name.replace("_", " ")).strip()[:45] or param.name[:45]
            required = bool(param.required)
            field = discord.ui.TextInput(
                label=label,
                custom_id=param.name,
                required=required,
                max_length=1000 if param.name in {"bio", "descricao", "comentario", "pergunta"} else 200,
                placeholder=f"Informe {param.name.replace('_', ' ')}"[:100],
                style=discord.TextStyle.paragraph if param.name in {"bio", "descricao", "comentario", "pergunta"} else discord.TextStyle.short,
            )
            self.inputs[param.name] = (field, param)
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        kwargs = {}
        try:
            for name, (field, param) in self.inputs.items():
                value = str(field.value).strip()
                if not value and not param.required:
                    continue
                if str(param.type) == "AppCommandOptionType.integer":
                    value = int(value)
                elif str(param.type) == "AppCommandOptionType.number":
                    value = float(value)
                elif str(param.type) == "AppCommandOptionType.boolean":
                    value = value.lower() in {"sim", "true", "1", "yes"}
                kwargs[name] = value
            await self.panel.invoke(interaction, self.cog_name, self.command_name, kwargs)
        except ValueError:
            await interaction.response.send_message("Valor inválido. Confira os campos numéricos e tente novamente.", ephemeral=True)
        except Exception:
            log.exception("Falha ao executar ação do painel: %s", self.command_name)
            if not interaction.response.is_done():
                await interaction.response.send_message("Não foi possível executar essa ação. Consulte os logs do bot.", ephemeral=True)


class ChannelActionView(discord.ui.View):
    def __init__(self, panel: "PanelView", cog_name: str, command_name: str):
        super().__init__(timeout=120)
        self.panel = panel
        self.cog_name = cog_name
        self.command_name = command_name
        self.selected_channel = None
        self.channel_selector = discord.ui.ChannelSelect(
            placeholder="Selecione o canal de destino",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1, max_values=1,
        )
        self.channel_selector.callback = self.channel_selected
        self.add_item(self.channel_selector)

    async def channel_selected(self, interaction: discord.Interaction):
        self.selected_channel = self.channel_selector.values[0]
        await interaction.response.edit_message(
            content=f"Canal selecionado: {self.selected_channel.mention}. Clique em **Executar** para publicar o painel.",
            view=self,
        )

    @discord.ui.button(label="Executar", style=discord.ButtonStyle.success, row=1)
    async def execute(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_channel is None:
            return await interaction.response.send_message("Selecione um canal primeiro.", ephemeral=True)
        await self.panel.invoke(interaction, self.cog_name, self.command_name, {"canal": self.selected_channel})


def get_cog_command(cog, command_name: str):
    """Localiza um comando slash registrado em um Cog pelo nome público."""
    if cog is None:
        return None
    return next(
        (command for command in cog.get_app_commands() if command.name == command_name),
        None,
    )


class PanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot, owner_id: int, page: str = "home"):
        super().__init__(timeout=300)
        self.bot = bot
        self.owner_id = owner_id
        self.page = page
        self._build()

    def label_for(self, command_name: str) -> str:
        for items in PAGES.values():
            for label, _, cmd in items:
                if cmd == command_name:
                    return label
        return command_name.replace("_", " ").title()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Este painel pertence a outra pessoa. Use `/painel` para abrir o seu.", ephemeral=True)
            return False
        return True

    def _build(self):
        self.clear_items()
        if self.page == "home":
            for label, emoji in [("Jogador", "🎮"), ("Servidor", "🛠️"), ("Catálogo", "📚"), ("YouTube e ofertas", "📺"), ("Administração", "⚙️")]:
                if label in {"Servidor", "Catálogo", "YouTube e ofertas", "Administração"}:
                    perms = getattr(self.bot.get_guild(getattr(self.bot, "guild_id", 0)), "me", None)
                    # A autorização real é verificada novamente na execução; o menu não é uma barreira de segurança.
                btn = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.primary if label == "Jogador" else discord.ButtonStyle.secondary, row=0 if label in ("Jogador", "Servidor", "Catálogo") else 1)
                async def callback(interaction, selected=label):
                    perms = getattr(interaction.user, "guild_permissions", None)
                    if selected != "Jogador" and not (perms and (perms.manage_guild or perms.manage_roles or perms.administrator)):
                        return await interaction.response.send_message("Esta área exige permissões administrativas do servidor.", ephemeral=True)
                    self.page = selected
                    self._build()
                    await interaction.response.edit_message(embed=self.embed(), view=self)
                btn.callback = callback
                self.add_item(btn)
        else:
            actions = PAGES.get(self.page, [])
            for i, (label, cog_name, command_name) in enumerate(actions):
                btn = discord.ui.Button(label=label[:80], style=discord.ButtonStyle.primary if i < 2 else discord.ButtonStyle.secondary, row=i // 5)
                async def callback(interaction, cog=cog_name, cmd=command_name):
                    if cmd in ADMIN_COMMANDS and not is_admin(interaction, cmd):
                        return await interaction.response.send_message("Você não tem permissão para executar esta ação.", ephemeral=True)
                    await self.open_action(interaction, cog, cmd)
                btn.callback = callback
                self.add_item(btn)
            back = discord.ui.Button(label="⬅ Voltar ao painel", style=discord.ButtonStyle.danger, row=4)
            async def go_back(interaction):
                self.page = "home"
                self._build()
                await interaction.response.edit_message(embed=self.embed(), view=self)
            back.callback = go_back
            self.add_item(back)

    def embed(self):
        if self.page == "home":
            e = discord.Embed(title="Colizeu • Painel de Controle", description="Escolha uma área. As ações são executadas pelos botões e formulários abaixo; comandos separados não são necessários.", color=discord.Color.blurple())
            e.add_field(name="🎮 Jogador", value="Nível, rankings, perfil, conquistas, runs e suporte.", inline=False)
            e.add_field(name="🛠️ Administração", value="Estrutura do servidor, painéis, catálogo e integrações.", inline=False)
            e.set_footer(text="Ações administrativas exigem permissões do Discord.")
        else:
            e = discord.Embed(title=f"Colizeu • {self.page}", description="Selecione uma ação abaixo. Campos necessários serão solicitados em um formulário.", color=discord.Color.blurple())
            e.set_footer(text="Use Voltar ao painel para trocar de área.")
        return e

    async def open_action(self, interaction: discord.Interaction, cog_name: str, command_name: str):
        cog = self.bot.get_cog(cog_name)
        command = get_cog_command(cog, command_name)
        if command is None:
            return await interaction.response.send_message(f"A ação **{self.label_for(command_name)}** não está disponível neste momento.", ephemeral=True)
        params = command.parameters
        if command_name in CHANNEL_COMMANDS:
            view = ChannelActionView(self, cog_name, command_name)
            return await interaction.response.send_message(f"**{self.label_for(command_name)}**\nSelecione o canal de destino:", view=view, ephemeral=True)
        if params:
            modal = ActionModal(self, cog_name, command_name, command)
            return await interaction.response.send_modal(modal)
        await self.invoke(interaction, cog_name, command_name, {})

    async def invoke(self, interaction: discord.Interaction, cog_name: str, command_name: str, kwargs: dict):
        if command_name in ADMIN_COMMANDS and not is_admin(interaction, command_name):
            return await interaction.response.send_message("Você não tem permissão para executar esta ação.", ephemeral=True)
        cog = self.bot.get_cog(cog_name)
        command = get_cog_command(cog, command_name)
        if not command:
            return await interaction.response.send_message("A ação não está disponível.", ephemeral=True)
        # Reutiliza a lógica já existente nos módulos, sem registrar comandos slash adicionais.
        await command.callback(cog, interaction, **kwargs)


class Painel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="painel", description="Abre o painel interativo do Colizeu.")
    @app_commands.guild_only()
    async def painel(self, interaction: discord.Interaction):
        view = PanelView(self.bot, interaction.user.id)
        await interaction.response.send_message(embed=view.embed(), view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Painel(bot))
