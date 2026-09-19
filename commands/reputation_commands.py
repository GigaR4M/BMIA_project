# commands/reputation_commands.py - Comandos de Reputação, Dossiê e Denúncias (Reports)

import discord
from discord import app_commands, ui
import logging
from datetime import datetime, timezone
from typing import Optional, List
from database import Database
from utils.reputation_manager import ReputationManager

logger = logging.getLogger(__name__)

REPORT_CATEGORIES = [
    discord.SelectOption(label="Spam / Divulgação Não Autorizada", value="spam", description="Mensagens repetitivas ou divulgação em massa", emoji="📢"),
    discord.SelectOption(label="Golpe / Scam / Phishing", value="scam", description="Links fraudulentos, roubo de contas ou promessas falsas", emoji="🎣"),
    discord.SelectOption(label="Conteúdo Adulto / NSFW", value="nsfw", description="Imagens, vídeos ou texto explícito em canais públicos", emoji="🔞"),
    discord.SelectOption(label="Gore / Violência Extrema", value="gore", description="Imagens ou vídeos de violência gráfica ou crueldade", emoji="🩸"),
    discord.SelectOption(label="Atividade Ilegal / Doxxing", value="illegal", description="Vazamento de dados privados ou atividade criminosa", emoji="⚠️"),
    discord.SelectOption(label="Assédio / Ofensas Graves", value="harassment", description="Ataques diretos, perseguição ou toxicidade excessiva", emoji="🚫"),
    discord.SelectOption(label="Outro Motivo", value="other", description="Qualquer outro comportamento que viole as regras", emoji="📝"),
]

class ReportModal(ui.Modal, title="🚨 Denunciar Usuário à Moderação"):
    category = ui.TextInput(
        label="Categoria (ex: spam, golpe, nsfw, ofensas)",
        placeholder="Digite o tipo da infração...",
        max_length=60,
        required=True
    )
    reason = ui.TextInput(
        label="Motivo Detalhado / Explicação",
        style=discord.TextStyle.paragraph,
        placeholder="Descreva detalhadamente o que aconteceu...",
        max_length=1000,
        required=True
    )
    proof_links = ui.TextInput(
        label="Links de Provas / Prints (Opcional)",
        placeholder="https://imgur.com/... ou link de mensagem",
        required=False,
        max_length=400
    )

    def __init__(self, db: Database, target_member: discord.Member, message: Optional[discord.Message] = None):
        super().__init__()
        self.db = db
        self.target_member = target_member
        self.message = message

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            guild_id = interaction.guild_id
            msg_content = self.message.content if self.message else None
            msg_id = self.message.id if self.message else None
            channel_id = self.message.channel.id if self.message else interaction.channel_id
            proofs = [self.proof_links.value.strip()] if self.proof_links.value.strip() else []

            report_id = await self.db.create_user_report(
                guild_id=guild_id,
                target_user_id=self.target_member.id,
                reporter_user_id=interaction.user.id,
                category=self.category.value.strip().lower(),
                reason=self.reason.value.strip(),
                message_content=msg_content,
                message_id=msg_id,
                channel_id=channel_id,
                attachment_urls=proofs
            )

            await interaction.followup.send(
                f"✅ **Denúncia #{report_id} enviada com sucesso!**\n"
                f"A equipe de moderação foi notificada e analisará o caso em breve. Obrigado por ajudar a manter o servidor seguro!",
                ephemeral=True
            )

            # Notificar canal de anúncios / moderação se configurado
            try:
                guild_config = await self.db.get_guild_config(guild_id)
                ann_channel_id = guild_config.get("announcement_channel_id")
                if ann_channel_id:
                    mod_channel = interaction.guild.get_channel(ann_channel_id)
                    if mod_channel:
                        embed = discord.Embed(
                            title=f"🚨 Nova Denúncia Registrada — #{report_id}",
                            description=f"**Acusado:** <@{self.target_member.id}> (`{self.target_member.name}`)\n"
                                        f"**Denunciante:** <@{interaction.user.id}> (`{interaction.user.name}`)\n"
                                        f"**Categoria:** `{self.category.value.strip()}`\n\n"
                                        f"**Motivo:**\n{self.reason.value.strip()}",
                            color=0xEF4444,
                            timestamp=datetime.now(timezone.utc)
                        )
                        if msg_content:
                            embed.add_field(name="💬 Mensagem Denunciada", value=msg_content[:500], inline=False)
                        if proofs:
                            embed.add_field(name="🔗 Provas", value="\n".join(proofs), inline=False)

                        view = ReportActionView(self.db, report_id, self.target_member.id)
                        await mod_channel.send(embed=embed, view=view)
            except Exception as notify_err:
                logger.warning(f"Não foi possível enviar alerta de denúncia no canal: {notify_err}")

        except Exception as e:
            logger.error(f"Erro ao processar denúncia para {self.target_member.id}: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao registrar sua denúncia. Tente novamente mais tarde.", ephemeral=True)


