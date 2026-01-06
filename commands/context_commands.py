
import discord
from discord import app_commands
import logging

logger = logging.getLogger(__name__)

class ContextCommands(app_commands.Group):
    """Comandos para gerenciar o contexto e memória do bot."""
    
    def __init__(self, db, memory_manager):
        super().__init__(name="context", description="Gerencia o contexto da IA do servidor")
        self.db = db
        self.memory_manager = memory_manager

    @app_commands.command(name="theme", description="Define o tema do servidor (Ex: 'Games e Diversão')")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_theme(self, interaction: discord.Interaction, text: str):
        await self.db.set_server_context(interaction.guild_id, "theme", text)
        await interaction.response.send_message(f"✅ Tema do servidor atualizado para: **{text}**")

    @app_commands.command(name="rules", description="Define regras principais que o bot deve saber")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_rules(self, interaction: discord.Interaction, text: str):
        await self.db.set_server_context(interaction.guild_id, "rules", text)
        await interaction.response.send_message(f"✅ Regras de contexto atualizadas.")

    @app_commands.command(name="tone", description="Define o tom de resposta desejado (Ex: 'Zoeiro', 'Formal')")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_tone(self, interaction: discord.Interaction, text: str):
        await self.db.set_server_context(interaction.guild_id, "tone", text)
        await interaction.response.send_message(f"✅ Tom do bot atualizado para: **{text}**")

    @app_commands.command(name="view", description="Vê o contexto atual do servidor")
    @app_commands.checks.has_permissions(administrator=True)
    async def view_context(self, interaction: discord.Interaction):
        ctx = await self.db.get_server_context(interaction.guild_id)
        if not ctx:
            await interaction.response.send_message("❌ Nenhum contexto definido ainda.")
            return

        embed = discord.Embed(title=f"🧠 Contexto: {interaction.guild.name}", color=discord.Color.blue())
        embed.add_field(name="🎨 Tema", value=ctx.get('theme', 'N/A'), inline=False)
        embed.add_field(name="📜 Regras", value=ctx.get('rules', 'N/A'), inline=False)
        embed.add_field(name="🎭 Tom", value=ctx.get('tone', 'N/A'), inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reset_user", description="Reseta suas preferências e memória de curto prazo")
    async def reset_user(self, interaction: discord.Interaction):
        # We don't have a direct method to delete profile in DB yet, but we can clear fields
        await self.db.update_user_bot_profile(interaction.user.id, interaction.guild_id, {
            "nickname_preference": None,
            "tone_preference": None,
            "interaction_summary": ""
        })
        await interaction.response.send_message("✅ Seu perfil de preferências na IA foi resetado.")
