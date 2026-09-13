# commands/tournament_commands.py - Comandos de Gerenciamento de Torneios

import discord
from discord import app_commands
from database import Database
from typing import Optional, Any, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TournamentRegistrationView(discord.ui.View):
    """View interativa com botões para inscrição e controle de torneio."""

    def __init__(self, db: Database, tournament_id: int):
        super().__init__(timeout=None)
        self.db = db
        self.tournament_id = tournament_id

        # Adiciona os botões com custom_id persistente
        self.btn_join = discord.ui.Button(
            label="Inscrever-se",
            style=discord.ButtonStyle.success,
            emoji="🎮",
            custom_id=f"tourney_join_{tournament_id}"
        )
        self.btn_join.callback = self.callback_join

        self.btn_leave = discord.ui.Button(
            label="Cancelar Inscrição",
            style=discord.ButtonStyle.secondary,
            emoji="❌",
            custom_id=f"tourney_leave_{tournament_id}"
        )
        self.btn_leave.callback = self.callback_leave

        self.btn_list = discord.ui.Button(
            label="Ver Inscritos",
            style=discord.ButtonStyle.primary,
            emoji="📋",
            custom_id=f"tourney_list_{tournament_id}"
        )
        self.btn_list.callback = self.callback_list

        self.add_item(self.btn_join)
        self.add_item(self.btn_leave)
        self.add_item(self.btn_list)

    async def callback_join(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            # Garante que o usuário existe na tabela users
            await self.db.upsert_user(
                interaction.user.id,
                interaction.user.name,
                interaction.user.discriminator,
                interaction.user.bot
            )

            res = await self.db.add_tournament_participant(self.tournament_id, interaction.user.id)
            if not res.get("success"):
                await interaction.followup.send(f"⚠️ {res.get('reason', 'Não foi possível se inscrever.')}", ephemeral=True)
                return

            await interaction.followup.send(
                f"✅ **Inscrição confirmada!** Você está participando do torneio! ({res['count']}/{res['max']} vagas preenchidas)",
                ephemeral=True
            )

            # Atualiza o embed principal com a contagem de inscritos
            await self._update_main_embed(interaction, res["count"], res["max"])
        except Exception as e:
            logger.error(f"Erro ao inscrever no torneio {self.tournament_id}: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao processar sua inscrição.", ephemeral=True)

    async def callback_leave(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            res = await self.db.remove_tournament_participant(self.tournament_id, interaction.user.id)
            if not res.get("success"):
                await interaction.followup.send(f"⚠️ {res.get('reason', 'Não foi possível cancelar a inscrição.')}", ephemeral=True)
                return

            await interaction.followup.send(
                f"ℹ️ Sua inscrição foi cancelada com sucesso. ({res['count']}/{res['max']} vagas preenchidas)",
                ephemeral=True
            )

            await self._update_main_embed(interaction, res["count"], res["max"])
        except Exception as e:
            logger.error(f"Erro ao cancelar inscrição no torneio {self.tournament_id}: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao processar o cancelamento.", ephemeral=True)

    async def callback_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            tourney = await self.db.get_tournament(self.tournament_id)
            participants = await self.db.get_tournament_participants(self.tournament_id)

            if not tourney:
                await interaction.followup.send("❌ Torneio não encontrado.", ephemeral=True)
                return

            if not participants:
                await interaction.followup.send(f"📋 **Inscritos no Torneio #{tourney['id']} - {tourney['name']}:**\nNenhum participante inscrito ainda.", ephemeral=True)
                return

            lines = []
            for idx, p in enumerate(participants, 1):
                member = interaction.guild.get_member(p["user_id"])
                name = member.mention if member else (p.get("username") or f"ID: {p['user_id']}")
                lines.append(f"`#{idx:02d}` {name}")

            embed = discord.Embed(
                title=f"📋 Lista de Inscritos - {tourney['name']}",
                description="\n".join(lines),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Total: {len(participants)}/{tourney['max_participants']} vagas")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Erro ao listar inscritos do torneio {self.tournament_id}: {e}")
            await interaction.followup.send("❌ Erro ao buscar lista de participantes.", ephemeral=True)

    async def _update_main_embed(self, interaction: discord.Interaction, current_count: int, max_count: int):
        try:
            tourney = await self.db.get_tournament(self.tournament_id)
            if not tourney or not interaction.message:
                return

            embed = interaction.message.embeds[0]
            for idx, field in enumerate(embed.fields):
                if "Vagas" in field.name or "Inscritos" in field.name:
                    embed.set_field_at(
                        idx,
                        name="👥 Vagas / Inscritos",
                        value=f"**{current_count} / {max_count}**",
                        inline=True
                    )
                    break
            await interaction.message.edit(embed=embed)
        except Exception as e:
            logger.debug(f"Não foi possível atualizar mensagem do torneio: {e}")


class TournamentCommands(app_commands.Group):
    """Grupo de comandos para gerenciar torneios no servidor."""

    def __init__(self, db: Database, points_manager: Any = None):
        super().__init__(name="torneio", description="Gerenciamento de torneios do servidor")
        self.db = db
        self.points_manager = points_manager

    @app_commands.command(name="criar", description="Cria um novo torneio com embed e botões de inscrição")
    @app_commands.describe(
        nome="Nome do torneio (ex: Copa Roblox BMIA)",
        jogo="Jogo do torneio (ex: Roblox, Valorant, League of Legends)",
        vagas="Quantidade máxima de vagas (padrão: 16)",
        formato="Formato do torneio (ex: 1v1, 2v2, 5v5, Mata-Mata)",
        premio="Premiação do torneio (ex: 5.000 pontos + Cargo Campeão)",
        inicio="Data e hora de início (ex: Sábado às 20:00)"
    )
    @app_commands.checks.has_permissions(manage_events=True)
    async def criar_torneio(
        self,
        interaction: discord.Interaction,
        nome: str,
        jogo: str,
        vagas: int = 16,
        formato: str = "1v1",
        premio: Optional[str] = None,
        inicio: Optional[str] = None
    ):
        await interaction.response.defer()
        try:
            vagas = max(2, min(vagas, 128))

            tourney_id = await self.db.create_tournament(
                guild_id=interaction.guild.id,
                name=nome,
                game_name=jogo,
                format=formato,
                max_participants=vagas,
                prize=premio,
                created_by=interaction.user.id
            )

            embed = discord.Embed(
                title=f"🏆 NOVO TORNEIO: {nome}",
                description="Clique nos botões abaixo para participar do torneio!",
                color=discord.Color.gold()
            )
            embed.add_field(name="🎮 Jogo", value=f"**{jogo}**", inline=True)
            embed.add_field(name="⚔️ Formato", value=f"**{formato}**", inline=True)
            embed.add_field(name="👥 Vagas / Inscritos", value=f"**0 / {vagas}**", inline=True)

            if premio:
                embed.add_field(name="🎁 Premiação", value=f"**{premio}**", inline=False)
            if inicio:
                embed.add_field(name="⏰ Início", value=f"**{inicio}**", inline=False)

            embed.set_footer(text=f"Torneio ID: #{tourney_id} • Organizado por {interaction.user.display_name}")
            embed.timestamp = datetime.now()

            view = TournamentRegistrationView(self.db, tourney_id)
            message = await interaction.followup.send(embed=embed, view=view)

            # Atualiza message_id e channel_id no banco
            await self.db.update_tournament_message(tourney_id, interaction.channel.id, message.id)

        except Exception as e:
            logger.error(f"Erro ao criar torneio: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao criar o torneio. Verifique os parâmetros e tente novamente.")

    @app_commands.command(name="listar", description="Lista os torneios abertos ou recentes do servidor")
    async def listar_torneios(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            tourneys = await self.db.get_recent_tournaments(interaction.guild.id, limit=8)
            if not tourneys:
                await interaction.followup.send("📊 Nenhum torneio registrado neste servidor ainda.")
                return

            embed = discord.Embed(
                title=f"🏆 Torneios de {interaction.guild.name}",
                description="Lista dos últimos torneios organizados no servidor:",
                color=discord.Color.purple()
            )

            status_map = {
                "open": "🟢 Inscrições Abertas",
                "active": "🟡 Em Andamento",
                "completed": "🏁 Encerrado",
                "cancelled": "🔴 Cancelado"
            }

            for t in tourneys:
                st = status_map.get(t["status"], t["status"])
                val = [
                    f"🎮 **Jogo:** {t['game_name']} ({t.get('format', '1v1')})",
                    f"📊 **Status:** {st}",
                    f"👥 **Inscritos:** {t.get('participant_count', 0)}/{t['max_participants']}"
                ]
                if t["status"] == "completed" and t.get("winner_name"):
                    val.append(f"👑 **Campeão:** {t['winner_name']}")
                if t.get("prize"):
                    val.append(f"🎁 **Prêmio:** {t['prize']}")

                embed.add_field(
                    name=f"#{t['id']} - {t['name']}",
                    value="\n".join(val),
                    inline=False
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro ao listar torneios: {e}")
            await interaction.followup.send("❌ Erro ao consultar a lista de torneios.")

    @app_commands.command(name="status", description="Exibe detalhes e inscritos de um torneio específico")
    @app_commands.describe(id="ID do torneio")
    async def status_torneio(self, interaction: discord.Interaction, id: int):
        await interaction.response.defer()
        try:
            tourney = await self.db.get_tournament(id)
            if not tourney or tourney["guild_id"] != interaction.guild.id:
                await interaction.followup.send("❌ Torneio não encontrado.")
                return

            participants = await self.db.get_tournament_participants(id)

            status_map = {
                "open": "🟢 Inscrições Abertas",
                "active": "🟡 Em Andamento",
                "completed": "🏁 Encerrado",
                "cancelled": "🔴 Cancelado"
            }

            embed = discord.Embed(
                title=f"🏆 Torneio #{tourney['id']}: {tourney['name']}",
                color=discord.Color.gold()
            )
            embed.add_field(name="🎮 Jogo", value=tourney["game_name"], inline=True)
            embed.add_field(name="⚔️ Formato", value=tourney.get("format", "1v1"), inline=True)
            embed.add_field(name="📊 Status", value=status_map.get(tourney["status"], tourney["status"]), inline=True)
            embed.add_field(name="👥 Vagas", value=f"{len(participants)} / {tourney['max_participants']}", inline=True)

            if tourney.get("prize"):
                embed.add_field(name="🎁 Premiação", value=tourney["prize"], inline=True)

            if tourney["status"] == "completed" and tourney.get("winner_id"):
                winner = interaction.guild.get_member(tourney["winner_id"])
                embed.add_field(name="👑 Campeão", value=winner.mention if winner else f"<@{tourney['winner_id']}>", inline=False)

            if participants:
                p_list = []
                for idx, p in enumerate(participants[:20], 1):
                    m = interaction.guild.get_member(p["user_id"])
                    name = m.mention if m else (p.get("username") or f"ID: {p['user_id']}")
                    p_list.append(f"`#{idx:02d}` {name}")
                if len(participants) > 20:
                    p_list.append(f"*... e mais {len(participants) - 20} participantes.*")
                embed.add_field(name="📋 Participantes", value="\n".join(p_list), inline=False)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro ao exibir status do torneio {id}: {e}")
            await interaction.followup.send("❌ Erro ao consultar detalhes do torneio.")

    @app_commands.command(name="encerrar", description="Finaliza o torneio, registra o pódio e concede pontos aos vencedores")
    @app_commands.describe(
        id="ID do torneio",
        vencedor="Membro campeão (1º Lugar)",
        segundo_lugar="Membro vice-campeão (2º Lugar)",
        terceiro_lugar="Membro 3º Lugar (opcional)",
        pontos_vencedor="Pontos concedidos ao 1º lugar (opcional)",
        pontos_segundo="Pontos concedidos ao 2º lugar (opcional)"
    )
    @app_commands.checks.has_permissions(manage_events=True)
    async def encerrar_torneio(
        self,
        interaction: discord.Interaction,
        id: int,
        vencedor: discord.Member,
        segundo_lugar: Optional[discord.Member] = None,
        terceiro_lugar: Optional[discord.Member] = None,
        pontos_vencedor: int = 0,
        pontos_segundo: int = 0
    ):
        await interaction.response.defer()
        try:
            tourney = await self.db.get_tournament(id)
            if not tourney or tourney["guild_id"] != interaction.guild.id:
                await interaction.followup.send("❌ Torneio não encontrado.")
                return

            if tourney["status"] == "completed":
                await interaction.followup.send("⚠️ Este torneio já foi encerrado anteriormente.")
                return

            # Garante que os vencedores existem no banco
            for member in [vencedor, segundo_lugar, terceiro_lugar]:
                if member:
                    await self.db.upsert_user(member.id, member.name, member.discriminator, member.bot)

            # Finaliza no banco
            await self.db.finish_tournament(
                tournament_id=id,
                winner_id=vencedor.id,
                second_place_id=segundo_lugar.id if segundo_lugar else None,
                third_place_id=terceiro_lugar.id if terceiro_lugar else None
            )

            # Concede pontos aos ganhadores se especificado
            if pontos_vencedor > 0 and self.points_manager:
                await self.points_manager.add_points(
                    vencedor.id,
                    pontos_vencedor,
                    interaction.guild.id,
                    interaction_type="tournament_win"
                )
            if pontos_segundo > 0 and segundo_lugar and self.points_manager:
                await self.points_manager.add_points(
                    segundo_lugar.id,
                    pontos_segundo,
                    interaction.guild.id,
                    interaction_type="tournament_win"
                )

            # Monta o Pódio
            podium_embed = discord.Embed(
                title=f"🎉 PÓDIO OFICIAL: {tourney['name']}",
                description=f"O torneio de **{tourney['game_name']}** foi concluído com sucesso! Confira os vencedores:",
                color=discord.Color.gold()
            )

            podium_lines = [
                f"🥇 **1º Lugar (Campeão):** {vencedor.mention}" + (f" *(+{pontos_vencedor} pts)*" if pontos_vencedor > 0 else "")
            ]
            if segundo_lugar:
                podium_lines.append(f"🥈 **2º Lugar (Vice):** {segundo_lugar.mention}" + (f" *(+{pontos_segundo} pts)*" if pontos_segundo > 0 else ""))
            if terceiro_lugar:
                podium_lines.append(f"🥉 **3º Lugar:** {terceiro_lugar.mention}")

            podium_embed.add_field(name="🏆 Vencedores", value="\n".join(podium_lines), inline=False)
            if tourney.get("prize"):
                podium_embed.add_field(name="🎁 Premiação Concedida", value=tourney["prize"], inline=False)

            if vencedor.avatar:
                podium_embed.set_thumbnail(url=vencedor.avatar.url)
            podium_embed.set_footer(text=f"Torneio #{tourney['id']} • Parabéns a todos os participantes!")

            await interaction.followup.send(embed=podium_embed)

            # Desabilita botões da mensagem original se acessível
            if tourney.get("channel_id") and tourney.get("message_id"):
                try:
                    ch = interaction.guild.get_channel(tourney["channel_id"])
                    if ch:
                        orig_msg = await ch.fetch_message(tourney["message_id"])
                        if orig_msg:
                            orig_embed = orig_msg.embeds[0]
                            orig_embed.color = discord.Color.dark_grey()
                            orig_embed.title = f"🏁 [ENCERRADO] {tourney['name']}"
                            orig_embed.description = f"Torneio encerrado! Campeão: {vencedor.mention}"
                            await orig_msg.edit(embed=orig_embed, view=None)
                except Exception as msg_err:
                    logger.debug(f"Não foi possível atualizar mensagem original do torneio: {msg_err}")

        except Exception as e:
            logger.error(f"Erro ao encerrar torneio {id}: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao encerrar o torneio.")

    @app_commands.command(name="cancelar", description="Cancela um torneio aberto")
    @app_commands.describe(id="ID do torneio a ser cancelado")
    @app_commands.checks.has_permissions(manage_events=True)
    async def cancelar_torneio(self, interaction: discord.Interaction, id: int):
        await interaction.response.defer()
        try:
            tourney = await self.db.get_tournament(id)
            if not tourney or tourney["guild_id"] != interaction.guild.id:
                await interaction.followup.send("❌ Torneio não encontrado.")
                return

            if tourney["status"] == "completed":
                await interaction.followup.send("⚠️ Não é possível cancelar um torneio que já foi concluído.")
                return

            await self.db.cancel_tournament(id)
            await interaction.followup.send(f"🚫 **Torneio #{id} ({tourney['name']}) foi cancelado com sucesso.**")

            # Atualiza mensagem original
            if tourney.get("channel_id") and tourney.get("message_id"):
                try:
                    ch = interaction.guild.get_channel(tourney["channel_id"])
                    if ch:
                        orig_msg = await ch.fetch_message(tourney["message_id"])
                        if orig_msg:
                            orig_embed = orig_msg.embeds[0]
                            orig_embed.color = discord.Color.red()
                            orig_embed.title = f"🔴 [CANCELADO] {tourney['name']}"
                            orig_embed.description = "Este torneio foi cancelado pelos organizadores."
                            await orig_msg.edit(embed=orig_embed, view=None)
                except Exception as msg_err:
                    logger.debug(f"Não foi possível atualizar mensagem cancelada: {msg_err}")

        except Exception as e:
            logger.error(f"Erro ao cancelar torneio {id}: {e}")
            await interaction.followup.send("❌ Erro ao cancelar o torneio.")

    @app_commands.command(name="halldafama", description="Exibe os maiores campeões de torneios do servidor")
    @app_commands.describe(limit="Quantidade de campeões a mostrar (padrão: 5)")
    async def hall_da_fama(self, interaction: discord.Interaction, limit: int = 5):
        await interaction.response.defer()
        try:
            limit = max(1, min(limit, 20))
            champions = await self.db.get_tournament_hall_of_fame(interaction.guild.id, limit=limit)
            if not champions:
                await interaction.followup.send("🏆 Nenhum campeão registrado no Hall da Fama ainda.")
                return

            embed = discord.Embed(
                title=f"👑 Hall da Fama dos Campeões - {interaction.guild.name}",
                description="Os membros mais vitoriosos em torneios do servidor:",
                color=discord.Color.gold()
            )

            medals = ["🥇", "🥈", "🥉", "🏅", "🎖️"]
            lines = []
            for idx, c in enumerate(champions):
                medal = medals[idx] if idx < len(medals) else "🏆"
                member = interaction.guild.get_member(c["user_id"])
                name = member.mention if member else (c.get("username") or f"ID: {c['user_id']}")
                titles = c["titles_count"]
                plural = "título" if titles == 1 else "títulos"
                lines.append(f"{medal} **{name}** — **{titles}** {plural}")

            embed.description = "\n\n".join(lines)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro ao exibir Hall da Fama: {e}")
            await interaction.followup.send("❌ Erro ao carregar o Hall da Fama.")