class ReportActionView(ui.View):
    """Botões de ação rápida para moderadores analisarem denúncias."""

    def __init__(self, db: Database, report_id: int, target_user_id: int):
        super().__init__(timeout=None)
        self.db = db
        self.report_id = report_id
        self.target_user_id = target_user_id

    @ui.button(label="✅ Aprovar Denúncia", style=discord.ButtonStyle.success, custom_id="report_approve")
    async def approve_report(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("⛔ Você não tem permissão para gerenciar denúncias.", ephemeral=True)
            return

        await self.db.update_report_status(self.report_id, "approved", interaction.user.id)
        # Registra infração
        await self.db.add_user_infraction(
            guild_id=interaction.guild_id,
            user_id=self.target_user_id,
            moderator_id=interaction.user.id,
            action_type="report_approved",
            reason=f"Denúncia #{self.report_id} confirmada e aprovada pela moderação."
        )

        for child in self.children:
            child.disabled = True
        button.label = "✅ Denúncia Aprovada"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🛡️ Denúncia #{self.report_id} foi **APROVADA** por {interaction.user.mention}.", ephemeral=False)

    @ui.button(label="❌ Descartar / Rejeitar", style=discord.ButtonStyle.secondary, custom_id="report_reject")
    async def reject_report(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("⛔ Você não tem permissão para gerenciar denúncias.", ephemeral=True)
            return

        await self.db.update_report_status(self.report_id, "rejected", interaction.user.id)

        for child in self.children:
            child.disabled = True
        button.label = "❌ Denúncia Descartada"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"Denúncia #{self.report_id} foi **REJEITADA** por {interaction.user.mention}.", ephemeral=True)


class ReputationCommands(app_commands.Group):
    """Comandos de Reputação, Dossiê de Segurança e Moderação."""

    def __init__(self, db: Database):
        super().__init__(name="seguranca", description="Comandos de reputação e segurança do servidor")
        self.db = db

    @app_commands.command(name="dossie", description="Exibe o dossiê completo de reputação e histórico de um membro (Staff Only).")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(membro="Membro que deseja consultar")
    async def get_user_dossier(self, interaction: discord.Interaction, membro: discord.Member):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            now = datetime.now(timezone.utc)
            
            # Idade da conta e tempo no servidor
            account_created = membro.created_at
            account_age_days = (now - account_created).days
            joined_server = membro.joined_at or now
            server_membership_days = (now - joined_server).days

            # Busca dossiê consolidado no banco
            dossier_data = await self.db.get_user_full_dossier(guild.id, membro.id)
            infractions_summary = dossier_data.get("infractions_summary", {})
            reports = dossier_data.get("reports", [])
            approved_reports = [r for r in reports if r.get("status") == "approved"]
            moderated_messages = dossier_data.get("moderated_messages_count", 0)
            
            # Sinais nativos do Discord
            is_timed_out = membro.is_timed_out()
            timed_out_until = membro.timed_out_until
            flags = membro.flags

            # Calcula Trust Score
            trust_info = ReputationManager.calculate_trust_score(
                account_age_days=account_age_days,
                server_membership_days=server_membership_days,
                infractions_summary=infractions_summary,
                reports_count=len(reports),
                approved_reports_count=len(approved_reports),
                moderated_messages_count=moderated_messages,
                is_currently_timed_out=is_timed_out
            )

            # Monta Embed Principal do Dossiê
            embed = discord.Embed(
                title=f"🛡️ Dossiê de Segurança — {membro.name}",
                description=f"**Classificação de Confiança:** `{trust_info['label']}`\n"
                            f"**Trust Score:** `{trust_info['score']}/100`",
                color=trust_info['color_hex'],
                timestamp=now
            )
            embed.set_thumbnail(url=membro.display_avatar.url)

            # 1. Identificação & Adesão
            join_source = dossier_data.get("join_source")
            invite_str = "Não rastreado"
            if join_source and join_source.get("invite_code"):
                inv_code = join_source.get("invite_code")
                inviter_name = join_source.get("inviter_username") or f"<@{join_source.get('inviter_id')}>"
                invite_str = f"`discord.gg/{inv_code}` (por {inviter_name})"

            embed.add_field(
                name="👤 Identificação & Adesão",
                value=f"• **ID:** `{membro.id}`\n"
                      f"• **Conta criada:** <t:{int(account_created.timestamp())}:R> ({account_age_days} dias)\n"
                      f"• **Entrou no servidor:** <t:{int(joined_server.timestamp())}:R> ({server_membership_days} dias)\n"
                      f"• **Convite usado:** {invite_str}",
                inline=False
            )

            # 2. Sinais Atuais do Discord
            status_sinais = []
            if is_timed_out:
                status_sinais.append(f"⛔ **De Castigo:** Até <t:{int(timed_out_until.timestamp())}:R>")
            else:
                status_sinais.append("🟢 **Castigo:** Nenhum ativo")

            # Quarentena / AutoMod
            quarantine_flags = []
            if getattr(flags, 'automod_quarantined_username', False):
                quarantine_flags.append("Nome de Usuário em Quarentena")
            if getattr(flags, 'automod_quarantined_bio', False):
                quarantine_flags.append("Bio em Quarentena")
            
            if quarantine_flags:
                status_sinais.append(f"⚠️ **Quarentena AutoMod:** {', '.join(quarantine_flags)}")
            else:
                status_sinais.append("✅ **Quarentena:** Nenhuma flag ativa")

            embed.add_field(
                name="📡 Sinais do Discord",
                value="\n".join(status_sinais),
                inline=False
            )

            # 3. Resumo de Infrações
            inf_lines = []
            warn_count = infractions_summary.get("warn", {}).get("count", 0)
            timeout_count = infractions_summary.get("timeout", {}).get("count", 0)
            mute_count = infractions_summary.get("mute", {}).get("count", 0) + infractions_summary.get("hardmute", {}).get("count", 0)
            kick_count = infractions_summary.get("kick", {}).get("count", 0) + infractions_summary.get("softban", {}).get("count", 0)
            ban_count = infractions_summary.get("ban", {}).get("count", 0) + infractions_summary.get("tempban", {}).get("count", 0)

            inf_lines.append(f"• **Advertências:** `{warn_count}`")
            inf_lines.append(f"• **Castigos (Timeouts):** `{timeout_count}`")
            inf_lines.append(f"• **Mutes / Hardmutes:** `{mute_count}`")
            inf_lines.append(f"• **Expulsões (Kicks):** `{kick_count}`")
            inf_lines.append(f"• **Banimentos Anteriores:** `{ban_count}`")
            inf_lines.append(f"• **Msgs Deletadas pela IA:** `{moderated_messages}`")
            inf_lines.append(f"• **Denúncias Recebidas:** `{len(reports)}` (`{len(approved_reports)}` aprovadas)")

            embed.add_field(
                name="📜 Histórico de Infrações",
                value="\n".join(inf_lines),
                inline=False
            )

            # 4. Detalhes de Penalidades no Trust Score
            if trust_info['penalties']:
                penalties_str = "\n".join([f"• 🔻 `{p[0]}`: -{p[1]} pts" for p in trust_info['penalties']])
                embed.add_field(name="⚖️ Fatores de Penalidade", value=penalties_str, inline=False)

            embed.set_footer(text="BMIA Security & Intelligence Suite • Uso estrito da Moderação")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Erro ao gerar dossiê para {membro.id}: {e}")
            await interaction.followup.send(f"❌ Erro ao consultar dossiê: {e}", ephemeral=True)

    @get_user_dossier.error
    async def dossier_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("⛔ Apenas membros da Staff podem consultar dossiês de segurança.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ocorreu um erro ao processar o comando.", ephemeral=True)


# ==================== COMANDO GLOBAL /REPORT ====================

@app_commands.command(name="report", description="Denuncie um usuário por má conduta ou violação de regras.")
@app_commands.describe(membro="Membro que você deseja denunciar")
async def report_user_command(interaction: discord.Interaction, membro: discord.Member):
    """Comando aberto para todos os membros reportarem abusos."""
    if membro.id == interaction.user.id:
        await interaction.response.send_message("❌ Você não pode denunciar a si mesmo.", ephemeral=True)
        return
    if membro.bot:
        await interaction.response.send_message("❌ Você não pode denunciar bots através deste comando.", ephemeral=True)
        return

    # Instância do banco passada pelo setup
    db: Database = interaction.client.ctx.db if hasattr(interaction.client, 'ctx') else None
    modal = ReportModal(db, membro)
    await interaction.response.send_modal(modal)


# ==================== CONTEXT MENU (CLIQUE DIREITO) ====================

@app_commands.context_menu(name="Reportar Mensagem")
async def report_message_context(interaction: discord.Interaction, message: discord.Message):
    """Permite denunciar diretamente uma mensagem ofensiva com clique direito."""
    if message.author.id == interaction.user.id:
        await interaction.response.send_message("❌ Você não pode denunciar sua própria mensagem.", ephemeral=True)
        return

    db: Database = interaction.client.ctx.db if hasattr(interaction.client, 'ctx') else None
    modal = ReportModal(db, message.author, message=message)
    await interaction.response.send_modal(modal)
