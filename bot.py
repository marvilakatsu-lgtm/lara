from __future__ import annotations
import os, re, json, logging, unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN', '').strip()
GUILD_ID = int(os.getenv('GUILD_ID', '0') or 0)
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('quasepro-organizer')

# O template evita apagar recursos. Canais e categorias são reconciliados por nome/alias,
# mas mensagens, tópicos, IDs de canais e dados dos bots não são recriados nem apagados.
CATEGORIES = [
    {'name':'📌・COMECE-AQUI','aliases':['BEM-VINDO','BEM VINDO','COMECE-AQUI','COMECE AQUI'], 'channels':[
        ('👋・boas-vindas','text',['boas-vindas','boas vindas']),('📜・regras','text',['regras']),('✅・verificação','text',['verificação','verificacao']),('🎭・cargos','text',['escolha-seus-cargos','escolha seus cargos','cargos']),('📚・guia-do-servidor','text',['guia-do-servidor','guia do servidor'])]},
    {'name':'🎬・QUASE-PRO','aliases':['QUASE-PRO','QUASE PRO','CRIADOR','BEM-VINDO'], 'channels':[
        ('📢・anúncios','text',['anúncios','anuncios']),('🎥・novos-vídeos','text',['novos-vídeos','novos videos','novos-videos']),('🔴・lives','text',['lives','live']),('💡・sugestões-de-vídeos','text',['sugestões-de-vídeos','sugestões','sugestoes']),('🗳️・votações','text',['votações','votacoes'])]},
    {'name':'💬・COMUNIDADE','aliases':['COMUNIDADE'], 'channels':[
        ('💬・bate-papo','text',['bate-papo','bate papo']),('👤・apresentações','text',['apresentações','apresentacoes']),('😂・memes','text',['memes']),('🎮・outros-jogos','text',['outros-jogos','outros jogos']),('🤝・procurando-jogadores','text',['procura-de-jogadores','procurando-jogadores','procura de jogadores'])]},
    {'name':'⚔️・UNIVERSO-SOULSLIKE','aliases':['UNIVERSO-SOULSLIKE','UNIVERSO SOULSLIKE'], 'channels':[
        ('🌑・elden-ring','text',['elden-ring','elden ring']),('💀・dark-souls','text',['dark-souls','dark souls']),('🩸・bloodborne','text',['bloodborne']),('🥷・sekiro','text',['sekiro']),('🔥・runs-e-desafios','text',['runs-e-desafios','runs e desafios'])]},
    {'name':'🏆・SISTEMAS-SOULSBOT','aliases':['SISTEMAS-SOULSBOT','SISTEMAS SOULSBOT'], 'channels':[
        ('🏆・coliseu','text',['coliseu','colizeu','hall-do-coliseu','hall do coliseu']),('📊・ranking-de-zerados','text',['ranking-de-zerados','ranking de zerados','zerados']),('💎・platinas','text',['platinas']),('👤・perfis-e-patentes','text',['perfis-e-patentes','perfis e patentes','perfis']),('⛩️・santuários','text',['santuários','santuarios','santuário','santuario'])]},
    {'name':'🤖・CATÁLOGO-E-OFERTAS','aliases':['CATÁLOGO-E-OFERTAS','CATALOGO-E-OFERTAS'], 'channels':[
        ('🎮・catálogo-de-jogos','text',['catálogo-de-jogos','catalogo-de-jogos','catálogo de jogos']),('🧩・catálogo-de-mods','text',['catálogo-de-mods','catalogo-de-mods','ports-e-mods','mods']),('📰・notícias-gamer','text',['notícias-gamer','novidades-e-lançamentos','noticias gamer','novidades e lançamentos']),('🆓・jogos-grátis','text',['jogos-grátis','jogos-gratis']),('💸・promoções','text',['promoções','promocoes-gamer','promocoes','promoções gamer'])]},
    {'name':'🔊・CANAIS-DE-VOZ','aliases':['VOZ','CANAIS-DE-VOZ','CANAIS DE VOZ'], 'channels':[
        ('💬・papo-livre','voice',['papo-livre','papo livre']),('🎮・coop-souls','voice',['coop-souls','coop souls']),('⚔️・arena-pvp','voice',['invasoes-e-pvp','invasões-e-pvp','arena-pvp','arena pvp']),('🎮・outros-jogos','voice',['outros jogos','outros-jogos']),('😴・afk','voice',['afk'])]},
    {'name':'🛡️・EQUIPE','aliases':['STAFF','EQUIPE'], 'channels':[
        ('🔒・chat-da-equipe','text',['staff-chat','chat-da-equipe','chat da equipe']),('📋・logs-de-moderação','text',['logs-moderação','logs-de-moderação','logs moderacao']),('🤖・comandos-de-bots','text',['comandos-bot','comandos-de-bots','comandos bot']),('📅・reunião-da-equipe','voice',['reunião staff','reuniao staff','reunião-da-equipe'])]},
    {'name':'❓・CENTRAL-DE-AJUDA','aliases':['CENTRAL-DE-AJUDA','CENTRAL DE AJUDA'], 'channels':[
        ('🤖・pergunte-à-ia','text',['pergunte-à-ia','pergunte a ia','pergunte-à-ia']),]},
]

