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
    @discord.ui.button(label='Ajuda e segurança', emoji='ℹ️', style=discord.ButtonStyle.secondary, row=1)
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title='Como este organizador funciona', description='• Um único comando: `/painel`.\n• Nenhum canal ou cargo é apagado automaticamente.\n• As alterações são mostradas antes da execução.\n• Movimentações de canais são classificadas como revisão porque podem alterar permissões herdadas.\n• Mensagens, IDs e bancos de dados dos bots existentes não são recriados.\n• A permissão Gerenciar servidor é exigida.', color=discord.Color.blurple())
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
    out=f'**Concluído:** {len(done)} operação(ões).\n'
    out += '\n'.join('✅ '+x for x in done[:15]) or 'Nenhuma operação aplicada.'
    if len(done)>15: out += f'\n… e mais {len(done)-15} operação(ões).'
    if failed: out += '\n\n**Falhas ({0}):**\n'.format(len(failed))+'\n'.join('⚠️ '+x for x in failed[:10])
    out += '\n\nNenhum canal ou cargo foi excluído. Revise permissões e integrações após a execução.'
    return out[:1900]

class OrganizerBot(commands.Bot):
    async def setup_hook(self):
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
    embed.add_field(name='Recursos', value='🔎 Analisar estrutura\n🛡️ Aplicar ações seguras\n🎭 Criar cargos básicos ausentes\nℹ️ Regras de segurança', inline=False)
    await interaction.response.send_message(embed=embed, view=MainPanel(interaction.user.id), ephemeral=True)

if not TOKEN:
    raise SystemExit('DISCORD_TOKEN não definido. Copie .env.example para .env e preencha o token.')
bot.run(TOKEN, log_handler=None)
