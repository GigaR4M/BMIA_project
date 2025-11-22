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
        Constrói embed com estatísticas de um usuário.
        
        Args:
            stats: Dicionário com estatísticas
            username: Nome do usuário
            avatar_url: URL do avatar (opcional)
            
        Returns:
            Embed formatado
        """
        embed = discord.Embed(
            title=f"📊 Estatísticas de {username}",
            color=self.COLOR_INFO,
            timestamp=datetime.now()
        )
        
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        
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
        
        # Top canais do usuário
        top_channels = stats.get('top_channels', [])
        if top_channels:
            channels_text = "\n".join([
                f"**#{ch['channel_name']}**: {ch['count']:,} mensagens"
                for ch in top_channels[:3]
            ])
            embed.add_field(
                name="📺 Canais Favoritos",
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
