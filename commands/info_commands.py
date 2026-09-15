import discord
from discord import app_commands
import logging

logger = logging.getLogger(__name__)

class InfoCommands(app_commands.Group):
    """Comandos informativos sobre o sistema."""

    def __init__(self):
        super().__init__(name="info", description="Comandos de informação")


    @app_commands.command(name="sistema_xp", description="Explica como funciona o sistema oficial de XP e Níveis")
    async def sistema_xp(self, interaction: discord.Interaction):
        """Exibe os detalhes do sistema de XP e Níveis."""
        embed = discord.Embed(
            title="⚡ Sistema Oficial de XP & Níveis BMIA",
            description="Ganhe XP participando do servidor, suba de nível e conquiste o topo do ranking!\nUse `/rank` para ver o seu Rank Card personalizado.",
            color=0x00f0ff
        )

        embed.add_field(
            name="💬 Chat de Texto",
            value=(
                "• **Mensagens curtas** (<10 caracteres): **+1 XP** (Máx 30/dia)\n"
                "• **Mensagens longas** (≥10 caracteres): **+2 XP**\n"
                "• **Responder alguém** (Reply): **+1 XP extra**\n"
                "• *Mensagens deletadas por moderação perdem XP.*"
            ),
            inline=False
        )

        embed.add_field(
            name="🎤 Chat de Voz & Streaming",
            value=(
                "• **Em Call** (falando/ouvindo): **+1 XP/min**\n"
                "• **Bônus de Galera** (2+ pessoas na call): **+1 XP/min**\n"
                "• **Fazendo Live** (Streaming p/ 2+ pessoas): **+1 XP/min**\n"
                "• *Estar mutado E ensurdecido (self-deaf) não gera XP.*"
            ),
            inline=False
        )

        embed.add_field(
            name="🎮 Jogos & Atividades",
            value=(
                "• **Jogando na Call**: **+1 XP/min** (acumula com voz)\n"
                "• **Jogando fora da Call**: **+1 XP a cada 2 min**\n"
                "• **Sinergia** (Jogando o mesmo jogo com amigos na call): **+1 XP/min**"
            ),
            inline=False
        )

        embed.add_field(
            name="🎖️ Progressão de Níveis",
            value=(
                "• A cada nível alcançado, você recebe um anúncio de **Level Up**!\n"
                "• Consulte `/rank` ou `/stats leaderboard` para acompanhar seu progresso."
            ),
            inline=False
        )

        embed.set_footer(text="O XP é sincronizado e verificado automaticamente a cada minuto.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="sistema_pontos", description="[Alias] Explica como funciona o sistema de XP e níveis")
    async def sistema_pontos(self, interaction: discord.Interaction):
        await self.sistema_xp(interaction)