# Cargos propostos são apenas criados se ausentes. Cargos de progressão do Soulsbot são intencionalmente omitidos.
ROLES = [
    ('🛡️・Administrador', discord.Colour.dark_red()),
    ('🔨・Moderador', discord.Colour.orange()),
    ('🧪・Trial-Mod', discord.Colour.gold()),
    ('✅・Membro', discord.Colour.green()),
    ('🎬・Quase-Pro', discord.Colour.blurple()),
    ('🔔 Avisos de Vídeo', discord.Colour.blue()),
    ('🔴 Avisos de Live', discord.Colour.red()),
    ('🌑・Elden Ring', discord.Colour.dark_purple()),
    ('💀・Dark Souls', discord.Colour.dark_grey()),
    ('🩸・Bloodborne', discord.Colour.red()),
    ('🥷・Sekiro', discord.Colour.dark_teal()),
    ('🤝・Procurando Co-op', discord.Colour.green()),
]

# Categorias privadas por jogo. O cargo correspondente controla a visibilidade.
GAME_CATEGORIES = [
    {
        "role": "🌑・Elden Ring", "category": "🌑・ELDEN RING", "colour": discord.Colour.dark_purple(),
        "channels": [
            ("💬・geral", "text"), ("🛠️・builds-e-equipamentos", "text"),
            ("👑・chefes-e-estratégias", "text"), ("🗺️・dicas-e-localizações", "text"),
            ("🌳・shadow-of-the-erdtree", "text"), ("📸・clips-e-screenshots", "text"),
        ],
    },
    {
        "role": "🔥・Dark Souls I", "category": "🔥・DARK SOULS I", "colour": discord.Colour.dark_grey(),
        "channels": [("💬・geral", "text"), ("🛠️・builds-e-equipamentos", "text"), ("👑・chefes-e-segredos", "text"), ("📸・clips-e-screenshots", "text")],
    },
    {
        "role": "⚔️・Dark Souls II", "category": "⚔️・DARK SOULS II", "colour": discord.Colour.dark_grey(),
        "channels": [("💬・geral", "text"), ("🛠️・builds-e-equipamentos", "text"), ("👑・chefes-e-exploração", "text"), ("📸・clips-e-screenshots", "text")],
    },
    {
        "role": "🛡️・Dark Souls III", "category": "🛡️・DARK SOULS III", "colour": discord.Colour.dark_grey(),
        "channels": [("💬・geral", "text"), ("🛠️・builds-e-equipamentos", "text"), ("👑・chefes-e-estratégias", "text"), ("📸・clips-e-screenshots", "text")],
    },
    {
        "role": "🩸・Bloodborne", "category": "🩸・BLOODBORNE", "colour": discord.Colour.red(),
        "channels": [("💬・geral", "text"), ("🗡️・armas-e-builds", "text"), ("🩸・chefes-e-segredos", "text"), ("📸・clips-e-screenshots", "text")],
    },
    {
        "role": "⚙️・Lies of P", "category": "⚙️・LIES OF P", "colour": discord.Colour.gold(),
        "channels": [("💬・geral", "text"), ("⚔️・armas-e-combinações", "text"), ("👑・chefes-e-estratégias", "text"), ("📸・clips-e-screenshots", "text")],
    },
    {
        "role": "🌋・Outros Soulslikes", "category": "🌋・OUTROS SOULSLIKES", "colour": discord.Colour.green(),
        "channels": [("💬・geral", "text"), ("🎮・qual-jogo-jogar", "text"), ("🛠️・builds-e-dicas", "text"), ("📸・clips-e-screenshots", "text")],
    },
]

PROTECTED_NAME_PARTS = ('santuário','santuario','coliseu','colizeu','platina','ranking','patente','zerado','runs-e-desafios','novos-vídeos','novos-videos','lives','catálogo','catalogo','moderação','moderacao')

def norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode('ascii').lower()
    s = re.sub(r'<a?:[^:]+:\d+>', '', s)
    s = re.sub(r'[^a-z0-9]+','-',s).strip('-')
    return s

def same_name(a: str, b: str) -> bool:
    return norm(a) == norm(b)

