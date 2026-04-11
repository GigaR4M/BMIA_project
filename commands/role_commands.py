# commands/role_commands.py - Comandos Slash de Cargos Automáticos

import discord
from discord import app_commands
from database import Database
from utils.role_manager import RoleManager
import logging

logger = logging.getLogger(__name__)


class RoleCommands(app_commands.Group):
    """Grupo de comandos de cargos automáticos."""
    
    def __init__(self, db: Database, role_manager: RoleManager):
        super().__init__(name="autorole", description="Gerenciar cargos automáticos por tempo")
        self.db = db
        self.role_manager = role_manager
    
    @app_commands.command(name="add", description="Adiciona um cargo automático")
    @app_commands.describe(
        cargo="Cargo a ser atribuído automaticamente",
        dias="Número de dias necessários no servidor"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def add_auto_role(self, interaction: discord.Interaction, 
                           cargo: discord.Role, dias: int):
        """Adiciona uma configuração de cargo automático."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validações
            if dias < 0:
                await interaction.followup.send(
                    "❌ O número de dias deve ser positivo!",
                    ephemeral=True
                )
                return
            
            # Verifica hierarquia de cargos
            if cargo >= interaction.guild.me.top_role:
                await interaction.followup.send(
                    f"❌ O cargo {cargo.mention} está acima do meu cargo na hierarquia! "
                    f"Mova meu cargo para cima ou escolha um cargo mais baixo.",
                    ephemeral=True
                )
                return
            
            # Adiciona configuração
            await self.db.add_auto_role(
                guild_id=interaction.guild.id,
                role_id=cargo.id,
                days_required=dias
            )
            
            await interaction.followup.send(
                f"✅ Cargo {cargo.mention} será atribuído automaticamente após **{dias} dia(s)** no servidor!",
                ephemeral=True
            )
            
            logger.info(f"✅ Cargo automático configurado: {cargo.name} após {dias} dias em {interaction.guild.name}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao adicionar cargo automático: {e}")
            await interaction.followup.send(
                "❌ Erro ao configurar cargo automático. Tente novamente.",
                ephemeral=True
            )
    
    @app_commands.command(name="remove", description="Remove um cargo automático")
    @app_commands.describe(cargo="Cargo a ser removido da configuração")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def remove_auto_role(self, interaction: discord.Interaction, cargo: discord.Role):
        """Remove uma configuração de cargo automático."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            await self.db.remove_auto_role(
                guild_id=interaction.guild.id,
                role_id=cargo.id
            )
            
            await interaction.followup.send(
                f"✅ Cargo {cargo.mention} removido da configuração de cargos automáticos!",
                ephemeral=True
            )
            
            logger.info(f"✅ Cargo automático removido: {cargo.name} em {interaction.guild.name}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao remover cargo automático: {e}")
            await interaction.followup.send(
                "❌ Erro ao remover cargo automático. Tente novamente.",
                ephemeral=True
            )
    
    @app_commands.command(name="list", description="Lista todos os cargos automáticos configurados")
    async def list_auto_roles(self, interaction: discord.Interaction):
        """Lista todas as configurações de cargos automáticos."""
        await interaction.response.defer()
        
        try:
            auto_roles = await self.db.get_auto_roles(interaction.guild.id)
            
            if not auto_roles:
                await interaction.followup.send(
                    "📋 Nenhum cargo automático configurado neste servidor."
                )
                return
            
            embed = discord.Embed(
                title="⚙️ Cargos Automáticos Configurados",
                description="Cargos que serão atribuídos automaticamente baseados no tempo no servidor:",
                color=discord.Color.blue()
            )
            
            # Ordena por dias necessários
            auto_roles.sort(key=lambda x: x['days_required'])
            
            for config in auto_roles:
                role = interaction.guild.get_role(config['role_id'])
                if role:
                    embed.add_field(
                        name=f"{role.name}",
                        value=f"Após **{config['days_required']} dia(s)** no servidor",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar cargos automáticos: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar configurações. Tente novamente.",
                ephemeral=True
            )
    
    @app_commands.command(name="check", description="Verifica o status de um membro")
    @app_commands.describe(membro="Membro para verificar (deixe vazio para verificar você mesmo)")
    async def check_member(self, interaction: discord.Interaction, 
                          membro: discord.Member = None):
        """Verifica o status de cargos de um membro."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            target = membro or interaction.user
            
            # Busca data de entrada
            join_date = await self.db.get_member_join_date(
                interaction.guild.id,
                target.id
            )
            
            if not join_date:
                # Tenta usar a data do Discord
                join_date = target.joined_at
                if join_date:
                    await self.db.upsert_member_join(
                        interaction.guild.id,
                        target.id,
                        join_date
                    )
            
            if not join_date:
                await interaction.followup.send(
                    "❌ Não foi possível determinar a data de entrada deste membro.",
                    ephemeral=True
                )
                return
            
            # Calcula dias no servidor
            days_in_server = self.role_manager.get_member_tenure_days(join_date)
            
            # Busca configurações de cargos
            auto_roles = await self.db.get_auto_roles(interaction.guild.id)
            
            embed = discord.Embed(
                title=f"📊 Status de {target.display_name}",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📅 Entrou no servidor",
                value=f"<t:{int(join_date.timestamp())}:R>",
                inline=False
            )
            
            embed.add_field(
                name="⏱️ Tempo no servidor",
                value=f"**{days_in_server} dia(s)**",
                inline=False
            )
            
            if auto_roles:
                # Verifica quais cargos o membro tem/terá
                has_roles = []
                will_get = []
                
                for config in auto_roles:
                    role = interaction.guild.get_role(config['role_id'])
                    if not role:
                        continue
                    
                    if days_in_server >= config['days_required']:
                        if role in target.roles:
                            has_roles.append(f"✅ {role.mention}")
                        else:
                            will_get.append(f"⏳ {role.mention} (será atribuído em breve)")
                    else:
                        days_left = config['days_required'] - days_in_server
                        will_get.append(f"🔒 {role.mention} (em {days_left} dia(s))")
                
                if has_roles:
                    embed.add_field(
                        name="🎖️ Cargos Automáticos Obtidos",
                        value="\n".join(has_roles),
                        inline=False
                    )
                
                if will_get:
                    embed.add_field(
                        name="📋 Próximos Cargos",
                        value="\n".join(will_get),
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar membro: {e}")
            await interaction.followup.send(
                "❌ Erro ao verificar status. Tente novamente.",
                ephemeral=True
            )
    
    @app_commands.command(name="sync", description="Sincroniza todos os membros existentes")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync_members(self, interaction: discord.Interaction):
        """Sincroniza todos os membros do servidor com o banco de dados."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            await interaction.followup.send(
                "🔄 Sincronizando membros... Isso pode levar alguns segundos.",
                ephemeral=True
            )
            
            await self.role_manager.sync_existing_members(interaction.guild)
            
            await interaction.followup.send(
                "✅ Todos os membros foram sincronizados!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao sincronizar membros: {e}")
            await interaction.followup.send(
                "❌ Erro ao sincronizar membros. Tente novamente.",
                ephemeral=True
            )

    @app_commands.command(name="explicar", description="Explica os requisitos para os cargos especiais")
    async def explain_dynamic_roles(self, interaction: discord.Interaction):
        """Lista e explica os cargos dinâmicos (conquistas) do servidor."""
        await interaction.response.defer(ephemeral=True)

        try:
            descriptions = {
                'top_1': ("🥇 Top 1 Global", "Maior pontuação geral (Atividade + Voz + Jogo) no ano."),
                'top_2': ("🥈 Top 2 Global", "Segunda maior pontuação geral no ano."),
                'top_3': ("🥉 Top 3 Global", "Terceira maior pontuação geral no ano."),
                'voz': ("🗣️ Voz do Sistema", "Maior tempo acumulado em canais de voz."),
                'streamer': ("📡 Streamer do Servidor", "Maior tempo transmitindo vídeo em canais de voz."),
                'mensagens': ("⌨️ Mestre da Conversa", "Maior quantidade de mensagens enviadas (sem spam)."),
                'toxico': ("☣️ Boca Suja", "Maior quantidade de mensagens moderadas/deletadas por filtro."),
                'gamer': ("🎮 Vício em Jogos", "Maior tempo acumulado jogando (status de atividade)."),
                'camaleao': ("🦎 Camaleão Gamer", "Maior variedade de jogos diferentes jogados."),
                'maratonista': ("🏃 Maratonista", "Sessão de voz contínua mais longa registrada."),
                'corujao': ("🌙 Corujão", "Maior tempo em voz na madrugada (00h–06h)."),
                'midia': ("📸 O Mídia", "Maior quantidade de arquivos/mídias enviados."),
                'onipresente': ("🌍 Onipresente", "Maior número de dias ativos no servidor.")
            }

            embed = discord.Embed(
                title="🏆 Cargos Dinâmicos & Conquistas",
                description="Estes cargos são disputados durante todo o ano e entregues periodicamente aos melhores em cada categoria!",
                color=discord.Color.gold()
            )

            # Access dynamic roles config from RoleManager
            # Note: RoleManager instances might share config or rely on what's set in main.py
            # If config is empty/None in manager, we try to use descriptions anyway.
            # Assuming role_manager.dynamic_roles_config is populated via main.py loop
            
            config = self.role_manager.dynamic_roles_config
            
            for key, (name, desc) in descriptions.items():
                role_id = config.get(key)
                role_mention = ""
                
                if role_id:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_mention = f"({role.mention})"
                    else:
                        # Se tem ID mas não achou cargo (deletado?), não mostra menção quebrada
                        pass
                
                # Combine name and mention
                field_name = f"{name} {role_mention}".strip()
                embed.add_field(name=field_name, value=desc, inline=False)

            embed.set_footer(text="As estatísticas são resetadas anualmente! Continue participando para ganhar.")
            
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ Erro ao explicar cargos dinâmicos: {e}")
            await interaction.followup.send(
                "❌ Erro ao listar cargos. Tente novamente.",
                ephemeral=True
            )
    
    # Error handlers
    @add_auto_role.error
    @remove_auto_role.error
    async def role_command_error(self, interaction: discord.Interaction, 
                                error: app_commands.AppCommandError):
        """Handler de erro para comandos que requerem permissões."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa de permissão de **Gerenciar Cargos** para usar este comando.",
                ephemeral=True
            )
    
    @sync_members.error
    async def sync_error(self, interaction: discord.Interaction, 
                        error: app_commands.AppCommandError):
        """Handler de erro para comando de sincronização."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa de permissão de **Administrador** para usar este comando.",
                ephemeral=True
            )
