# commands/gif_commands.py - Comandos Slash de Busca e Envio de GIFs

import logging
import discord
from discord import app_commands
from config import BMIA_DANCE_GIF_URL
from utils.giphy_client import GiphyClient, to_direct_gif_url

logger = logging.getLogger(__name__)


def setup_gif_slash_command(tree: app_commands.CommandTree, gif_client: GiphyClient):
    """Registra os comandos slash de GIF e dança na CommandTree do bot."""

    @tree.command(name="gif", description="Pesquisa e envia um GIF animado do GIPHY no canal")
    @app_commands.describe(busca="Termo ou emoção para pesquisar o GIF (ex: risada, comemoração, anime, lol, bmia)")
    async def gif_slash(interaction: discord.Interaction, busca: str):
        if not busca or not busca.strip():
            await interaction.response.send_message("❌ Digite um termo para buscar o GIF.", ephemeral=True)
            return

        await interaction.response.defer(thinking=False)

        try:
            b_lower = busca.strip().lower()
            if b_lower in ("bmia", "bmia danca", "bmia dança", "danca bmia", "dança bmia", "bmia dance", "dança do bmia", "danca do bmia"):
                direct_url = BMIA_DANCE_GIF_URL
            else:
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

    @tree.command(name="danca", description="BMIA faz sua dança engraçada característica!")
    async def danca_slash(interaction: discord.Interaction):
        await interaction.response.defer(thinking=False)
        try:
            embed = discord.Embed(
                title="🕺 Dança do BMIA!",
                description="*Mandando aquele passinho lendário...*",
                color=0x00f0ff,
            )
            embed.set_image(url=BMIA_DANCE_GIF_URL)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error("Erro ao executar comando /danca: %s", e, exc_info=True)
            await interaction.followup.send("❌ Ocorreu um erro ao enviar a dança do BMIA.", ephemeral=True)

