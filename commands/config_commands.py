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

        guild_id = interaction.guild.id
        current_allowed = list(await self.ctx.get_allowed_channels(guild_id))
        if canal.id in current_allowed:
            await interaction.response.send_message(f"ℹ️ {canal.mention} já está na lista deste servidor.", ephemeral=True)
            return

        current_allowed.append(canal.id)
        await self.db.set_allowed_channels(guild_id, current_allowed)
        self.ctx.invalidate_guild_config(guild_id)
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

        guild_id = interaction.guild.id
        current_allowed = list(await self.ctx.get_allowed_channels(guild_id))
        if canal.id not in current_allowed:
            await interaction.response.send_message(f"ℹ️ {canal.mention} não está na lista deste servidor.", ephemeral=True)
            return

        current_allowed = [cid for cid in current_allowed if cid != canal.id]
        await self.db.set_allowed_channels(guild_id, current_allowed)
        self.ctx.invalidate_guild_config(guild_id)
        await interaction.response.send_message(f"✅ {canal.mention} removido dos canais com pontos.", ephemeral=True)

    @app_commands.command(name="canais-pontos-listar", description="Lista os canais que dão pontos neste servidor.")
    async def list_allowed_channels(self, interaction: discord.Interaction) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        allowed = await self.ctx.get_allowed_channels(guild_id)
        
        # Filtra apenas os canais pertencentes a este servidor
        guild_channel_ids = {ch.id for ch in interaction.guild.channels}
        server_allowed = [ch_id for ch_id in allowed if ch_id in guild_channel_ids or interaction.guild.get_channel(ch_id)]

        if not server_allowed:
            await interaction.response.send_message("Nenhum canal configurado para este servidor.", ephemeral=True)
            return

        mentions = [f"<#{ch_id}>" for ch_id in server_allowed]

        embed = discord.Embed(
            title="📋 Canais com Pontos",
            description="\n".join(mentions),
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Servidor: {interaction.guild.name}")
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

        guild_id = interaction.guild.id
        current_ignored = list(await self.ctx.get_ignored_voice_channels(guild_id))
        if canal.id in current_ignored:
            await interaction.response.send_message(f"ℹ️ {canal.mention} já está ignorado neste servidor.", ephemeral=True)
            return

        current_ignored.append(canal.id)
        await self.db.set_ignored_voice_channels(guild_id, current_ignored)
        self.ctx.invalidate_guild_config(guild_id)
        await interaction.response.send_message(f"✅ {canal.mention} adicionado aos canais de voz ignorados.", ephemeral=True)

    @app_commands.command(name="voz-ignorar-remover", description="Remove canal de voz da lista de ignorados.")
    @app_commands.describe(canal="Canal de voz a reativar")
    async def remove_ignored_voice(
        self, interaction: discord.Interaction, canal: discord.VoiceChannel
    ) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        current_ignored = list(await self.ctx.get_ignored_voice_channels(guild_id))
        if canal.id not in current_ignored:
            await interaction.response.send_message(f"ℹ️ {canal.mention} não está na lista de ignorados deste servidor.", ephemeral=True)
            return

        current_ignored = [cid for cid in current_ignored if cid != canal.id]
        await self.db.set_ignored_voice_channels(guild_id, current_ignored)
        self.ctx.invalidate_guild_config(guild_id)
        await interaction.response.send_message(f"✅ {canal.mention} reativado (dará pontos agora).", ephemeral=True)

    # ── Moderação IA ───────────────────────────────────────────────────────────
    @app_commands.command(name="moderacao", description="Ativa ou desativa a moderação por IA neste servidor.")
    @app_commands.describe(ativar="True para ativar, False para desativar")
    async def set_moderation(self, interaction: discord.Interaction, ativar: bool) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        await self.db.set_ai_moderation(interaction.guild.id, ativar)
        self.ctx.invalidate_guild_config(interaction.guild.id)
        status = "✅ ativada" if ativar else "⏸️ desativada"
        await interaction.response.send_message(
            f"Moderação por IA {status} para **{interaction.guild.name}**.", ephemeral=True
        )

    # ── Canal de Moderação / Alertas ───────────────────────────────────────────
    @app_commands.command(name="canal-moderacao", description="Define o canal onde serão enviados alertas de moderação e denúncias.")
    @app_commands.describe(canal="Canal de texto para receber alertas da Staff")
    async def set_moderation_channel(
        self, interaction: discord.Interaction, canal: discord.TextChannel
    ) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        await self.db.set_announcement_channel(interaction.guild.id, canal.id)
        self.ctx.invalidate_guild_config(interaction.guild.id)
        await interaction.response.send_message(
            f"✅ Canal de alertas de moderação e denúncias definido para {canal.mention}.",
            ephemeral=True
        )
        logger.info("Canal de moderação definido como %s em %s", canal.name, interaction.guild.name)

    # ── Canal de Jogos e Promoções ─────────────────────────────────────────────
    @app_commands.command(name="canal-jogos", description="Define o canal para anúncios de eventos Steam, promoções e rastreamento de links.")
    @app_commands.describe(canal="Canal de texto para sugestões de jogos e ofertas Steam")
    async def set_deals_channel(
        self, interaction: discord.Interaction, canal: discord.TextChannel
    ) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        await self.db.set_deals_channel(interaction.guild.id, canal.id)
        self.ctx.invalidate_guild_config(interaction.guild.id)
        await interaction.response.send_message(
            f"🎮 Canal de jogos e promoções Steam definido para {canal.mention}.",
            ephemeral=True
        )
        logger.info("Canal de jogos definido como %s em %s", canal.name, interaction.guild.name)

    @app_commands.command(name="canal-jogos-remover", description="Remove o canal personalizado de jogos (voltará a usar os canais principais).")
    async def remove_deals_channel(self, interaction: discord.Interaction) -> None:
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem usar este comando.", ephemeral=True)
            return

        await self.db.set_deals_channel(interaction.guild.id, None)
        self.ctx.invalidate_guild_config(interaction.guild.id)
        await interaction.response.send_message(
            "ℹ️ Canal de jogos personalizado removido. O bot usará os canais principais de conversa para anúncios e sugestões.",
            ephemeral=True
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
        ann_channel = guild_config.get("announcement_channel_id")
        deals_channel = guild_config.get("deals_channel_id")
        dyn_roles = guild_config.get("dynamic_roles_config", {})

        def ch_list(ids: list) -> str:
            if not ids:
                return "*(padrão do código)*"
            return ", ".join(f"<#{cid}>" for cid in ids)

        embed = discord.Embed(
            title=f"⚙️ Configuração — {interaction.guild.name}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="🛡️ Moderação por IA", value="✅ Ativada" if ai_mod else "⏸️ Desativada", inline=False)
        embed.add_field(name="🚨 Canal de Moderação / Alertas", value=f"<#{ann_channel}>" if ann_channel else "*(não configurado)*", inline=False)
        embed.add_field(name="🎮 Canal de Jogos e Promoções", value=f"<#{deals_channel}>" if deals_channel else "*(canais principais de bate-papo)*", inline=False)
        embed.add_field(name="💬 Canais com Pontos", value=ch_list(allowed), inline=False)
        embed.add_field(name="🔇 Canais de Voz Ignorados", value=ch_list(ignored), inline=False)
        embed.add_field(
            name="🏅 Cargos Dinâmicos Configurados",
            value=f"{len(dyn_roles)} cargo(s)" if dyn_roles else "*(padrão do código)*",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


