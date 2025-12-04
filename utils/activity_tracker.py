# utils/activity_tracker.py - Rastreador de Atividades/Jogos

import discord
from database import Database
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ActivityTracker:
    """Rastreador de atividades e jogos dos usuários."""
    
    def __init__(self, db: Database):
        """
        Inicializa o rastreador de atividades.
        
        Args:
            db: Instância do gerenciador de banco de dados
        """
        self.db = db
        # Cache de atividades em andamento: {(user_id, guild_id, activity_name): activity_id}
        self.active_activities: Dict[tuple, int] = {}
    
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """
        Handler para mudanças de estado de voz (para detectar compartilhamento de tela).
        """
        if member.bot:
            return

        try:
            # Detecta início de compartilhamento de tela (Go Live)
            if not before.self_stream and after.self_stream:
                await self._start_activity(member, "Screen Share", "screen_share")
            
            # Detecta fim de compartilhamento de tela
            elif before.self_stream and not after.self_stream:
                await self._end_activity(member, "Screen Share")
                
            # Se saiu do canal de voz, encerra screen share se estiver ativo
            if before.channel and not after.channel:
                await self._end_activity(member, "Screen Share")

        except Exception as e:
            logger.error(f"❌ Erro ao processar atualização de voz no ActivityTracker: {e}")

    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """
        Handler para mudanças de presença (atividades/jogos).
        
        Args:
            before: Estado anterior do membro
            after: Estado atual do membro
        """
        # Ignora bots
        if after.bot:
            return
        
        try:
            # Extrai atividades antes e depois
            before_activities = self._extract_activities(before)
            after_activities = self._extract_activities(after)
            
            # Atividades que terminaram
            ended_activities = before_activities - after_activities
            for activity_name, activity_type in ended_activities:
                await self._end_activity(after, activity_name)
            
            # Atividades que começaram
            started_activities = after_activities - before_activities
            for activity_name, activity_type in started_activities:
                await self._start_activity(after, activity_name, activity_type)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar atualização de presença: {e}")
    
    def _extract_activities(self, member: discord.Member) -> set:
        """
        Extrai atividades de um membro.
        
        Args:
            member: Membro do Discord
            
        Returns:
            Set de tuplas (activity_name, activity_type)
        """
        activities = set()
        
        if not member.activities:
            return activities
        
        for activity in member.activities:
            # Ignora status customizados
            if isinstance(activity, discord.CustomActivity):
                continue
            
            # Ignora Spotify (pode ser adicionado depois se quiser)
            if isinstance(activity, discord.Spotify):
                continue
            
            activity_name = None
            activity_type = "unknown"
            
            if isinstance(activity, discord.Game):
                activity_name = activity.name
                activity_type = "playing"
            elif isinstance(activity, discord.Streaming):
                activity_name = activity.name
                activity_type = "streaming"
            elif isinstance(activity, discord.Activity):
                activity_name = activity.name
                if activity.type == discord.ActivityType.playing:
                    activity_type = "playing"
                elif activity.type == discord.ActivityType.streaming:
                    activity_type = "streaming"
                elif activity.type == discord.ActivityType.listening:
                    activity_type = "listening"
                elif activity.type == discord.ActivityType.watching:
                    activity_type = "watching"
            
            if activity_name:
                activities.add((activity_name, activity_type))
        
        return activities
    
    async def _start_activity(self, member: discord.Member, activity_name: str, 
                             activity_type: str):
        """
        Registra início de uma atividade.
        
        Args:
            member: Membro do Discord
            activity_name: Nome da atividade
            activity_type: Tipo da atividade
        """
        try:
            # Verifica se já está rastreando esta atividade
            cache_key = (member.id, member.guild.id, activity_name)
            
            if cache_key in self.active_activities:
                return  # Já está sendo rastreada
            
            # Registra no banco de dados
            activity_id = await self.db.start_activity(
                user_id=member.id,
                guild_id=member.guild.id,
                activity_name=activity_name,
                activity_type=activity_type
            )
            
            # Adiciona ao cache
            self.active_activities[cache_key] = activity_id
            
            logger.debug(f"🎮 {member.name} começou: {activity_name} ({activity_type})")
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar rastreamento de atividade: {e}")
    
    async def _end_activity(self, member: discord.Member, activity_name: str):
        """
        Finaliza rastreamento de uma atividade.
        
        Args:
            member: Membro do Discord
            activity_name: Nome da atividade
        """
        try:
            cache_key = (member.id, member.guild.id, activity_name)
            
            # Busca no cache
            activity_id = self.active_activities.get(cache_key)
            
            if not activity_id:
                return  # Não estava sendo rastreada
            
            # Finaliza no banco de dados
            await self.db.end_activity(activity_id)
            
            # Remove do cache
            del self.active_activities[cache_key]
            
            logger.debug(f"🎮 {member.name} parou: {activity_name}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao finalizar rastreamento de atividade: {e}")
    
    async def cleanup_member_activities(self, member: discord.Member):
        """
        Limpa atividades em andamento de um membro (quando sai do servidor, etc).
        
        Args:
            member: Membro do Discord
        """
        try:
            # Busca todas as atividades deste membro no cache
            keys_to_remove = [
                key for key in self.active_activities.keys()
                if key[0] == member.id and key[1] == member.guild.id
            ]
            
            # Finaliza cada uma
            for key in keys_to_remove:
                activity_id = self.active_activities[key]
                await self.db.end_activity(activity_id)
                del self.active_activities[key]
            
            if keys_to_remove:
                logger.info(f"🧹 Limpas {len(keys_to_remove)} atividades de {member.name}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao limpar atividades: {e}")
