# commands/gif_commands.py - Comandos Slash de Busca e Envio de GIFs

import logging
import discord
from discord import app_commands
from utils.giphy_client import GiphyClient, to_direct_gif_url

logger = logging.getLogger(__name__)


def setup_gif_slash_command(tree: app_commands.CommandTree, gif_client: GiphyClient):
    """Registra o comando slash /gif na CommandTree do bot."""

    @tree.command(name="gif", description="Pesquisa e envia um GIF animado do GIPHY no canal")
    @app_commands.describe(busca="Termo ou emoção para pesquisar o GIF (ex: risada, comemoração, anime, lol)")
    async def gif_slash(interaction: discord.Interaction, busca: str):
        if not busca or not busca.strip():
            await interaction.response.send_message("❌ Digite um termo para buscar o GIF.", ephemeral=True)
            return

        await interaction.response.defer(thinking=False)

        try:
            gif_url = await gif_client.search_gif_url(busca)
            if not gif_url:
                await interaction.followup.send(f"❌ Nenhum GIF encontrado para `{busca}`.", ephemeral=True)
                return

            direct_url = to_direct_gif_url(gif_url)
            embed = discord.Embed(color=0x2b2d31)
            embed.set_image(url=direct_url)
            embed.set_footer(text=f"🔍 {busca}")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error("Erro ao executar comando /gif: %s", e, exc_info=True)
            await interaction.followup.send("❌ Ocorreu um erro ao buscar o GIF.", ephemeral=True)
