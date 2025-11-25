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
    
    async def check_and_assign_roles(self, member: discord.Member) -> int:
        """
        Verifica e atribui cargos automáticos baseados no tempo no servidor.
        Remove cargos anteriores e atribui apenas o cargo mais alto elegível.
        Sistema de progressão: cada membro tem apenas UM cargo por vez.
        
        Args:
            member: Membro do Discord para verificar
            
        Returns:
            1 se houve mudança de cargo, 0 caso contrário
        """
        try:
            # Busca data de entrada
            join_date = await self.db.get_member_join_date(member.guild.id, member.id)
            
            if not join_date:
                # Se não tiver registro, registra agora
                await self.register_member_join(member)
                join_date = member.joined_at if member.joined_at else datetime.now(timezone.utc)
            
            # Calcula dias no servidor (ambos são timezone-aware agora)
            days_in_server = (datetime.now(timezone.utc) - join_date).days
            
            # Busca configurações de cargos automáticos
            auto_roles = await self.db.get_auto_roles(member.guild.id)
            
            if not auto_roles:
                return 0
            
            # Ordena por dias necessários (decrescente) para pegar o maior cargo elegível
            auto_roles.sort(key=lambda x: x['days_required'], reverse=True)
            
            # Encontra o cargo mais alto que o membro é elegível
            highest_eligible_role = None
            for config in auto_roles:
                if days_in_server >= config['days_required']:
                    highest_eligible_role = config
                    break
            
            if not highest_eligible_role:
                return 0
            
            # Busca o cargo no servidor
            target_role = member.guild.get_role(highest_eligible_role['role_id'])
            
            if not target_role:
                logger.warning(f"⚠️ Cargo {highest_eligible_role['role_id']} não encontrado no servidor")
                return 0
            
            # Verifica se o membro já tem este cargo
            if target_role in member.roles:
                return 0  # Já tem o cargo correto
            
            # Remove TODOS os cargos automáticos antigos
            roles_to_remove = []
            for config in auto_roles:
                role = member.guild.get_role(config['role_id'])
                if role and role in member.roles and role != target_role:
                    roles_to_remove.append(role)
            
            # Remove cargos antigos
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Progressão de patente")
                removed_names = [r.name for r in roles_to_remove]
                logger.info(f"🔽 Removidos cargos de {member.name}: {', '.join(removed_names)}")
            
            # Atribui o novo cargo
            await member.add_roles(target_role, reason=f"Tempo no servidor: {days_in_server} dias")
            logger.info(f"✅ Cargo {target_role.name} atribuído a {member.name} ({days_in_server} dias)")
            
            # Atualiza última verificação
            await self.db.update_member_last_checked(member.guild.id, member.id)
            
            return 1
            
        except discord.Forbidden:
            logger.error(f"❌ Sem permissão para gerenciar cargos de {member.name}")
            return 0
        except Exception as e:
            logger.error(f"❌ Erro ao verificar cargos para {member.name}: {e}")
            return 0
    
    async def check_all_members(self, guild: discord.Guild) -> int:
        """
        Verifica e atribui cargos para todos os membros do servidor.
        
        Args:
            guild: Servidor do Discord
            
        Returns:
            Total de mudanças de cargo realizadas
        """
        try:
            total_assigned = 0
            
            for member in guild.members:
                if not member.bot:  # Ignora bots
                    assigned = await self.check_and_assign_roles(member)
                    total_assigned += assigned
            
            if total_assigned > 0:
                logger.info(f"✅ Verificação completa: {total_assigned} mudança(s) de cargo em {guild.name}")
            
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
