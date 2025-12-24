import discord
from discord import app_commands
import logging

logger = logging.getLogger(__name__)

class InfoCommands(app_commands.Group):
    """Comandos informativos sobre o sistema."""

    def __init__(self):
        super().__init__(name="info", description="Comandos de informação")

    @app_commands.command(name="sistema_pontos", description="Explica como funciona o sistema de pontos e níveis")
    async def sistema_pontos(self, interaction: discord.Interaction):
        """Exibe os detalhes do sistema de pontuação."""
        embed = discord.Embed(
            title="✨ Como funciona o Sistema de Pontos",
            description="Entenda como ganhar pontos e subir de nível no servidor!",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="💬 Chat de Texto",
            value=(
                "• **Mensagens curtas** (<10 caracteres): **1 ponto**\n"
                "• **Mensagens longas** (≥10 caracteres): **2 pontos**\n"
                "• **Responder alguém** (Reply): **+1 ponto extra**\n"
                "• *Mensagens apagadas por moderação perdem os pontos!*"
            ),
            inline=False
        )

        embed.add_field(
            name="😄 Reações",
            value=(
                "• **Reagir** a uma mensagem: **1 ponto**\n"
                "• **Receber reação** na sua mensagem: **1 ponto**\n"
                "• *Auto-reações não contam.*"
            ),
            inline=False
        )

        embed.add_field(
            name="🎤 Chat de Voz & Streaming",
            value=(
                "• **Na Call** (falando/ouvindo): **1 ponto/min**\n"
                "• **Bônus de Galera** (2+ pessoas na call): **+1 ponto/min**\n"
                "• **Fazendo Live** (Streaming paiado): **+1 ponto/min**\n"
                "• *Estar mutado E ensurdecido (self-deaf) não gera pontos.*"
            ),
            inline=False
        )

        embed.add_field(
            name="🎮 Jogos & Atividades",
            value=(
                "• **Jogando** (qualquer jogo detectado): **1 ponto/min**\n"
                "• **Sinergia** (Jogando o mesmo jogo com amigos na call): **+1 ponto/min**"
            ),
            inline=False
        )

        embed.set_footer(text="Os pontos são verificados automaticamente a cada minuto.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
