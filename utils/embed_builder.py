# utils/embed_builder.py - Construtor de Embeds para Estatísticas

import discord
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import now_brt



class StatsEmbedBuilder:
    """Construtor de embeds formatados para estatísticas."""
    
    # Cores para diferentes tipos de embeds
    COLOR_INFO = 0x3498db      # Azul
    COLOR_SUCCESS = 0x2ecc71   # Verde
    COLOR_WARNING = 0xf39c12   # Laranja
    COLOR_STATS = 0x9b59b6     # Roxo
    
    def build_server_stats(self, stats: Dict[str, Any], server_name: str) -> discord.Embed:
        """
        Constrói embed com estatísticas do servidor.
        
        Args:
            stats: Dicionário com estatísticas
            server_name: Nome do servidor
            
        Returns:
            Embed formatado
        """
        embed = discord.Embed(
            title=f"📊 Estatísticas do Servidor",
            description=f"**{server_name}**",
            color=self.COLOR_STATS,
            timestamp=now_brt()
        )
        
        period = stats.get('period_days', 30)
        embed.add_field(
            name="📅 Período",
            value=f"Últimos {period} dias",
            inline=False
        )
        
        embed.add_field(
            name="💬 Total de Mensagens",
            value=f"**{stats.get('total_messages', 0):,}**",
            inline=True
        )
        
        embed.add_field(
            name="👥 Usuários Ativos",
            value=f"**{stats.get('active_users', 0):,}**",
            inline=True
        )
        
        embed.add_field(
            name="📺 Canais Ativos",
            value=f"**{stats.get('active_channels', 0):,}**",
            inline=True
        )
        
        moderated = stats.get('moderated_messages', 0)
        if moderated > 0:
            embed.add_field(
                name="🚫 Mensagens Moderadas",
                value=f"**{moderated:,}**",
                inline=True
            )
        
        embed.set_footer(text="Use /stats top para ver os usuários mais ativos")
        
        return embed
    
    def build_user_stats(self, stats: Dict[str, Any], username: str, 
                        avatar_url: Optional[str] = None) -> discord.Embed:
        """
        Constrói embed com estatísticas de um usuário incluindo nível e XP.
        """
        from utils.level_manager import get_level_progress
        
        total_xp = stats.get('total_points', 0)
        level_data = get_level_progress(total_xp)
        level = level_data["level"]
        progress_pct = level_data["progress_pct"]
        
        embed = discord.Embed(
            title=f"📊 Estatísticas de {username}",
            color=self.COLOR_INFO,
            timestamp=now_brt()
        )
        
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        
        # Período e Nível
        period = stats.get('period_days', 30)
        period_text = "Ano Atual" if period > 365 else f"Últimos {period} dias"
        embed.add_field(name="📅 Período", value=period_text, inline=True)
        embed.add_field(name="🎖️ Nível", value=f"**Nv. {level}** ({progress_pct}%)", inline=True)
        embed.add_field(name="⚡ Total de XP", value=f"**{total_xp:,} XP**", inline=True)
        
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        
        # 1. Estatísticas de Uso
        total_msgs = stats.get('total_messages', 0)
        voice_mins = stats.get('voice_minutes', 0)
        game_mins = stats.get('game_minutes', 0)
        
        def format_time(minutes):
            if minutes >= 60:
                return f"{minutes // 60}h {minutes % 60}m"
            return f"{minutes} min"

        usage_text = (
            f"📨 **Mensagens:** {total_msgs:,}\n"
            f"🎙️ **Tempo em Voz:** {format_time(voice_mins)}\n"
            f"🎮 **Tempo em Jogo:** {format_time(game_mins)}"
        )
        embed.add_field(name="📈 Atividade", value=usage_text, inline=True)

        # 2. Detalhamento de XP
        breakdown = stats.get('points_breakdown', {})
        
        # Agrega pontos de mensagem (legacy 'message', 'message_short', 'message_long')
        xp_msg = (
            breakdown.get('message', 0) + 
            breakdown.get('message_short', 0) + 
            breakdown.get('message_long', 0)
        )
        
        # Agrega pontos de voz (legacy 'voice', 'voice_base', etc. e novo 'minute_tick')
        xp_voice = (
            breakdown.get('voice', 0) +
            breakdown.get('voice_base', 0) +
            breakdown.get('voice_crowd_bonus', 0) +
            breakdown.get('streaming_bonus', 0) +
            breakdown.get('minute_tick', 0)
        )
        
        other_xp = total_xp - (xp_msg + xp_voice)
        
        xp_text = (
            f"💬 **Mensagens:** {xp_msg:,} XP\n"
            f"🗣️ **Voz & Jogos:** {xp_voice:,} XP\n"
        )
        if other_xp > 0:
            xp_text += f"✨ **Bônus/Outros:** {other_xp:,} XP"
            
        embed.add_field(name="⭐ Ganho de XP", value=xp_text, inline=True)
        
        embed.add_field(name="\u200b", value="\u200b", inline=False)

        # 3. Favoritos
        top_text = stats.get('top_text_channels', [])
        top_voice = stats.get('top_voice_channels', [])
        top_games = stats.get('top_activities', [])

        favs_text = ""
        if top_text:
            ch = top_text[0]
            cnt = int(ch.get('count') or 0)
            favs_text += f"📝 **Chat:** #{ch.get('channel_name', 'desconhecido')} ({cnt} msgs)\n"
        
        if top_voice:
            ch = top_voice[0]
            mins = int(ch.get('minutes') or 0)
            favs_text += f"🔊 **Call:** {ch.get('channel_name', 'desconhecido')} ({format_time(mins)})\n"
            
        if top_games:
            game = top_games[0]
            mins = int(game.get('minutes') or 0)
            favs_text += f"🎮 **Jogo:** {game.get('activity_name', 'desconhecido')} ({format_time(mins)})"
            
        if favs_text:
            embed.add_field(name="❤️ Favoritos", value=favs_text, inline=False)
        
        return embed

    
    def build_top_users(self, users: List[Dict[str, Any]], days: int) -> discord.Embed:
        """
        Constrói embed com ranking de usuários mais ativos.
        
        Args:
            users: Lista de usuários com contagem de mensagens
            days: Período em dias
            
        Returns:
            Embed formatado
        """
        embed = discord.Embed(
            title="🏆 Usuários Mais Ativos",
            description=f"Ranking dos últimos {days} dias",
            color=self.COLOR_SUCCESS,
            timestamp=now_brt()
        )
        
        if not users:
            embed.description = "Nenhum dado disponível para este período."
            return embed
        
        # Emojis de medalhas
        medals = ["🥇", "🥈", "🥉"]
        
        ranking_text = ""
        for i, user in enumerate(users, 1):
            medal = medals[i-1] if i <= 3 else f"**{i}.**"
            username = user['username']
            count = user['message_count']
            ranking_text += f"{medal} **{username}** - {count:,} mensagens\n"
        
        embed.add_field(
            name="💬 Mensagens Enviadas",
            value=ranking_text,
            inline=False
        )
        
        return embed
    
    def build_top_channels(self, channels: List[Dict[str, Any]], days: int) -> discord.Embed:
        """
        Constrói embed com ranking de canais mais ativos.
        
        Args:
            channels: Lista de canais com contagem de mensagens
            days: Período em dias
            
        Returns:
            Embed formatado
        """
        embed = discord.Embed(
            title="📺 Canais Mais Ativos",
            description=f"Ranking dos últimos {days} dias",
            color=self.COLOR_WARNING,
            timestamp=now_brt()
        )
        
        if not channels:
            embed.description = "Nenhum dado disponível para este período."
            return embed
        
        # Emojis de medalhas
        medals = ["🥇", "🥈", "🥉"]
        
        ranking_text = ""
        for i, channel in enumerate(channels, 1):
            medal = medals[i-1] if i <= 3 else f"**{i}.**"
            channel_name = channel['channel_name']
            count = channel['message_count']
            ranking_text += f"{medal} **#{channel_name}** - {count:,} mensagens\n"
        
        embed.add_field(
            name="💬 Mensagens Enviadas",
            value=ranking_text,
            inline=False
        )
        
        return embed
    
    def build_error_embed(self, error_message: str) -> discord.Embed:
        """
        Constrói embed de erro.
        
        Args:
            error_message: Mensagem de erro
            
        Returns:
            Embed formatado
        """
        embed = discord.Embed(
            title="❌ Erro",
            description=error_message,
            color=discord.Color.red(),
            timestamp=now_brt()
        )
        
        return embed

    def build_leaderboard(self, leaderboard: List[Dict[str, Any]]) -> discord.Embed:
        """
        Constrói embed com leaderboard de XP e Níveis.
        
        Args:
            leaderboard: Lista de usuários com pontos/XP
            
        Returns:
            Embed formatado
        """
        from utils.level_manager import get_level_from_xp

        embed = discord.Embed(
            title="🏆 Leaderboard de XP",
            description="Ranking de interação e níveis do servidor",
            color=0xffd700, # Gold
            timestamp=now_brt()
        )
        
        if not leaderboard:
            embed.description = "Nenhum dado disponível."
            return embed
        
        # Emojis de medalhas
        medals = ["🥇", "🥈", "🥉"]
        
        ranking_text = ""
        for i, user in enumerate(leaderboard, 1):
            medal = medals[i-1] if i <= 3 else f"**{i}.**"
            username = user['username']
            xp = user['total_points']
            lvl = get_level_from_xp(xp)
            ranking_text += f"{medal} **{username}** • `Nv. {lvl}` — **{xp:,} XP**\n"
        
        embed.add_field(
            name="🌟 Top Membros",
            value=ranking_text,
            inline=False
        )
        
        return embed

