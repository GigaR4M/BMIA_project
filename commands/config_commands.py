# commands/config_commands.py — Slash Commands de Configuração do Servidor
"""
Permite que administradores configurem o bot via Discord, sem editar código.
Persiste as configurações no banco (guild_settings) para que funcionem
em qualquer servidor sem hardcode.
"""

import discord
from discord import app_commands
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ConfigCommands(app_commands.Group, name="config", description="Configurações do bot (admin)"):
    """Grupo de comandos /config para administradores."""

    def __init__(self, db, bot_ctx):
        super().__init__()
        self.db = db
        self.ctx = bot_ctx  # BotContext

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        """Verifica se o usuário tem permissão de administrador."""
        if not interaction.guild:
            return False
        member = interaction.guild.get_member(interaction.user.id)
        return member is not None and member.guild_permissions.administrator

    # ── Canais Permitidos ──────────────────────────────────────────────────────
    @app_commands.command(name="canal-pontos-adicionar", description="Adiciona um canal à lista de canais que dão pontos.")
    @app_commands.describe(canal="Canal de texto a adicionar")
    async def add_allowed_channel(
        self, interaction: discord.Interaction, canal: discord.TextChannel
    ) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        if canal.id in self.ctx.allowed_channels:
            await interaction.response.send_message(f"ℹ️ {canal.mention} já está na lista.", ephemeral=True)
            return

        self.ctx.allowed_channels.append(canal.id)
        await self.db.set_allowed_channels(interaction.guild.id, self.ctx.allowed_channels)
        await interaction.response.send_message(f"✅ {canal.mention} adicionado aos canais com pontos.", ephemeral=True)
        logger.info("Canal %s adicionado aos canais permitidos de %s", canal.name, interaction.guild.name)

    @app_commands.command(name="canal-pontos-remover", description="Remove um canal da lista de canais que dão pontos.")
    @app_commands.describe(canal="Canal de texto a remover")
    async def remove_allowed_channel(
        self, interaction: discord.Interaction, canal: discord.TextChannel
    ) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        if canal.id not in self.ctx.allowed_channels:
            await interaction.response.send_message(f"ℹ️ {canal.mention} não está na lista.", ephemeral=True)
            return

        self.ctx.allowed_channels.remove(canal.id)
        await self.db.set_allowed_channels(interaction.guild.id, self.ctx.allowed_channels)
        await interaction.response.send_message(f"✅ {canal.mention} removido dos canais com pontos.", ephemeral=True)

    @app_commands.command(name="canais-pontos-listar", description="Lista os canais que dão pontos neste servidor.")
    async def list_allowed_channels(self, interaction: discord.Interaction) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        if not self.ctx.allowed_channels:
            await interaction.response.send_message("Nenhum canal configurado.", ephemeral=True)
            return

        mentions = []
        for ch_id in self.ctx.allowed_channels:
            ch = interaction.guild.get_channel(ch_id) if interaction.guild else None
            mentions.append(ch.mention if ch else f"`{ch_id}`")

        embed = discord.Embed(
            title="📋 Canais com Pontos",
            description="\n".join(mentions),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Canais de Voz Ignorados ────────────────────────────────────────────────
    @app_commands.command(name="voz-ignorar-adicionar", description="Adiciona canal de voz à lista de canais ignorados (sem pontos).")
    @app_commands.describe(canal="Canal de voz a ignorar")
    async def add_ignored_voice(
        self, interaction: discord.Interaction, canal: discord.VoiceChannel
    ) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        if canal.id in self.ctx.ignored_voice_channels:
            await interaction.response.send_message(f"ℹ️ {canal.mention} já está ignorado.", ephemeral=True)
            return

        self.ctx.ignored_voice_channels.append(canal.id)
        await self.db.set_ignored_voice_channels(interaction.guild.id, self.ctx.ignored_voice_channels)
        await interaction.response.send_message(f"✅ {canal.mention} adicionado aos canais de voz ignorados.", ephemeral=True)

    @app_commands.command(name="voz-ignorar-remover", description="Remove canal de voz da lista de ignorados.")
    @app_commands.describe(canal="Canal de voz a reativar")
    async def remove_ignored_voice(
        self, interaction: discord.Interaction, canal: discord.VoiceChannel
    ) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        if canal.id not in self.ctx.ignored_voice_channels:
            await interaction.response.send_message(f"ℹ️ {canal.mention} não está na lista de ignorados.", ephemeral=True)
            return

        self.ctx.ignored_voice_channels.remove(canal.id)
        await self.db.set_ignored_voice_channels(interaction.guild.id, self.ctx.ignored_voice_channels)
        await interaction.response.send_message(f"✅ {canal.mention} reativado (dará pontos agora).", ephemeral=True)

    # ── Moderação IA ───────────────────────────────────────────────────────────
    @app_commands.command(name="moderacao", description="Ativa ou desativa a moderação por IA neste servidor.")
    @app_commands.describe(ativar="True para ativar, False para desativar")
    async def set_moderation(self, interaction: discord.Interaction, ativar: bool) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        await self.db.set_ai_moderation(interaction.guild.id, ativar)
        status = "✅ ativada" if ativar else "⏸️ desativada"
        await interaction.response.send_message(
            f"Moderação por IA {status} para **{interaction.guild.name}**.", ephemeral=True
        )

    # ── Ver configuração atual ─────────────────────────────────────────────────
    @app_commands.command(name="ver", description="Mostra a configuração atual do bot neste servidor.")
    async def show_config(self, interaction: discord.Interaction) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        guild_config = await self.db.get_guild_config(interaction.guild.id)

        ai_mod = guild_config.get("ai_moderation_enabled", True)
        allowed = guild_config.get("allowed_channels", [])
        ignored = guild_config.get("ignored_voice_channels", [])
        dyn_roles = guild_config.get("dynamic_roles_config", {})

        def ch_list(ids: list) -> str:
            if not ids:
                return "*(padrão do código)*"
            result = []
            for cid in ids:
                ch = interaction.guild.get_channel(cid)
                result.append(ch.mention if ch else f"`{cid}`")
            return ", ".join(result)

        embed = discord.Embed(
            title=f"⚙️ Configuração — {interaction.guild.name}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="🛡️ Moderação por IA", value="✅ Ativada" if ai_mod else "⏸️ Desativada", inline=False)
        embed.add_field(name="💬 Canais com Pontos", value=ch_list(allowed), inline=False)
        embed.add_field(name="🔇 Canais de Voz Ignorados", value=ch_list(ignored), inline=False)
        embed.add_field(
            name="🏅 Cargos Dinâmicos Configurados",
            value=f"{len(dyn_roles)} cargo(s)" if dyn_roles else "*(padrão do código)*",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
