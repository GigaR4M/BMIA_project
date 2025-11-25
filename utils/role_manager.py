# utils/role_manager.py - Gerenciador de Cargos Automáticos

import discord
from database import Database
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RoleManager:
    """Gerenciador de cargos automáticos baseados em tempo no servidor."""
    
    def __init__(self, db: Database):
        """
        Inicializa o gerenciador de cargos.
        
        Args:
            db: Instância do gerenciador de banco de dados
        """
        self.db = db
    
    async def register_member_join(self, member: discord.Member):
        """
        Registra a entrada de um membro no servidor.
        
        Args:
            member: Membro que entrou no servidor
        """
        try:
            # Usa a data de entrada do Discord (já vem com timezone)
            # Se não tiver, usa datetime.now() com timezone UTC
            joined_at = member.joined_at if member.joined_at else datetime.now(timezone.utc)
            
            await self.db.upsert_member_join(
                guild_id=member.guild.id,
                user_id=member.id,
                joined_at=joined_at
            )
            
            logger.info(f"✅ Registrado entrada de {member.name} no servidor {member.guild.name}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar entrada de membro: {e}")
    
    async def sync_existing_members(self, guild: discord.Guild):
        """
        Sincroniza membros existentes do servidor com o banco de dados.
        Útil para quando o bot é adicionado a um servidor existente.
        
        Args:
            guild: Servidor do Discord
        """
        try:
            count = 0
            for member in guild.members:
                if not member.bot:  # Ignora bots
                    # member.joined_at já vem com timezone do Discord
                    joined_at = member.joined_at if member.joined_at else datetime.now(timezone.utc)
                    await self.db.upsert_member_join(
                        guild_id=guild.id,
                        user_id=member.id,
                        joined_at=joined_at
                    )
                    count += 1
            
            logger.info(f"✅ Sincronizados {count} membros do servidor {guild.name}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao sincronizar membros: {e}")
    
    async def check_and_assign_roles(self, guild: discord.Guild, member: discord.Member) -> int:
        """
        Verifica e atribui cargos automáticos para um membro baseado no tempo.
        
        Args:
            guild: Servidor do Discord
            member: Membro para verificar
            
        Returns:
            Número de cargos atribuídos
        """
        try:
            # Busca configurações de cargos automáticos
            auto_roles = await self.db.get_auto_roles(guild.id)
            
            if not auto_roles:
                return 0
            
            # Busca data de entrada do membro
            join_date = await self.db.get_member_join_date(guild.id, member.id)
            
            if not join_date:
                # Se não tiver registro, registra agora
                await self.register_member_join(member)
                join_date = member.joined_at if member.joined_at else datetime.now(timezone.utc)
            
            # Calcula dias no servidor (ambos são timezone-aware agora)
            days_in_server = (datetime.now(timezone.utc) - join_date).days
            
            roles_assigned = 0
            
            # Verifica cada configuração de cargo
            for config in auto_roles:
                role_id = config['role_id']
                days_required = config['days_required']
                
                # Verifica se o membro já tem o cargo
                role = guild.get_role(role_id)
                if not role:
                    logger.warning(f"⚠️ Cargo {role_id} não encontrado no servidor {guild.name}")
                    continue
                
                # Se o membro tem dias suficientes e não tem o cargo ainda
                if days_in_server >= days_required and role not in member.roles:
                    try:
                        await member.add_roles(role, reason=f"Cargo automático: {days_in_server} dias no servidor")
                        logger.info(f"✅ Cargo {role.name} atribuído a {member.name} ({days_in_server} dias)")
                        roles_assigned += 1
                    except discord.Forbidden:
                        logger.error(f"❌ Sem permissão para atribuir cargo {role.name}")
                    except discord.HTTPException as e:
                        logger.error(f"❌ Erro ao atribuir cargo {role.name}: {e}")
            
            # Atualiza última verificação
            await self.db.update_member_last_checked(guild.id, member.id)
            
            return roles_assigned
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar cargos para {member.name}: {e}")
            return 0
    
    async def check_all_members(self, guild: discord.Guild) -> int:
        """
        Verifica e atribui cargos para todos os membros do servidor.
        
        Args:
            guild: Servidor do Discord
            
        Returns:
            Total de cargos atribuídos
        """
        try:
            total_assigned = 0
            
            for member in guild.members:
                if not member.bot:  # Ignora bots
                    assigned = await self.check_and_assign_roles(guild, member)
                    total_assigned += assigned
            
            logger.info(f"✅ Verificação completa: {total_assigned} cargos atribuídos em {guild.name}")
            return total_assigned
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar todos os membros: {e}")
            return 0
    
    def get_member_tenure_days(self, join_date: datetime) -> int:
        """
        Calcula quantos dias um membro está no servidor.
        
        Args:
            join_date: Data de entrada do membro (timezone-aware)
            
        Returns:
            Número de dias no servidor
        """
        return (datetime.now(timezone.utc) - join_date).days
