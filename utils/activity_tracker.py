# utils/activity_tracker.py - Rastreador de Atividades/Jogos

import discord
from database import Database
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def normalize_game_name(name: str) -> str:
    """Normaliza o nome do jogo/atividade para evitar duplicações por case sensitivity."""
    if not name:
        return ""
    clean = " ".join(name.strip().split())
    lowered = clean.lower()

    # Mapeamento para jogos populares com variações frequentes de capitalização
    KNOWN_GAMES = {
        "roblox": "Roblox",
        "ea sports fc 24": "EA Sports FC 24",
        "ea sports fc 25": "EA Sports FC 25",
        "ea sports fc 26": "EA Sports FC 26",
        "valorant": "VALORANT",
        "counter-strike 2": "Counter-Strike 2",
        "cs2": "Counter-Strike 2",
        "league of legends": "League of Legends",
        "rocket league": "Rocket League",
        "dead by daylight": "Dead by Daylight",
        "visual studio code": "Visual Studio Code",
        "tlauncher": "TLauncher",
        "curseforge": "CurseForge",
        "no man's sky": "No Man's Sky",
        "project zomboid": "Project Zomboid",
        "valheim": "Valheim",
        "gta v": "Grand Theft Auto V",
        "grand theft auto v": "Grand Theft Auto V",
        "minecraft": "Minecraft",
        "fortnite": "Fortnite",
        "overwatch 2": "Overwatch 2",
        "dota 2": "Dota 2",
        "apex legends": "Apex Legends",
        "rainbow six siege": "Tom Clancy's Rainbow Six Siege",
    }

    return KNOWN_GAMES.get(lowered, clean)


class ActivityTracker:
    """Rastreador de atividades e jogos dos usuários."""
    
    def __init__(self, db: Database):
        """
        Inicializa o rastreador de atividades.
        
        Args:
            db: Instância do gerenciador de banco de dados
        """
        self.db = db
        # Cache de atividades em andamento: {(user_id, guild_id, normalized_lower_name): (activity_id, display_name)}
        self.active_activities: Dict[tuple, tuple] = {}
    
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
            # Extrai atividades antes e depois (retorna dict {key_lower: (display_name, activity_type)})
            before_activities = self._extract_activities(before)
            after_activities = self._extract_activities(after)
            
            # Chaves que terminaram
            ended_keys = set(before_activities.keys()) - set(after_activities.keys())
            for key in ended_keys:
                display_name, _ = before_activities[key]
                await self._end_activity(after, display_name)
            
            # Chaves que começaram
            started_keys = set(after_activities.keys()) - set(before_activities.keys())
            for key in started_keys:
                display_name, activity_type = after_activities[key]
                await self._start_activity(after, display_name, activity_type)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar atualização de presença: {e}")
    
    def _extract_activities(self, member: discord.Member) -> Dict[str, tuple]:
        """
        Extrai atividades de um membro de forma case-insensitive.
        
        Args:
            member: Membro do Discord
            
        Returns:
            Dict de {activity_name_lower: (normalized_display_name, activity_type)}
        """
        activities = {}
        
        if not member.activities:
            return activities
        
        for activity in member.activities:
            # Ignora status customizados
            if isinstance(activity, discord.CustomActivity):
                continue
            
            # Ignora Spotify
            if isinstance(activity, discord.Spotify):
                continue
            
            # Ignora hang status (ícones automáticos como "chilling", "gaming" nos canais de voz)
            if hasattr(activity, 'type') and getattr(activity.type, 'value', None) == 6:
                continue
            
            raw_name = getattr(activity, 'name', None)
            if not raw_name:
                continue
            
            # Ignora nomes que são status de voz ou tocadores
            if raw_name.strip().lower() in ("hang status", "spotify"):
                continue
            
            activity_name = normalize_game_name(raw_name)
            activity_type = "unknown"
            
            if isinstance(activity, discord.Game):
                activity_type = "playing"
            elif isinstance(activity, discord.Streaming):
                activity_type = "streaming"
            elif isinstance(activity, discord.Activity):
                if activity.type == discord.ActivityType.playing:
                    activity_type = "playing"
                elif activity.type == discord.ActivityType.streaming:
                    activity_type = "streaming"
                elif activity.type == discord.ActivityType.listening:
                    activity_type = "listening"
                elif activity.type == discord.ActivityType.watching:
                    activity_type = "watching"
                elif activity.type == discord.ActivityType.custom:
                    continue  # Ignora custom status que não seja CustomActivity
            
            if activity_name:
                key = activity_name.strip().lower()
                activities[key] = (activity_name, activity_type)
        
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
            normalized_name = normalize_game_name(activity_name)
            cache_key = (member.id, member.guild.id, normalized_name.strip().lower())
            
            if cache_key in self.active_activities:
                return  # Já está sendo rastreada
            
            # Registra no banco de dados
            activity_id = await self.db.start_activity(
                user_id=member.id,
                guild_id=member.guild.id,
                activity_name=normalized_name,
                activity_type=activity_type
            )
            
            # Adiciona ao cache
            self.active_activities[cache_key] = (activity_id, normalized_name)
            
            logger.debug(f"🎮 {member.name} começou: {normalized_name} ({activity_type})")
            
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
            normalized_name = normalize_game_name(activity_name)
            cache_key = (member.id, member.guild.id, normalized_name.strip().lower())
            
            # Busca no cache
            cached_data = self.active_activities.get(cache_key)
            
            if not cached_data:
                return  # Não estava sendo rastreada
            
            activity_id = cached_data[0] if isinstance(cached_data, tuple) else cached_data
            
            # Finaliza no banco de dados
            await self.db.end_activity(activity_id)
            
            # Remove do cache
            del self.active_activities[cache_key]
            
            logger.debug(f"🎮 {member.name} parou: {normalized_name}")
            
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
                cached_data = self.active_activities[key]
                activity_id = cached_data[0] if isinstance(cached_data, tuple) else cached_data
                await self.db.end_activity(activity_id)
                del self.active_activities[key]
            
            if keys_to_remove:
                logger.info(f"🧹 Limpas {len(keys_to_remove)} atividades de {member.name}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao limpar atividades: {e}")