def matches_alias(name: str, aliases: list[str]) -> bool:
    n = norm(name)
    return any(n == norm(a) or n.endswith('-'+norm(a)) or norm(a).endswith('-'+n) for a in aliases)

@dataclass
class Action:
    kind: str
    description: str
    data: dict
    risk: str = 'safe'

class Planner:
    def __init__(self, guild: discord.Guild):
        self.guild = guild
        self.actions: list[Action] = []
        self.notes: list[str] = []

    def plan(self):
        used_channels: set[int] = set()
        category_matches: dict[str, Optional[discord.CategoryChannel]] = {}
        categories = list(self.guild.categories)
        for spec in CATEGORIES:
            target = spec['name']
            current = next((c for c in categories if same_name(c.name, target)), None)
            if current is None:
                current = next((c for c in categories if matches_alias(c.name, spec['aliases'])), None)
            if current is None:
                self.actions.append(Action('create_category', f'Criar categoria {target}', {'name':target}))
                category_matches[target] = None
            else:
                category_matches[target] = current
                if current.name != target:
                    # Não renomear BEM-VINDO para duas categorias distintas: isso seria ambíguo.
                    if norm(current.name) == norm('BEM-VINDO') and target == '🎬・QUASE-PRO':
                        self.notes.append('A categoria BEM-VINDO não será reaproveitada para QUASE-PRO; será criada uma categoria nova.')
                        category_matches[target] = None
                        self.actions.append(Action('create_category', f'Criar categoria {target}', {'name':target}))
                    else:
                        self.actions.append(Action('rename_category', f'Renomear categoria {current.name} → {target}', {'id':current.id,'name':target}))

        all_channels = [c for c in self.guild.channels if not isinstance(c, discord.CategoryChannel)]
        # Cada canal existente pode ser associado no máximo uma vez.
        for spec in CATEGORIES:
            cat_name = spec['name']
            for target_name, kind, aliases in spec['channels']:
                candidates = [c for c in all_channels if c.id not in used_channels and not isinstance(c, discord.CategoryChannel) and ((kind == 'voice' and isinstance(c, (discord.VoiceChannel, discord.StageChannel))) or (kind == 'text' and isinstance(c, (discord.TextChannel, discord.ForumChannel))))]
                match = next((c for c in candidates if same_name(c.name, target_name)), None)
                if match is None:
                    match = next((c for c in candidates if matches_alias(c.name, aliases)), None)
                if match is None:
                    # Do not duplicate channels that are mapped to another feature/category.
                    self.actions.append(Action('create_channel', f'Criar canal {target_name} em {cat_name}', {'name':target_name,'kind':kind,'category':cat_name}))
                    continue
                used_channels.add(match.id)
                if match.name != target_name:
                    self.actions.append(Action('rename_channel', f'Renomear canal {match.name} → {target_name}', {'id':match.id,'name':target_name}, 'review' if any(p in norm(match.name) for p in PROTECTED_NAME_PARTS) else 'safe'))
                target_cat = category_matches.get(cat_name)
                if target_cat is None or match.category_id != target_cat.id:
                    # Movimentar canais é sempre classificado como revisão: permissões herdadas podem mudar.
                    self.actions.append(Action('move_channel', f'Mover {target_name} para {cat_name}', {'id':match.id,'category':cat_name}, 'review'))

        # A ordem faz parte do template: primeiro as categorias na ordem definida
        # em CATEGORIES e depois os canais na ordem declarada em cada categoria.
        # A operação não apaga nem recria canais; apenas ajusta posições.
        self.actions.append(Action(
            'reorder_structure',
            'Ordenar categorias e canais conforme o modelo Quase-Pro',
            {},
            'review',
        ))

        # Existing channels not mapped by template are preserved, not deleted.
        unmapped = [c for c in all_channels if c.id not in used_channels]
        if unmapped:
            self.notes.append(f'{len(unmapped)} canal(is) não mapeado(s) serão preservados. Verifique-os manualmente antes de remover qualquer coisa.')
        return self.actions, self.notes

class ConfirmView(discord.ui.View):
    def __init__(self, owner_id: int, actions: list[Action], *, only_safe: bool = False):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.actions = actions
        self.only_safe = only_safe
        self.add_item(ApplyButton())
        self.add_item(CancelButton())
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('Este painel pertence a outra pessoa.', ephemeral=True)
            return False
        if not isinstance(interaction.user, discord.Member) or not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message('Você precisa da permissão **Gerenciar servidor** para usar este painel.', ephemeral=True)
            return False
        return True

