# utils/invite_tracker.py - Rastreador de Convites do Discord

import discord
import logging
from typing import Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)

class InviteTracker:
    """Rastreador de convites ativos para associar entradas aos seus respectivos autores."""

    def __init__(self, client: discord.Client):
        self.client = client
        # Cache no formato: {guild_id: {invite_code: uses_count}}
        self.invites_cache: Dict[int, Dict[str, int]] = {}
        # Cache de autores dos convites: {invite_code: inviter_id}
        self.invite_creators: Dict[str, int] = {}

    async def initialize(self):
        """Preenche o cache de convites para todas as guilds onde o bot está presente."""
        for guild in self.client.guilds:
            await self.update_guild_invites(guild)

    async def update_guild_invites(self, guild: discord.Guild):
        """Atualiza a lista de convites em cache para uma guild."""
        try:
            # Verifica se o bot tem permissão para gerenciar/ver convites
            if not guild.me.guild_permissions.manage_guild:
                logger.debug(f"Bot não possui permissão 'manage_guild' em {guild.name} para rastrear convites.")
                return

            invites = await guild.invites()
            self.invites_cache[guild.id] = {invite.code: invite.uses for invite in invites}
            for invite in invites:
                if invite.inviter:
                    self.invite_creators[invite.code] = invite.inviter.id
        except Exception as e:
            logger.warning(f"Erro ao buscar convites da guild {guild.id}: {e}")

    async def find_used_invite(self, member: discord.Member) -> Tuple[Optional[str], Optional[int]]:
        """
        Determina qual convite foi utilizado pelo membro ao ingressar.
        
        Retorna:
            (invite_code, inviter_id) ou (None, None) se não detectado.
        """
        guild = member.guild
        if guild.id not in self.invites_cache:
            await self.update_guild_invites(guild)
            return None, None

        try:
            if not guild.me.guild_permissions.manage_guild:
                return None, None

            new_invites = await guild.invites()
            old_cache = self.invites_cache.get(guild.id, {})

            used_invite_code = None
            inviter_id = None

            for invite in new_invites:
                old_uses = old_cache.get(invite.code, 0)
                if invite.uses > old_uses:
                    used_invite_code = invite.code
                    inviter_id = invite.inviter.id if invite.inviter else None
                    break

            # Se não encontrou nos convites existentes, pode ter sido um convite de uso único que expirou
            if not used_invite_code:
                new_codes = {inv.code for inv in new_invites}
                for old_code in old_cache:
                    if old_code not in new_codes:
                        used_invite_code = old_code
                        inviter_id = self.invite_creators.get(old_code)
                        break

            # Atualiza o cache local
            self.invites_cache[guild.id] = {invite.code: invite.uses for invite in new_invites}
            for invite in new_invites:
                if invite.inviter:
                    self.invite_creators[invite.code] = invite.inviter.id

            return used_invite_code, inviter_id

        except Exception as e:
            logger.error(f"Erro ao identificar convite usado por {member.id} em {guild.id}: {e}")
            return None, None
