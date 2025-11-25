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
        self.db = db
    
    def _to_naive_utc(self, dt: datetime) -> datetime:
        """
        Converte uma data Aware (com timezone) para Naive UTC (sem timezone).
        Essencial para salvar no PostgreSQL na coluna TIMESTAMP.
        """
        if dt is None:
            return datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Garante que está em UTC e remove a informação de timezone
        return dt.astimezone(timezone.utc).replace(tzinfo=None)

    async def register_member_join(self, member: discord.Member):
        """Registra a entrada de um membro no servidor."""
        try:
            # CORREÇÃO 1: Converter para Naive UTC antes de salvar
            raw_date = member.joined_at if member.joined_at else datetime.now(timezone.utc)
            joined_at = self._to_naive_utc(raw_date)
            
            await self.db.upsert_member_join(
                guild_id=member.guild.id,
                user_id=member.id,
                joined_at=joined_at
            )
            
            logger.info(f"✅ Registrado entrada de {member.name} no servidor {member.guild.name}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar entrada de membro: {e}")
    
    async def sync_existing_members(self, guild: discord.Guild):
        """Sincroniza membros existentes."""
        try:
            count = 0
            for member in guild.members:
                if not member.bot:
                    # CORREÇÃO 2: Converter para Naive UTC antes de salvar
                    raw_date = member.joined_at if member.joined_at else datetime.now(timezone.utc)
                    joined_at = self._to_naive_utc(raw_date)

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
        """Verifica e atribui cargos automáticos."""
        try:
            # Busca data de entrada
            join_date = await self.db.get_member_join_date(member.guild.id, member.id)
            
            if not join_date:
                await self.register_member_join(member)
                # Pega a data atual já em UTC Naive para o cálculo abaixo
                join_date = datetime.now(timezone.utc).replace(tzinfo=None)
            
            # CORREÇÃO 3: Lidar com a leitura do Banco
            # Se a data do banco vier Naive (sem fuso), adicionamos UTC para fazer contas
            if join_date.tzinfo is None:
                join_date = join_date.replace(tzinfo=timezone.utc)

            # Agora podemos subtrair com segurança (Aware - Aware)
            days_in_server = (datetime.now(timezone.utc) - join_date).days
            
            # --- Resto da lógica original (sem alterações) ---
            auto_roles = await self.db.get_auto_roles(member.guild.id)
            
            if not auto_roles:
                return 0
            
            auto_roles.sort(key=lambda x: x['days_required'], reverse=True)
            
            highest_eligible_role = None
            for config in auto_roles:
                if days_in_server >= config['days_required']:
                    highest_eligible_role = config
                    break
            
            if not highest_eligible_role:
                return 0
            
            target_role = member.guild.get_role(highest_eligible_role['role_id'])
            
            if not target_role:
                logger.warning(f"⚠️ Cargo {highest_eligible_role['role_id']} não encontrado")
                return 0
            
            if target_role in member.roles:
                return 0
            
            roles_to_remove = []
            for config in auto_roles:
                role = member.guild.get_role(config['role_id'])
                if role and role in member.roles and role != target_role:
                    roles_to_remove.append(role)
            
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Progressão de patente")
            
            await member.add_roles(target_role, reason=f"Tempo no servidor: {days_in_server} dias")
            logger.info(f"✅ Cargo {target_role.name} atribuído a {member.name} ({days_in_server} dias)")
            
            await self.db.update_member_last_checked(member.guild.id, member.id)
            
            return 1
            
        except discord.Forbidden:
            logger.error(f"❌ Sem permissão para gerenciar cargos de {member.name}")
            return 0
        except Exception as e:
            logger.error(f"❌ Erro ao verificar cargos para {member.name}: {e}")
            return 0

    async def check_all_members(self, guild: discord.Guild) -> int:
        """Verifica todos os membros."""
        try:
            total_assigned = 0
            for member in guild.members:
                if not member.bot:
                    assigned = await self.check_and_assign_roles(member)
                    total_assigned += assigned
            
            if total_assigned > 0:
                logger.info(f"✅ Verificação completa: {total_assigned} mudança(s) em {guild.name}")
            return total_assigned
        except Exception as e:
            logger.error(f"❌ Erro ao verificar todos os membros: {e}")
            return 0

    def get_member_tenure_days(self, join_date: datetime) -> int:
        # Garante timezone para o cálculo
        if join_date.tzinfo is None:
            join_date = join_date.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - join_date).days