class ApplyButton(discord.ui.Button):
    def __init__(self): super().__init__(label='Aplicar mudanças aprovadas', style=discord.ButtonStyle.success, row=0)
    async def callback(self, interaction: discord.Interaction):
        view: ConfirmView = self.view  # type: ignore
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await apply_actions(interaction.guild, view.actions, include_review=not view.only_safe)
        await interaction.followup.send(result, ephemeral=True)
        view.stop()

class CancelButton(discord.ui.Button):
    def __init__(self): super().__init__(label='Cancelar', style=discord.ButtonStyle.secondary, row=0)
    async def callback(self, interaction: discord.Interaction):
        view: ConfirmView = self.view  # type: ignore
        await interaction.response.edit_message(content='Operação cancelada. Nenhuma alteração foi aplicada.', embed=None, view=None)
        view.stop()

class MainPanel(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=300)
        self.owner_id = owner_id
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('Abra seu próprio `/painel` para administrar o servidor.', ephemeral=True); return False
        if not isinstance(interaction.user, discord.Member) or not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message('Você precisa da permissão **Gerenciar servidor**.', ephemeral=True); return False
        return True
    @discord.ui.button(label='Analisar servidor', emoji='🔎', style=discord.ButtonStyle.primary, row=0)
    async def audit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        g = interaction.guild
        if g is None: return
        plan = Planner(g); actions, notes = plan.plan()
        embed = make_plan_embed(g, actions, notes)
        view = ConfirmView(self.owner_id, actions)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    @discord.ui.button(label='Aplicar apenas ações seguras', emoji='🛡️', style=discord.ButtonStyle.success, row=0)
    async def safe_apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        g = interaction.guild
        if g is None: return
        plan = Planner(g); actions, notes = plan.plan()
        safe = [a for a in actions if a.risk == 'safe' and a.kind in ('create_category','rename_category','create_channel','rename_channel')]
        embed = make_plan_embed(g, safe, notes, title='Prévia: ações seguras')
        await interaction.followup.send(embed=embed, view=ConfirmView(self.owner_id, safe, only_safe=True), ephemeral=True)
    @discord.ui.button(label='Criar cargos básicos ausentes', emoji='🎭', style=discord.ButtonStyle.secondary, row=1)
    async def roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = interaction.guild
        if g is None: return
        existing = {norm(r.name) for r in g.roles}
        missing = [(n,c) for n,c in ROLES if norm(n) not in existing]
        if not missing:
            await interaction.response.send_message('Os cargos básicos sugeridos já existem. Nenhum cargo foi criado.', ephemeral=True); return
        desc = '\n'.join(f'• {n}' for n,_ in missing)
        embed = discord.Embed(title='Prévia de cargos', description=f'Vou criar somente estes cargos ausentes, sem conceder permissões administrativas automaticamente:\n\n{desc}\n\nA hierarquia e as permissões devem ser revisadas depois.', color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, view=RoleConfirmView(self.owner_id, missing), ephemeral=True)
    @discord.ui.button(label='Configurar categorias privadas por jogo', emoji='🎮', style=discord.ButtonStyle.primary, row=2)
    async def game_access(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message('Servidor não encontrado.', ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not (interaction.user.guild_permissions.manage_roles and interaction.user.guild_permissions.manage_channels or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message('O bot precisa das permissões **Gerenciar cargos** e **Gerenciar canais**; você precisa ter essas permissões para executar esta configuração.', ephemeral=True)
            return
        embed = discord.Embed(
            title='🎮 Categorias privadas por jogo',
            description=(
                'Vou preparar sete categorias privadas, criar os cargos de jogos ausentes e configurar as permissões para que cada membro veja apenas os jogos que selecionou.\n\n'
                '**Segurança:** canais existentes não serão apagados. Canais novos serão criados quando necessário; os canais antigos não serão movidos automaticamente nesta etapa.\n\n'
                'A execução exige que o cargo do bot esteja acima dos cargos de jogos que ele gerenciará.'
            ), color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, view=GameSetupConfirmView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label='Ajuda e segurança', emoji='ℹ️', style=discord.ButtonStyle.secondary, row=1)
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title='Como este organizador funciona', description='• Um único comando: `/painel`.\n• Nenhum canal ou cargo é apagado automaticamente.\n• As alterações são mostradas antes da execução.\n• Movimentações de canais são classificadas como revisão porque podem alterar permissões herdadas.\n• O botão de categorias privadas configura permissões por cargo de jogo.\n• Mensagens, IDs e bancos de dados dos bots existentes não são recriados.\n• A permissão Gerenciar servidor é exigida.', color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RoleConfirmView(discord.ui.View):
    def __init__(self, owner_id: int, missing):
        super().__init__(timeout=180); self.owner_id=owner_id; self.missing=missing
    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('Este painel pertence a outra pessoa.', ephemeral=True); return False
        return isinstance(interaction.user, discord.Member) and (interaction.user.guild_permissions.manage_roles or interaction.user.guild_permissions.administrator)
    @discord.ui.button(label='Criar cargos', style=discord.ButtonStyle.success)
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        g=interaction.guild; made=[]; failed=[]
        try:
            for name, colour in self.missing:
                try:
                    if discord.utils.get(g.roles, name=name): continue
                    await g.create_role(name=name, colour=colour, reason=f'Organizador Quase-Pro: aprovado por {interaction.user}')
                    made.append(name)
                except discord.HTTPException as e: failed.append(f'{name}: {e.__class__.__name__}')
        except Exception: log.exception('Erro criando cargos')
        msg = f'**Criados ({len(made)}):** ' + (', '.join(made) if made else 'nenhum')
        if failed: msg += '\n**Falhas:** ' + '; '.join(failed)
        msg += '\n\nNenhuma permissão administrativa foi concedida automaticamente.'
        await interaction.followup.send(msg, ephemeral=True); self.stop()
    @discord.ui.button(label='Cancelar', style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content='Cancelado. Nenhum cargo foi criado.', embed=None, view=None); self.stop()

class GameSetupConfirmView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('Este painel pertence a outra pessoa.', ephemeral=True)
            return False
        if not isinstance(interaction.user, discord.Member) or not (interaction.user.guild_permissions.administrator or (interaction.user.guild_permissions.manage_roles and interaction.user.guild_permissions.manage_channels)):
            await interaction.response.send_message('Você precisa de Gerenciar cargos e Gerenciar canais.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Criar e configurar categorias', style=discord.ButtonStyle.success)
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message('Servidor não encontrado.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        made_roles, made_categories, made_channels, secured, failed = [], [], [], [], []
        bot_member = guild.me
        try:
            for spec in GAME_CATEGORIES:
                role = discord.utils.get(guild.roles, name=spec['role'])
                if role is None:
                    try:
                        role = await guild.create_role(name=spec['role'], colour=spec['colour'], reason='Configuração de categorias privadas por jogo')
                        made_roles.append(role.name)
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        failed.append(f"Cargo {spec['role']}: {type(exc).__name__}")
                        continue

                # Negar a visualização a @everyone; permitir ao cargo do jogo, equipe autorizada e bot.
                overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=True, add_reactions=True, connect=True, speak=True)
                for staff_role in guild.roles:
                    perms = staff_role.permissions
                    if staff_role != guild.default_role and (perms.administrator or perms.manage_guild or perms.manage_channels):
                        overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=True, manage_channels=perms.manage_channels)
                if bot_member is not None:
                    overwrites[bot_member] = discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=True, manage_channels=True, manage_roles=True)

                category = discord.utils.get(guild.categories, name=spec['category'])
                if category is None:
                    try:
                        category = await guild.create_category(spec['category'], overwrites=overwrites, reason='Criar categoria privada para cargo de jogo')
                        made_categories.append(category.name)
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        failed.append(f"Categoria {spec['category']}: {type(exc).__name__}")
                        continue
                else:
                    try:
                        await category.edit(overwrites=overwrites, reason='Aplicar acesso privado por cargo de jogo')
                        secured.append(category.name)
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        failed.append(f"Permissões {spec['category']}: {type(exc).__name__}")

                for channel_name, kind in spec['channels']:
                    # Reutilizar somente canal com nome exato dentro desta categoria; não mover canais existentes automaticamente.
                    existing = next((c for c in category.channels if norm(c.name) == norm(channel_name)), None)
                    if existing is not None:
                        continue
                    try:
                        if kind == 'voice':
                            await guild.create_voice_channel(channel_name, category=category, reason='Criar canal da categoria privada de jogo')
                        else:
                            await guild.create_text_channel(channel_name, category=category, reason='Criar canal da categoria privada de jogo')
                        made_channels.append(f'{category.name} / {channel_name}')
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        failed.append(f"Canal {channel_name} em {category.name}: {type(exc).__name__}")

            # Publicar/atualizar painel de seleção no canal 🎭・cargos ou alias conhecido.
            roles_channel = next((c for c in guild.text_channels if norm(c.name) in {norm('🎭・cargos'), norm('escolha-seus-cargos'), norm('cargos')}), None)
            panel_status = 'Painel não publicado: canal 🎭・cargos não encontrado.'
            if roles_channel is not None:
                panel_embed = discord.Embed(
                    title='🎮 Escolha seus jogos',
                    description='Selecione um ou mais jogos para receber os cargos correspondentes. A seleção adiciona cargos sem remover os que você já possui. Use o botão abaixo para remover todos os seus cargos de jogos, se desejar.',
                    color=discord.Color.blurple())
                try:
                    async for msg in roles_channel.history(limit=50):
                        if msg.author == guild.me and msg.embeds and msg.embeds[0].title == '🎮 Escolha seus jogos':
                            await msg.edit(embed=panel_embed, view=GameRoleSelectView())
                            panel_status = f'Painel de seleção atualizado em {roles_channel.mention}.'
                            break
                    else:
                        await roles_channel.send(embed=panel_embed, view=GameRoleSelectView())
                        panel_status = f'Painel de seleção publicado em {roles_channel.mention}.'
                except (discord.Forbidden, discord.HTTPException) as exc:
                    panel_status = f'Não foi possível publicar o painel: {type(exc).__name__}. Verifique Enviar mensagens, Incorporar links e Ler histórico.'

        except Exception:
            log.exception('Falha inesperada ao configurar categorias de jogos')
            failed.append('Falha inesperada; consulte o log do bot.')

        summary = [f'**Cargos criados ({len(made_roles)}):** ' + (', '.join(made_roles) if made_roles else 'nenhum'),
                   f'**Categorias criadas ({len(made_categories)}):** ' + (', '.join(made_categories) if made_categories else 'nenhuma'),
                   f'**Categorias privadas configuradas ({len(secured)}):** ' + (', '.join(secured) if secured else 'nenhuma'),
                   f'**Canais criados ({len(made_channels)}):** ' + (', '.join(made_channels[:8]) if made_channels else 'nenhum'), panel_status]
        if len(made_channels) > 8: summary.append(f'… e mais {len(made_channels)-8} canais.')
        if failed: summary.append('**Falhas:**\n' + '\n'.join('⚠️ '+x for x in failed[:8]))
        summary.append('\nCanais existentes fora dessas categorias não foram movidos nem apagados. Verifique a hierarquia do cargo do bot e teste o acesso com uma conta comum.')
        await interaction.followup.send('\n'.join(summary)[:1900], ephemeral=True)
        self.stop()

    @discord.ui.button(label='Cancelar', style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content='Cancelado. Nenhuma categoria de jogo foi configurada.', embed=None, view=None)
        self.stop()

class GameRoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GameRoleSelect())
        self.add_item(ClearGameRolesButton())

class GameRoleSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=spec['role'].split('・', 1)[-1], value=spec['role'], emoji=spec['role'][0]) for spec in GAME_CATEGORIES]
        super().__init__(placeholder='Selecione seus jogos...', min_values=0, max_values=len(options), options=options, custom_id='quasepro:game_roles')

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message('Use este painel dentro do servidor.', ephemeral=True)
            return
        guild = interaction.guild
        selected = set(self.values)
        changed = []
        failed = []
        # Seleção é aditiva para não remover acidentalmente cargos já escolhidos:
        # menus públicos não conseguem pré-selecionar opções diferentes para cada usuário.
        for spec in GAME_CATEGORIES:
            if spec['role'] not in selected:
                continue
            role = discord.utils.get(guild.roles, name=spec['role'])
            if role is None:
                failed.append(spec['role'])
                continue
            if role in interaction.user.roles:
                continue
            try:
                await interaction.user.add_roles(role, reason='Escolha de jogo no painel de cargos')
                changed.append('+' + role.name)
            except (discord.Forbidden, discord.HTTPException):
                failed.append(role.name)
        message = 'Cargos adicionados: ' + (', '.join(changed) if changed else 'nenhum novo cargo selecionado.')
        if failed:
            message += '\nNão foi possível atualizar: ' + ', '.join(failed) + '. Verifique a hierarquia de cargos ou avise a equipe.'
        await interaction.response.send_message(message[:1900], ephemeral=True)

class ClearGameRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label='Remover meus cargos de jogos', emoji='🧹', style=discord.ButtonStyle.secondary, custom_id='quasepro:clear_game_roles')

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message('Use este painel dentro do servidor.', ephemeral=True)
            return
        roles = [discord.utils.get(interaction.guild.roles, name=spec['role']) for spec in GAME_CATEGORIES]
        owned = [r for r in roles if r is not None and r in interaction.user.roles]
        if not owned:
            await interaction.response.send_message('Você não possui cargos de jogos para remover.', ephemeral=True)
            return
        view = ClearGameRolesConfirmView(interaction.user.id, owned)
        await interaction.response.send_message('Remover todos os seus cargos de jogos? Você perderá acesso às categorias correspondentes, mas suas mensagens não serão apagadas.', view=view, ephemeral=True)

class ClearGameRolesConfirmView(discord.ui.View):
    def __init__(self, owner_id: int, roles: list[discord.Role]):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.roles = roles

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('Este painel pertence a outra pessoa.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Confirmar remoção', style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message('Membro não encontrado.', ephemeral=True)
            return
        try:
            await interaction.user.remove_roles(*self.roles, reason='Usuário removeu cargos de jogos pelo painel')
            await interaction.response.edit_message(content='Cargos de jogos removidos. As mensagens foram preservadas.', view=None)
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.response.edit_message(content=f'Não foi possível remover os cargos: {type(exc).__name__}. Avise a equipe.', view=None)
        self.stop()

    @discord.ui.button(label='Cancelar', style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content='Cancelado. Seus cargos foram mantidos.', view=None)
        self.stop()

def make_plan_embed(guild, actions, notes, title='Prévia de reorganização'):
    embed=discord.Embed(title=title, description=f'Servidor: **{guild.name}**\nAções propostas: **{len(actions)}**. Nada foi alterado ainda.', color=discord.Color.blurple())
    buckets={'safe':[],'review':[],'other':[]}
    for a in actions: buckets.get(a.risk,'other').append(a)
    for key,label in [('safe','Ações de menor risco'),('review','Revisar com cuidado'),('other','Outras ações')]:
        arr=buckets[key]
        if arr:
            text='\n'.join(('• '+x.description) for x in arr[:12])
            if len(arr)>12: text += f'\n… e mais {len(arr)-12}'
            embed.add_field(name=f'{label} ({len(arr)})', value=text[:1024], inline=False)
    if notes:
        note='\n'.join('• '+n for n in notes[:5])
        embed.add_field(name='Avisos', value=note[:1024], inline=False)
    embed.set_footer(text='Não há exclusões automáticas. Movimentações podem alterar permissões herdadas.')
    return embed

async def apply_actions(guild: Optional[discord.Guild], actions: list[Action], include_review=True) -> str:
    if guild is None: return 'Servidor não encontrado.'
    done=[]; failed=[]; created_categories={c.name:c for c in guild.categories}
    # Reconcile category operations first so later channel creation/moves can resolve them.
    for a in actions:
        if a.risk == 'review' and not include_review: continue
        try:
            if a.kind == 'create_category':
                name=a.data['name']
                obj=discord.utils.get(guild.categories, name=name) or await guild.create_category(name, reason='Template Quase-Pro aprovado')
                created_categories[name]=obj; done.append(a.description)
            elif a.kind == 'rename_category':
                obj=guild.get_channel(a.data['id'])
                if isinstance(obj, discord.CategoryChannel): await obj.edit(name=a.data['name'], reason='Template Quase-Pro aprovado'); done.append(a.description)
        except (discord.HTTPException, discord.Forbidden, KeyError) as e:
            failed.append(f'{a.description}: {type(e).__name__}')
    for a in actions:
        if a.risk == 'review' and not include_review: continue
        try:
            if a.kind == 'create_channel':
                name=a.data['name']; cat_name=a.data['category']; cat=discord.utils.get(guild.categories, name=cat_name) or created_categories.get(cat_name)
                if a.data['kind']=='voice':
                    await guild.create_voice_channel(name, category=cat, reason='Template Quase-Pro aprovado')
                else:
                    await guild.create_text_channel(name, category=cat, reason='Template Quase-Pro aprovado')
                done.append(a.description)
            elif a.kind == 'rename_channel':
                obj=guild.get_channel(a.data['id'])
                if isinstance(obj, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel)):
                    await obj.edit(name=a.data['name'], reason='Template Quase-Pro aprovado'); done.append(a.description)
            elif a.kind == 'move_channel':
                obj=guild.get_channel(a.data['id']); cat=discord.utils.get(guild.categories, name=a.data['category']) or created_categories.get(a.data['category'])
                if isinstance(obj, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel, discord.StageChannel)) and cat:
                    await obj.edit(category=cat, reason='Template Quase-Pro aprovado; movimentação confirmada'); done.append(a.description)
        except (discord.HTTPException, discord.Forbidden, KeyError) as e:
            failed.append(f'{a.description}: {type(e).__name__}')

    # Reordenar somente depois de criar/renomear/mover. O Discord mantém os IDs,
    # mensagens e configurações dos canais; esta etapa muda apenas suas posições.
    if include_review and any(a.kind == 'reorder_structure' for a in actions):
        try:
            refreshed_categories = list(guild.categories)
            ordered_categories = []
            for spec in CATEGORIES:
                cat = next((c for c in refreshed_categories if same_name(c.name, spec['name'])), None)
                if cat is not None and cat not in ordered_categories:
                    ordered_categories.append(cat)
            # Categorias fora do modelo são preservadas e ficam depois das categorias padronizadas.
            ordered_categories.extend(c for c in refreshed_categories if c not in ordered_categories)
            if ordered_categories:
                for i, cat in enumerate(ordered_categories):
                    await cat.edit(position=i, reason='Organizador Quase-Pro: ordenar categorias conforme modelo aprovado')

            for spec in CATEGORIES:
                cat = next((c for c in guild.categories if same_name(c.name, spec['name'])), None)
                if cat is None:
                    continue
                children = list(cat.channels)
                ordered_children = []
                for target_name, kind, aliases in spec['channels']:
                    candidate = next((c for c in children if same_name(c.name, target_name)), None)
                    if candidate is None:
                        candidate = next((c for c in children if matches_alias(c.name, aliases)), None)
                    if candidate is not None and candidate not in ordered_children:
                        ordered_children.append(candidate)
                # Canais adicionais não mapeados não são apagados; ficam depois dos mapeados.
                ordered_children.extend(c for c in children if c not in ordered_children)
                if ordered_children:
                    for i, channel in enumerate(ordered_children):
                        await channel.edit(position=i, reason=f'Organizador Quase-Pro: ordenar canais em {cat.name}')
            done.append('Ordenar categorias e canais conforme o modelo Quase-Pro')
        except (discord.HTTPException, discord.Forbidden, KeyError, ValueError) as e:
            failed.append(f'Ordenar categorias e canais: {type(e).__name__}')

    out=f'**Concluído:** {len(done)} operação(ões).\n'
    out += '\n'.join('✅ '+x for x in done[:15]) or 'Nenhuma operação aplicada.'
    if len(done)>15: out += f'\n… e mais {len(done)-15} operação(ões).'
    if failed: out += '\n\n**Falhas ({0}):**\n'.format(len(failed))+'\n'.join('⚠️ '+x for x in failed[:10])
    out += '\n\nNenhum canal ou cargo foi excluído. Revise permissões e integrações após a execução.'
    return out[:1900]

