# utils/embed_builder.py - Construtor de Embeds para Estatísticas

import discord
from typing import List, Dict, Any, Optional
from datetime import datetime


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
            timestamp=datetime.now()
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
        Constrói embed com estatísticas detalhadas de um usuário para auditoria.
        """
        total_points = stats.get('total_points', 0)
        
        embed = discord.Embed(
            title=f"📊 Ficha de: {username}",
            color=self.COLOR_INFO,
            timestamp=datetime.now()
        )
        
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        
        # Período
        period = stats.get('period_days', 30)
        period_text = "Ano Atual" if period > 365 else f"Últimos {period} dias"
        embed.add_field(name="📅 Período", value=period_text, inline=True)
        
        # Total Real de Pontos
        embed.add_field(name="🏆 Total de Pontos", value=f"**{total_points:,}**", inline=True)
        
        # Quebra de linha para separar o cabeçalho dos detalhes
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        
        # Auditoria (Detalhamento)
        total_msgs = stats.get('total_messages', 0)
        voice_mins = stats.get('voice_minutes', 0)
        
        # Formata tempo de voz
        voice_time_str = f"{voice_mins} min"
        if voice_mins >= 60:
            voice_time_str = f"{voice_mins // 60}h {voice_mins % 60}m"

        breakdown = stats.get('points_breakdown', {})
        points_msg = breakdown.get('message', 0)
        points_voice = breakdown.get('voice', 0)
        
        audit_text = (
            f"📝 **Mensagens:** {total_msgs:,} enviadas\n"
            f"🗣️ **Voz:** {voice_time_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"**Pontos de Mensagem:** {points_msg:,}\n"
            f"**Pontos de Voz:** {points_voice:,}\n"
        )
        
        # Adiciona outros tipos de pontos se houver (ex: daily, bonus)
        other_points = total_points - (points_msg + points_voice)
        if other_points > 0:
            audit_text += f"**Outros/Bônus:** {other_points:,}\n"
            
        audit_text += f"━━━━━━━━━━━━━━━━━━━━\n**TOTAL:** {total_points:,} pontos"

        embed.add_field(
            name="📋 Auditoria de Pontos",
            value=audit_text,
            inline=False
        )
        
        # Top canais
        top_channels = stats.get('top_channels', [])
        if top_channels:
            channels_text = "\n".join([
                f"**#{ch['channel_name']}**: {ch['count']:,} msgs"
                for ch in top_channels[:3]
            ])
            embed.add_field(
                name="📺 Canais Mais Ativos",
                value=channels_text,
                inline=False
            )
        
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
            timestamp=datetime.now()
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
            timestamp=datetime.now()
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
            timestamp=datetime.now()
        )
        
        return embed

    def build_leaderboard(self, leaderboard: List[Dict[str, Any]]) -> discord.Embed:
        """
        Constrói embed com leaderboard de pontos.
        
        Args:
            leaderboard: Lista de usuários com pontos
            
        Returns:
            Embed formatado
        """
        embed = discord.Embed(
            title="🏆 Leaderboard de Pontos",
            description="Ranking de interação do servidor",
            color=0xffd700, # Gold
            timestamp=datetime.now()
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
            points = user['total_points']
            ranking_text += f"{medal} **{username}** - {points:,} pontos\n"
        
        embed.add_field(
            name="🌟 Top Membros",
            value=ranking_text,
            inline=False
        )
        
        return embed
