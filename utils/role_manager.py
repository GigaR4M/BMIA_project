# utils/role_manager.py - Gerenciador de Cargos Automáticos

import discord
from database import Database
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RoleManager:
    """Gerenciador de cargos automáticos baseados em tempo no servidor."""
    
    def __init__(self, db: Database, ignored_channels: Optional[list] = None):
        self.db = db
        self.ignored_channels = ignored_channels if ignored_channels else []
        self.dynamic_roles_config = {
             # Category Key: Role ID (will be populated from config/env)
            'top_1': None,
            'top_2': None,
            'top_3': None,
            'voz': None,
            'streamer': None,
            'mensagens': None,
            'toxico': None,
            'gamer': None,
            'camaleao': None,
            'maratonista': None
        }
    
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
        """Verifica e atribui cargos automáticos (Versão com Limpeza Forçada)."""
        try:
            # --- 1. Preparar Datas (com a correção de timezone) ---
            join_date = await self.db.get_member_join_date(member.guild.id, member.id)
            
            if not join_date:
                await self.register_member_join(member)
                join_date = datetime.now(timezone.utc).replace(tzinfo=None)
            
            if join_date.tzinfo is None:
                join_date = join_date.replace(tzinfo=timezone.utc)

            days_in_server = (datetime.now(timezone.utc) - join_date).days
            
            # --- 2. Encontrar o Cargo Alvo ---
            auto_roles = await self.db.get_auto_roles(member.guild.id)
            if not auto_roles:
                return 0
            
            # Ordena do maior para o menor
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
            
            changes_made = False

            # --- 3. LIMPEZA: Remover cargos antigos (AQUI ESTAVA O PROBLEMA) ---
            # Removemos o "return 0" prematuro. Agora ele verifica a limpeza sempre.
            roles_to_remove = []
            for config in auto_roles:
                role = member.guild.get_role(config['role_id'])
                # Se o membro tem o cargo, E não é o cargo alvo -> LIXO, REMOVER
                if role and role in member.roles and role.id != target_role.id:
                    roles_to_remove.append(role)
            
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Limpeza de patentes antigas")
                removed_names = [r.name for r in roles_to_remove]
                logger.info(f"🔽 Removidos cargos excedentes de {member.name}: {', '.join(removed_names)}")
                changes_made = True
            
            # --- 4. ATRIBUIÇÃO: Dar o cargo novo (se faltar) ---
            if target_role not in member.roles:
                await member.add_roles(target_role, reason=f"Tempo no servidor: {days_in_server} dias")
                logger.info(f"✅ Cargo {target_role.name} atribuído a {member.name} ({days_in_server} dias)")
                changes_made = True
            
            await self.db.update_member_last_checked(member.guild.id, member.id)
            
            return 1 if changes_made else 0
            
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

    # ==================== DYNAMIC ROLES LOGIC ====================

    def set_dynamic_role_ids(self, config: dict):
        """Atualiza a configuração com os IDs reais dos cargos."""
        for key, role_id in config.items():
            if key in self.dynamic_roles_config:
                self.dynamic_roles_config[key] = role_id
    
    async def sync_dynamic_roles(self, guild: discord.Guild):
        """Sincroniza os cargos dinâmicos baseado nas estatísticas do ano."""
        logger.info(f"🔄 Iniciando sincronização de cargos dinâmicos para {guild.name}")
        
        current_year = datetime.now().year
        
        # 1. Calcular vencedores para cada categoria
        # Retorna lista de user_ids para cada chave
        winners_map = {}
        
        try:
            # Top 1, 2, 3 Absoluto
            winners_map['top_1'] = await self.db.get_top_users_total_points_rank(guild.id, current_year, 1, self.ignored_channels)
            winners_map['top_2'] = await self.db.get_top_users_total_points_rank(guild.id, current_year, 2, self.ignored_channels)
            winners_map['top_3'] = await self.db.get_top_users_total_points_rank(guild.id, current_year, 3, self.ignored_channels)
            
            # Voz do Servidor
            winners_map['voz'] = await self.db.get_top_users_voice_time_year(guild.id, current_year, self.ignored_channels)
            
            # Streamer
            winners_map['streamer'] = await self.db.get_top_users_streaming_time_year(guild.id, current_year)
            
            # Mestre da Conversa
            winners_map['mensagens'] = await self.db.get_top_users_messages_year(guild.id, current_year, self.ignored_channels)
            
            # Boca Suja (Moderated)
            winners_map['toxico'] = await self.db.get_top_users_moderated_year(guild.id, current_year)
            
            # Top Player (Tempo Jogo)
            winners_map['gamer'] = await self.db.get_top_users_game_time_year(guild.id, current_year)
            
            # Camaleão (Jogos Distintos)
            winners_map['camaleao'] = await self.db.get_top_users_distinct_games_year(guild.id, current_year)
            
            # Maratonista
            winners_map['maratonista'] = await self.db.get_top_users_longest_session_year(guild.id, current_year, self.ignored_channels)
            
            # 2. Aplicar mudanças
            for key, role_id in self.dynamic_roles_config.items():
                if not role_id:
                    continue
                    
                role = guild.get_role(role_id)
                if not role:
                    logger.warning(f"⚠️ Cargo dinâmico {key} (ID: {role_id}) não encontrado no servidor.")
                    continue
                
                current_winners = winners_map.get(key, [])
                
                # Adicionar cargo para vencedores
                for user_id in current_winners:
                    member = guild.get_member(user_id)
                    if member and role not in member.roles:
                        try:
                            await member.add_roles(role, reason=f"Vencedor dinâmico: {key}")
                            logger.info(f"➕ Cargo {role.name} adicionado a {member.name}")
                        except discord.Forbidden:
                            logger.error(f"❌ Sem permissão para dar cargo a {member.name}")

                # Remover cargo de quem NÃO é vencedor
                for member in role.members:
                    if member.id not in current_winners:
                        try:
                            await member.remove_roles(role, reason=f"Perdeu posto: {key}")
                            logger.info(f"➖ Cargo {role.name} removido de {member.name}")
                        except discord.Forbidden:
                            logger.error(f"❌ Sem permissão para remover cargo de {member.name}")
                            
            logger.info("✅ Sincronização de cargos dinâmicos concluída.")

        except Exception as e:
            logger.error(f"❌ Erro na sincronização de cargos dinâmicos: {e}")