class OrganizerBot(commands.Bot):
    async def setup_hook(self):
        self.add_view(GameRoleSelectView())
        if GUILD_ID:
            guild_obj = discord.Object(id=GUILD_ID)

            # Registra primeiro os comandos locais (nesta versão, apenas /painel)
            # no escopo do servidor. O sync substitui a lista remota desse servidor.
            self.tree.copy_global_to(guild=guild_obj)
            synced_guild = await self.tree.sync(guild=guild_obj)
            log.info(
                'Comandos do servidor sincronizados (%s): %s',
                GUILD_ID,
                ', '.join(command.name for command in synced_guild) or '(nenhum)',
            )

            # Remove comandos globais antigos que possam ter ficado publicados
            # por versões anteriores desta aplicação. Isso afeta apenas comandos
            # slash desta aplicação, não mensagens, canais, cargos ou outros bots.
            self.tree.clear_commands(guild=None)
            synced_global = await self.tree.sync()
            log.info(
                'Comandos globais antigos removidos: %s comando(s) restante(s).',
                len(synced_global),
            )
        else:
            # Sem GUILD_ID, não é seguro limpar os comandos globais: exigimos que
            # o servidor seja configurado para garantir uma atualização direcionada.
            raise RuntimeError(
                'GUILD_ID não definido. Preencha o ID do servidor no .env; '
                'a sincronização forçada foi interrompida por segurança.'
            )

