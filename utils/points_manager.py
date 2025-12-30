import discord
from typing import List
import logging
from database import Database
from datetime import datetime

logger = logging.getLogger(__name__)

class PointsManager:
    def __init__(self, db: Database, ignored_channels: List[int] = None):
        self.db = db
        self.ignored_channels = ignored_channels if ignored_channels else []
        # Cache for voice/activity start times: {user_id: start_time}
        # Depreciado para cálculo de pontos, mantido se necessário para legacy analytics
        self.voice_sessions = {}
        self.activity_sessions = {}

    async def add_points(self, user_id: int, points: int, interaction_type: str, guild_id: int, username: str = "Unknown", discriminator: str = "0000", is_bot: bool = False):
        """Adds points to a user for a specific interaction type."""
        try:
            if is_bot:
                return

            # Ensure user exists
            await self.db.upsert_user(user_id, username, discriminator, is_bot)
            
            await self.db.add_interaction_point(user_id, points, interaction_type, guild_id)
            logger.info(f"Added {points} points to user {user_id} for {interaction_type}")
        except Exception as e:
            logger.error(f"Error adding points for user {user_id}: {e}")

    async def remove_points(self, user_id: int, points: int, guild_id: int, reason: str = None):
        """Remove pontos de um usuário (usado para moderação)."""
        try:
            # Para simplificar, adicionar pontos negativos é uma forma de remover
            # Assumindo que o DB suporta incrementos negativos ou criar método específico no DB se precisar
            await self.db.add_interaction_point(user_id, -points, "penalty", guild_id) 
            logger.info(f"Removed {points} points from user {user_id}. Reason: {reason}")
        except Exception as e:
            logger.error(f"Error removing points for user {user_id}: {e}")

    async def process_voice_points(self, guilds: List[discord.Guild]):
        """
        Processa periodicamente pontos de voz, streaming e atividades.
        Deve ser chamado a cada minuto.
        """
        try:
            for guild in guilds:
                for channel in guild.voice_channels:
                    # Verifica se canal está na lista de ignorados
                    if channel.id in self.ignored_channels:
                        continue

                    # Filtra membros válidos no canal (não bots)
                    members_in_channel = [m for m in channel.members if not m.bot]
                    count_users = len(members_in_channel)
                    
                    if count_users == 0:
                        continue

                    # Mapeia jogos jogados no canal para verificação de sinergia
                    # Dict[game_name, List[user_id]]
                    games_played = {}
                    
                    for member in members_in_channel:
                        # Pula se estiver mutado E ensurdecido (self_deaf implica não ouvir, logo sem interação)
                        # O requisito diz: "não pontuar se estiver mutado e ensurdecido"
                        # Mas também diz: "pontuação... contabilizada se o usuário estiver só na call, desde que não esteja ensurdecido (self-deaf)"
                        # Vamos assumir que self_deaf anula os pontos.
                        if member.voice.self_deaf:
                            continue

                        points_to_add = 0
                        reasons = []

                        # 1. Ponto Base de Voz (1 ponto/min)
                        points_to_add += 1
                        reasons.append("voice_base")

                        # 2. Bônus de Call (Crowd) (+1 ponto/min se >= 2 pessoas)
                        if count_users >= 2:
                            points_to_add += 1
                            reasons.append("voice_crowd_bonus")

                        # 3. Streaming (+1 ponto/min se transmitindo e >= 2 pessoas na call)
                        if member.voice.self_stream and count_users >= 2:
                            points_to_add += 1
                            reasons.append("streaming_bonus")

                        # Coleta atividades para o bônus de sinergia
                        for activity in member.activities:
                            if activity.type == discord.ActivityType.playing and activity.name:
                                if activity.name not in games_played:
                                    games_played[activity.name] = []
                                games_played[activity.name].append(member.id)
                        
                        # Atividade individual (Jogando algo detectado, mesmo sem call, mas aqui estamos iterando quem TÁ na call)
                        # O requisito "manteremos a pontuação 1 ponto/min em jogo... mesmo se o usuario não estiver em call" 
                        # é tratado em OUTRA parte ou precisamos iterar todos os membros do server?
                        # O ideal para "mesmo fora de call" é iterar guild.members, não channel.members.
                        # Mas iterar todos os membros do server a cada minuto pode ser pesado se for muito grande.
                        # Assumindo que vamos focar nos que estão em call aqui, e tratar os "fora de call" separadamente ou assumir que o "playing" conta aqui.
                        # O requisito diz: "mesmo se o usuario não estiver em call". Então precisamos olhar guild.members que não estão em channel.members também?
                        # Para calls, já estamos iterando. 
                        
                        # Vamos iterar guild.members APENAS para quem está jogando?
                        # O método on_presence_update atual já rastreia início/fim. Talvez seja melhor manter aquele para "fora da call" ou unificar tudo aqui?
                        # O plano diz "Verificação Periódica - 60s" para Jogos também. Então vamos iterar todos os membros.
                        
                        # Para evitar duplicar iteração, vamos processar "Voz" e "Atividade" separadamente ou unificar.
                        # Unificando: Iterar todos membros com atividade OU voz no servidor?
                        # Discord.py cacheia membros. Iterar `guild.members` filtra quem tem `activity` ou `voice`.
                        
                        # Vamos simplificar: Processar quem está na call aqui (já cobre voz + jogo na call).
                        # Depois iterar quem NÃO está na call mas tem atividade?
                        pass # Continua lógica abaixo

                    # Aplica Bônus de Sinergia (jogos iguais na mesma call)
                    # +1 ponto/min se houver dois ou mais membros em call jogando o mesmo jogo
                    synergy_users = set()
                    for game_name, players in games_played.items():
                        if len(players) >= 2:
                            for uid in players:
                                synergy_users.add(uid)
                    
                    # Agora aplica os pontos calculados para os membros do canal
                    for member in members_in_channel:
                         if member.voice.self_deaf:
                            continue
                            
                         # Recalcula pontos locais pois separei a lógica acima para explicar, mas vamos fazer num loop só
                         # ...
                         pass 

            # Refatorando para ser mais eficiente e cobrir "fora da call"
            # Iterar por todos os membros ativos no cache do bot pode ser melhor.
            
            for guild in guilds:
                 for member in guild.members:
                    if member.bot: 
                        continue

                    points = 0
                    
                    # --- Lógica de VOZ ---
                    if member.voice and member.voice.channel and member.voice.channel.id: # Está em call
                        # Verifica se canal está na lista de ignorados
                        if member.voice.channel.id in self.ignored_channels:
                            pass # Pula lógica de voz mas pode pontuar por atividade? 
                            # Requisito não especifica, mas geralmente "ignored from points" em voz
                            # implica não ganhar por estar lá. Por atividade jogando talvez ganhe?
                            # Vamos assumir que ignore invalida SÓ parte de voz.
                        else:
                            # Verifica self_deaf
                            if not member.voice.self_deaf:
                                # Base
                                points += 1
                                
                                # Crowd Bonus (pessoas na mesma sala)
                                #channel = member.voice.channel # Pode ser None se acabou de sair? Não, estamos no loop sincrono do cache
                                # members_in_channel = [m for m in channel.members if not m.bot] # Ineficiente recalcular para cada membro
                                # Melhor pré-calcular mapas de canais.
                                pass

        except Exception as e:
            logger.error(f"Erro no process_voice_points: {e}")

    # Vamos reescrever o método inteiro de forma limpa abaixo
    async def process_voice_points_clean(self, guilds: List[discord.Guild]):
         pass

    async def execute_points_loop(self, guilds: List[discord.Guild]):
        """Executa a verificação periódica de pontos."""
        try:
            # Check for even minute
            is_even_minute = datetime.now().minute % 2 == 0

            for guild in guilds:
                # Pré-cálculo de contagens de canais para evitar O(N^2)
                channel_counts = {} # channel_id -> count of non-bot users
                channel_games = {} # channel_id -> {game_name: set(user_ids)}
                
                for channel in guild.voice_channels:
                    # Verifica se canal está na lista de ignorados
                    if channel.id in self.ignored_channels:
                        continue

                    valid_members = [m for m in channel.members if not m.bot]
                    channel_counts[channel.id] = len(valid_members)
                    
                    channel_games[channel.id] = {}
                    for m in valid_members:
                        for act in m.activities:
                            if act.type == discord.ActivityType.playing and act.name:
                                if act.name not in channel_games[channel.id]:
                                    channel_games[channel.id][act.name] = set()
                                channel_games[channel.id][act.name].add(m.id)

                for member in guild.members:
                    if member.bot:
                        continue
                    
                    current_points = 0
                    
                    # 1. VOZ
                    # Verifica se está em voz E em canal válido
                    in_voice_valid = False
                    if member.voice and member.voice.channel and member.voice.channel.id:
                        if member.voice.channel.id not in self.ignored_channels:
                            in_voice_valid = True
                    
                    # Pontos de Voz (1/min)
                    if in_voice_valid and not member.voice.self_deaf:
                        # Base
                        current_points += 1
                        
                        channel_id = member.voice.channel.id
                        user_count = channel_counts.get(channel_id, 0)
                        
                        # Bonus de Call (>= 2 pessoas)
                        if user_count >= 2:
                            current_points += 1
                        
                        # Bonus de Streaming
                        if member.voice.self_stream and user_count >= 2:
                             current_points += 1
                             
                        # Bonus de Sinergia (dentro da call)
                        has_synergy = False
                        if channel_id in channel_games:
                            for act in member.activities:
                                if act.type == discord.ActivityType.playing and act.name:
                                    if len(channel_games[channel_id].get(act.name, set())) >= 2:
                                        has_synergy = True
                                        break
                        if has_synergy:
                            current_points += 1

                    # 2. ATIVIDADE (Jogando)
                    # Lógica atualizada: 
                    # - Se estiver em call: 1 ponto/min (acumula com voz)
                    # - Se NÃO estiver em call: 1 ponto a cada 2 mins (even minutes only)
                    
                    is_playing = False
                    for act in member.activities:
                        if act.type == discord.ActivityType.playing:
                            is_playing = True
                            break
                    
                    if is_playing:
                        if in_voice_valid:
                            # Jogando E em call válida -> 1 ponto/min
                            current_points += 1
                        elif is_even_minute:
                            # Jogando mas FORA de call -> 1 ponto/2 min
                            current_points += 1
                        # Se não for minuto par e não estiver em call, não ganha ponto de jogo
                    
                    if current_points > 0:
                        await self.add_points(member.id, current_points, "minute_tick", guild.id, member.name, member.discriminator)
                        
        except Exception as e:
            logger.error(f"Error in execute_points_loop: {e}")

    def start_voice_session(self, user_id: int):
        # Legacy stub
        pass

    async def end_voice_session(self, user_id: int):
        # Legacy stub
        pass

    def start_activity_session(self, user_id: int):
        # Legacy stub
        pass

    async def end_activity_session(self, user_id: int):
        # Legacy stub
        pass

    async def recover_sessions(self):
         # Legacy stub
         pass
