# commands/gif_commands.py - Comandos Slash de Busca e Envio de GIFs

import logging
import discord
from discord import app_commands
from utils.tenor_client import TenorClient

logger = logging.getLogger(__name__)


def setup_gif_slash_command(tree: app_commands.CommandTree, tenor_client: TenorClient):
    """Registra o comando slash /gif na CommandTree do bot."""

    @tree.command(name="gif", description="Pesquisa e envia um GIF animado do Tenor no canal")
    @app_commands.describe(busca="Termo ou emoção para pesquisar o GIF (ex: risada, comemoração, anime, lol)")
    async def gif_slash(interaction: discord.Interaction, busca: str):
        if not busca or not busca.strip():
            await interaction.response.send_message("❌ Digite um termo para buscar o GIF.", ephemeral=True)
            return

        await interaction.response.defer(thinking=False)

        try:
            gif_url = await tenor_client.search_gif_url(busca)
            if not gif_url:
                await interaction.followup.send(f"❌ Nenhum GIF encontrado para `{busca}`.", ephemeral=True)
                return

            await interaction.followup.send(content=gif_url)
        except Exception as e:
            logger.error("Erro ao executar comando /gif: %s", e, exc_info=True)
            await interaction.followup.send("❌ Ocorreu um erro ao buscar o GIF.", ephemeral=True)