intents=discord.Intents.default()
bot=OrganizerBot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    log.info('Conectado como %s (%s)', bot.user, bot.user.id if bot.user else '?')

@bot.tree.command(name='painel', description='Abre o painel visual do organizador de servidor')
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def painel(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message('Você precisa da permissão **Gerenciar servidor**.', ephemeral=True); return
    embed=discord.Embed(title='🛠️ Organizador Quase-Pro', description='Gerencie a estrutura do servidor por botões.\n\n**Comece por “Analisar servidor”** para visualizar o plano antes de alterar qualquer coisa.\n\nEste bot não apaga canais nem cargos automaticamente e não recria mensagens dos bots existentes.', color=discord.Color.blurple())
    embed.add_field(name='Recursos', value='🔎 Analisar estrutura\n🛡️ Aplicar ações seguras\n🧭 Ordenar categorias e canais\n🎮 Criar categorias privadas e painel de cargos por jogo\n🎭 Criar cargos básicos ausentes\nℹ️ Regras de segurança', inline=False)
    await interaction.response.send_message(embed=embed, view=MainPanel(interaction.user.id), ephemeral=True)

if not TOKEN:
    raise SystemExit('DISCORD_TOKEN não definido. Copie .env.example para .env e preencha o token.')
bot.run(TOKEN, log_handler=None)
