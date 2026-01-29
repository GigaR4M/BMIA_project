import discord
from discord import app_commands
import logging
from database import Database

logger = logging.getLogger(__name__)

class ModerationCommands(app_commands.Group):
    """Comandos de moderação do servidor."""

    def __init__(self, db: Database):
        super().__init__(name="moderacao", description="Configurações de moderação do servidor")
        self.db = db

    @app_commands.command(name="ia", description="Ativa ou desativa a moderação por Inteligência Artificial.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(ativar="Se True, a IA moderará mensagens ofensivas. Se False, desativa.")
    async def toggle_ai_moderation(self, interaction: discord.Interaction, ativar: bool):
        if not self.db:
            await interaction.response.send_message("❌ Banco de dados não disponível.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send("Este comando deve ser usado em um servidor.")
                return

            await self.db.set_ai_moderation(guild_id, ativar)
            
            status = "ATIVADA" if ativar else "DESATIVADA"
            emoji = "✅" if ativar else "🚫"
            
            await interaction.followup.send(f"{emoji} Moderação por IA **{status}** com sucesso!")
            logger.info(f"Moderação IA {status} em {interaction.guild.name} por {interaction.user.name}")

        except Exception as e:
            logger.error(f"Erro ao alterar moderação IA: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao salvar a configuração.")

    @toggle_ai_moderation.error
    async def toggle_ai_moderation_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("⛔ Você precisa de permissão de Administrador para usar este comando.", ephemeral=True)
        else:
            logger.error(f"Erro no comando moderacao ia: {error}")
            await interaction.response.send_message("❌ Ocorreu um erro ao processar o comando.", ephemeral=True)
