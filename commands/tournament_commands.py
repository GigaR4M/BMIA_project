# commands/tournament_commands.py - Comandos de Gerenciamento de Torneios

import discord
from discord import app_commands
from database import Database
from typing import Optional, Any, List
import logging
import json
from datetime import datetime
from utils.image_generator import BracketBuilder, LeagueTableBuilder

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
            avatar_url = str(interaction.user.display_avatar.url) if hasattr(interaction.user, 'display_avatar') else None
            await self.db.upsert_user(
                interaction.user.id,
                interaction.user.name,
                interaction.user.discriminator,
                interaction.user.bot,
                avatar_url=avatar_url
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
        nome="Nome do torneio (ex: Copa Rocket League BMIA)",
        jogo="Jogo do torneio (ex: Rocket League, Roblox, Valorant)",
        formato="Formato de disputa (1v1, 2v2, 3v3, 5v5)",
        vagas="Quantidade total de vagas/participantes",
        tipo="Tipo de torneio: Mata-Mata (Chaveamento) ou Pontos Corridos (Liga)",
        premio="Premiação do torneio (ex: 5.000 pontos + Cargo Campeão)",
        inicio="Data e hora de início (ex: Sábado às 20:00)"
    )
    @app_commands.choices(
        formato=[
            app_commands.Choice(name="1v1 (Individual)", value="1v1"),
            app_commands.Choice(name="2v2 (Duplas)", value="2v2"),
            app_commands.Choice(name="3v3 (Trios)", value="3v3"),
            app_commands.Choice(name="5v5 (Equipes)", value="5v5"),
        ],
        vagas=[
            app_commands.Choice(name="2 Participantes (Final Direta em 1v1)", value=2),
            app_commands.Choice(name="4 Participantes (Final em 2v2 / Semis em 1v1)", value=4),
            app_commands.Choice(name="8 Participantes (Semis em 2v2 / Quartas em 1v1)", value=8),
            app_commands.Choice(name="16 Participantes (Quartas em 2v2 / Oitavas em 1v1)", value=16),
            app_commands.Choice(name="32 Participantes", value=32),
        ],
        tipo=[
            app_commands.Choice(name="Mata-Mata (Chaveamento Eliminatório)", value="bracket"),
            app_commands.Choice(name="Pontos Corridos (Liga / Todos contra Todos)", value="round_robin"),
        ]
    )
    @app_commands.checks.has_permissions(manage_events=True)
    async def criar_torneio(
        self,
        interaction: discord.Interaction,
        nome: str,
        jogo: str,
        formato: app_commands.Choice[str],
        vagas: app_commands.Choice[int],
        tipo: Optional[app_commands.Choice[str]] = None,
        premio: Optional[str] = None,
        inicio: Optional[str] = None
    ):
        await interaction.response.defer()
        try:
            vagas_val = vagas.value if isinstance(vagas, app_commands.Choice) else int(vagas)
            formato_val = formato.value if isinstance(formato, app_commands.Choice) else str(formato)
            tipo_val = tipo.value if isinstance(tipo, app_commands.Choice) else (str(tipo) if tipo else "bracket")
            vagas_val = max(2, min(vagas_val, 128))

            tourney_id = await self.db.create_tournament(
                guild_id=interaction.guild.id,
                name=nome,
                game_name=jogo,
                format=formato_val,
                max_participants=vagas_val,
                prize=premio,
                created_by=interaction.user.id,
                tournament_type=tipo_val
            )

            tipo_label = "⚡ Pontos Corridos (Liga)" if tipo_val == "round_robin" else "🏆 Mata-Mata (Chaveamento)"

            embed = discord.Embed(
                title=f"🏆 NOVO TORNEIO: {nome}",
                description="Clique nos botões abaixo para participar do torneio!",
                color=discord.Color.gold()
            )
            embed.add_field(name="🎮 Jogo", value=f"**{jogo}**", inline=True)
            embed.add_field(name="⚔️ Formato", value=f"**{formato_val.upper()}**", inline=True)
            embed.add_field(name="📊 Tipo", value=f"**{tipo_label}**", inline=True)
            embed.add_field(name="👥 Vagas / Inscritos", value=f"**0 / {vagas_val}**", inline=True)

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
    @app_commands.describe(id="ID do torneio (opcional, padrão: torneio ativo ou mais recente)")
    async def status_torneio(self, interaction: discord.Interaction, id: Optional[int] = None):
        await interaction.response.defer()
        try:
            if id is None:
                active = await self.db.get_active_tournaments(interaction.guild.id)
                if active:
                    id = active[0]["id"]
                else:
                    recent = await self.db.get_recent_tournaments(interaction.guild.id, limit=1)
                    if recent:
                        id = recent[0]["id"]
                    else:
                        await interaction.followup.send("❌ Nenhum torneio encontrado neste servidor. Use `/torneio criar` para criar um.")
                        return

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

            t_type = tourney.get("tournament_type") or "bracket"
            tipo_label = "⚡ Pontos Corridos (Liga)" if t_type == "round_robin" else "🏆 Mata-Mata (Chaveamento)"

            embed = discord.Embed(
                title=f"🏆 Torneio #{tourney['id']}: {tourney['name']}",
                color=discord.Color.gold()
            )
            embed.add_field(name="🎮 Jogo", value=tourney["game_name"], inline=True)
            embed.add_field(name="⚔️ Formato", value=tourney.get("format", "1v1").upper(), inline=True)
            embed.add_field(name="📊 Tipo", value=tipo_label, inline=True)
            embed.add_field(name="📊 Status", value=status_map.get(tourney["status"], tourney["status"]), inline=True)
            embed.add_field(name="👥 Vagas", value=f"{len(participants)} / {tourney['max_participants']}", inline=True)

            if t_type == "round_robin":
                standings = await self.db.get_tournament_standings(id)
                if standings:
                    leader_str = standings[0]["team_name"]
                    pts = standings[0]["points"]
                    embed.add_field(name="🥇 Líder da Liga", value=f"**{leader_str}** ({pts} pts)", inline=True)

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

    @app_commands.command(name="encerrar", description="Encerra um torneio, define os vencedores e distribui os pontos")
    @app_commands.describe(
        id="ID do torneio a ser encerrado",
        vencedor="Membro campeão do torneio",
        segundo_lugar="Membro que ficou em 2º lugar (Vice)",
        terceiro_lugar="Membro que ficou em 3º lugar",
        pontos_vencedor="Pontos adicionais para o campeão (opcional)",
        pontos_segundo="Pontos adicionais para o vice (opcional)",
        placar="Placar da Grande Final (ex: '3x1' ou '4x2')"
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
        pontos_segundo: int = 0,
        placar: Optional[str] = None
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

            participants = await self.db.get_tournament_participants(id)
            fmt_raw = str(tourney.get("format", "1v1")).lower().strip()
            is_2v2 = any(k in fmt_raw for k in ["2v2", "2x2", "dupla", "duplas"])
            is_3v3 = any(k in fmt_raw for k in ["3v3", "3x3", "trio", "trios"])
            team_size = 2 if is_2v2 else (3 if is_3v3 else 1)

            # Localiza todos os integrantes da equipe a partir de um capitão/jogador selecionado
            async def find_team_members(target_member: Optional[discord.Member]) -> List[discord.Member]:
                if not target_member:
                    return []
                if team_size == 1 or not participants:
                    return [target_member]

                found_chunk = None
                for i in range(0, len(participants), team_size):
                    chunk = participants[i:i + team_size]
                    if any(p.get("user_id") == target_member.id for p in chunk):
                        found_chunk = chunk
                        break

                if not found_chunk:
                    return [target_member]

                team_members = []
                for p in found_chunk:
                    p_id = p.get("user_id")
                    m = interaction.guild.get_member(p_id)
                    if not m:
                        try:
                            m = await interaction.guild.fetch_member(p_id)
                        except Exception:
                            m = None
                    if m:
                        team_members.append(m)
                return team_members if team_members else [target_member]

            winner_team = await find_team_members(vencedor)
            runner_up_team = await find_team_members(segundo_lugar) if segundo_lugar else []
            third_place_team = await find_team_members(terceiro_lugar) if terceiro_lugar else []

            # Garante que todos os membros existem no banco
            for member in winner_team + runner_up_team + third_place_team:
                if member:
                    m_avatar = str(member.display_avatar.url) if hasattr(member, 'display_avatar') else None
                    await self.db.upsert_user(member.id, member.name, member.discriminator, member.bot, avatar_url=m_avatar)

            # Finaliza no banco com todos os IDs de cada equipe e placar
            await self.db.finish_tournament(
                tournament_id=id,
                winner_id=vencedor.id,
                second_place_id=segundo_lugar.id if segundo_lugar else None,
                third_place_id=terceiro_lugar.id if terceiro_lugar else None,
                winner_ids=[m.id for m in winner_team],
                second_place_ids=[m.id for m in runner_up_team],
                third_place_ids=[m.id for m in third_place_team],
                final_score=placar
            )

            # Concede pontos aos ganhadores se especificado
            if pontos_vencedor > 0 and self.points_manager:
                for m in winner_team:
                    m_avatar = str(m.display_avatar.url) if hasattr(m, 'display_avatar') else None
                    await self.points_manager.add_points(
                        m.id,
                        pontos_vencedor,
                        "tournament_win",
                        interaction.guild.id,
                        m.name,
                        m.discriminator,
                        m.bot,
                        avatar_url=m_avatar
                    )
            if pontos_segundo > 0 and self.points_manager:
                for m in runner_up_team:
                    m_avatar = str(m.display_avatar.url) if hasattr(m, 'display_avatar') else None
                    await self.points_manager.add_points(
                        m.id,
                        pontos_segundo,
                        "tournament_win",
                        interaction.guild.id,
                        m.name,
                        m.discriminator,
                        m.bot,
                        avatar_url=m_avatar
                    )

            # Monta o Pódio
            podium_embed = discord.Embed(
                title=f"🎉 PÓDIO OFICIAL: {tourney['name']}",
                description=f"O torneio de **{tourney['game_name']}** foi concluído com sucesso! Confira os vencedores:",
                color=discord.Color.gold()
            )

            winners_mention = " & ".join([m.mention for m in winner_team])
            pts_win_str = f" *(+{pontos_vencedor} pts cada)*" if pontos_vencedor > 0 and len(winner_team) > 1 else (f" *(+{pontos_vencedor} pts)*" if pontos_vencedor > 0 else "")
            label_1st = "Campeões" if len(winner_team) > 1 else "Campeão"
            podium_lines = [
                f"🥇 **1º Lugar ({label_1st}):** {winners_mention}{pts_win_str}"
            ]

            if runner_up_team:
                runners_mention = " & ".join([m.mention for m in runner_up_team])
                pts_sec_str = f" *(+{pontos_segundo} pts cada)*" if pontos_segundo > 0 and len(runner_up_team) > 1 else (f" *(+{pontos_segundo} pts)*" if pontos_segundo > 0 else "")
                label_2nd = "Vice-Campeões" if len(runner_up_team) > 1 else "Vice"
                podium_lines.append(f"🥈 **2º Lugar ({label_2nd}):** {runners_mention}{pts_sec_str}")

            if third_place_team:
                thirds_mention = " & ".join([m.mention for m in third_place_team])
                podium_lines.append(f"🥉 **3º Lugar:** {thirds_mention}")

            podium_embed.add_field(name="🏆 Vencedores", value="\n".join(podium_lines), inline=False)
            
            final_placar_display = placar or tourney.get("final_score")
            if final_placar_display:
                podium_embed.add_field(name="⚽ Placar da Final", value=f"`{final_placar_display}`", inline=True)

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
                            orig_embed.description = f"Torneio encerrado! Campeões: {winners_mention}"
                            await orig_msg.edit(embed=orig_embed, view=None)
                except Exception as msg_err:
                    logger.debug(f"Não foi possível atualizar mensagem original do torneio: {msg_err}")

        except Exception as e:
            logger.error(f"Erro ao encerrar torneio {id}: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao encerrar o torneio.")

    @app_commands.command(name="partida", description="Registra o placar de uma partida e avança a fase ou pontua na liga")
    @app_commands.describe(
        id="ID do torneio",
        jogo="Número da partida (1, 2, 3...)",
        placar="Placar da partida (ex: '3x1', '2x0', '1x1')",
        vencedor="Membro da equipe vencedora (opcional se houver empate ou placar evidente)"
    )
    @app_commands.checks.has_permissions(manage_events=True)
    async def registrar_partida(
        self,
        interaction: discord.Interaction,
        id: int,
        jogo: int,
        placar: str,
        vencedor: Optional[discord.Member] = None
    ):
        await interaction.response.defer()
        try:
            tourney = await self.db.get_tournament(id)
            if not tourney or tourney["guild_id"] != interaction.guild.id:
                await interaction.followup.send("❌ Torneio não encontrado.")
                return

            if tourney["status"] == "completed":
                await interaction.followup.send("⚠️ Este torneio já foi concluído.")
                return

            import re
            nums = re.findall(r'\d+', placar)
            if len(nums) < 2:
                await interaction.followup.send("⚠️ Formato de placar inválido. Use por exemplo: `3x1`, `2x0` ou `3-2`.")
                return

            score_a = int(nums[0])
            score_b = int(nums[1])

            matches = await self.db.get_tournament_matches(id)
            target_match = next((m for m in matches if m["match_number"] == jogo), None)
            if not target_match:
                await interaction.followup.send(f"❌ Partida #{jogo} não encontrada no calendário deste torneio.")
                return

            team_a = target_match.get("team_a_ids") or []
            team_b = target_match.get("team_b_ids") or []

            if not team_a or not team_b:
                await interaction.followup.send(f"⚠️ A Partida #{jogo} ainda não possui as duas equipes definidas.")
                return

            is_draw = (score_a == score_b)
            t_type = tourney.get("tournament_type") or "bracket"

            if is_draw and t_type != "round_robin":
                await interaction.followup.send("⚠️ Em torneios de mata-mata não são permitidos empates. Deve haver um vencedor.")
                return

            winner_team_ids = []
            if not is_draw:
                if vencedor:
                    if vencedor.id in team_a:
                        winner_team_ids = team_a
                    elif vencedor.id in team_b:
                        winner_team_ids = team_b
                    else:
                        await interaction.followup.send(f"⚠️ O membro {vencedor.mention} não faz parte de nenhuma das equipes da Partida #{jogo}.")
                        return
                else:
                    winner_team_ids = team_a if score_a > score_b else team_b

            res = await self.db.record_match_result(
                tournament_id=id,
                match_number=jogo,
                score_a=score_a,
                score_b=score_b,
                winner_team_ids=winner_team_ids if not is_draw else None
            )

            if not res.get("success"):
                await interaction.followup.send(f"❌ {res.get('reason', 'Erro ao registrar resultado da partida.')}")
                return

            round_title = target_match.get("round_name", "").upper()

            if is_draw:
                embed = discord.Embed(
                    title=f"⚔️ Resultado da Partida #{jogo} — {round_title}",
                    description=f"🎮 **Torneio:** {tourney['name']}\n🔢 **Placar:** `{score_a} x {score_b}`\n🤝 **Resultado:** **EMPATE!** (1 ponto para cada equipe)",
                    color=discord.Color.gold()
                )
            else:
                winner_names = []
                for uid in winner_team_ids:
                    m = interaction.guild.get_member(uid)
                    winner_names.append(m.mention if m else f"<@{uid}>")
                winner_str = " & ".join(winner_names)

                embed = discord.Embed(
                    title=f"⚔️ Resultado da Partida #{jogo} — {round_title}",
                    description=f"🎮 **Torneio:** {tourney['name']}\n🔢 **Placar Registrado:** `{score_a} x {score_b}`\n🏆 **Equipe Vencedora:** {winner_str}",
                    color=discord.Color.from_rgb(0, 240, 255)
                )

            if t_type == "round_robin":
                standings = await self.db.get_tournament_standings(id)
                top_lines = []
                medals = ["🥇", "🥈", "🥉"]
                for idx, s in enumerate(standings[:3]):
                    top_lines.append(f"{medals[idx]} **{s['team_name']}** — {s['points']} pts ({s['won']}V-{s['drawn']}E-{s['lost']}D, SG: {s['goal_diff']})")

                if top_lines:
                    embed.add_field(name="📊 Top 3 Atual da Liga", value="\n".join(top_lines), inline=False)

                if res.get("all_completed"):
                    champ = standings[0] if standings else None
                    champ_str = champ['team_name'] if champ else "A definir"
                    champ_id = champ['team_ids'][0] if champ and champ.get('team_ids') else None
                    mention_cmd = f" vencedor:<@{champ_id}>" if champ_id else ""
                    embed.add_field(
                        name="👑 LIGA CONCLUÍDA!",
                        value=f"Todas as rodadas foram finalizadas!\n🏆 **Campeão da Liga:** **{champ_str}** com **{champ['points'] if champ else 0} pontos**!\nUtilize `/torneio encerrar id:{id}{mention_cmd}` para oficializar o pódio.",
                        inline=False
                    )

                embed.set_footer(text=f"Use /torneio tabela id:{id} para visualizar a classificação completa atualizada.")
            else:
                if res.get("is_final"):
                    winner_mention = vencedor.mention if vencedor else (winner_str if not is_draw else "")
                    embed.add_field(
                        name="👑 Grande Final Finalizada!",
                        value=f"A Grande Final foi concluída com placar **{score_a} x {score_b}**!\nUtilize `/torneio encerrar id:{id} vencedor:{winner_mention} placar:'{score_a} x {score_b}'` para oficializar a premiação e o pódio.",
                        inline=False
                    )
                elif res.get("next_match_number"):
                    embed.add_field(
                        name="🚀 Avanço de Fase",
                        value=f"A equipe {winner_str} avançou para a **Partida #{res['next_match_number']}** do chaveamento!",
                        inline=False
                    )

                embed.set_footer(text=f"Use /torneio chaveamento id:{id} para visualizar o chaveamento atualizado.")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro ao registrar partida do torneio {id}: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao registrar o resultado da partida.")

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
                description="Os membros mais vitoriosos em torneios do servidor:\n",
                color=discord.Color.gold()
            )

            medals = ["🥇", "🥈", "🥉", "🏅", "🎖️"]
            lines = []
            current_rank = 0
            prev_titles = None

            for c in champions:
                titles = c.get("titles_count") or 1
                if titles != prev_titles:
                    current_rank += 1
                    prev_titles = titles

                medal_idx = current_rank - 1
                medal = medals[medal_idx] if medal_idx < len(medals) else "🏆"
                member = interaction.guild.get_member(c["user_id"])
                name = member.mention if member else (c.get("username") or f"ID: {c['user_id']}")
                plural = "título" if titles == 1 else "títulos"

                header = f"{medal} **{name}** — **{titles}** {plural}"

                tourneys = c.get("tournaments") or []
                if isinstance(tourneys, str):
                    try:
                        tourneys = json.loads(tourneys)
                    except Exception:
                        tourneys = []

                detail_lines = []
                if tourneys:
                    for t in tourneys:
                        if isinstance(t, dict):
                            t_name = t.get("name") or "Torneio"
                            t_game = t.get("game_name") or ""
                            if t_game:
                                detail_lines.append(f"   └ 🏆 *{t_name}* • 🎮 `{t_game}`")
                            else:
                                detail_lines.append(f"   └ 🏆 *{t_name}*")
                elif c.get("games"):
                    games_list = [g for g in c["games"] if g]
                    if games_list:
                        games_str = ", ".join(f"`{g}`" for g in games_list)
                        detail_lines.append(f"   └ 🎮 {games_str}")

                if detail_lines:
                    lines.append(f"{header}\n" + "\n".join(detail_lines))
                else:
                    lines.append(header)

            embed.description = "\n\n".join(lines)
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
            embed.set_footer(text="BMIA Esports • Hall da Fama")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro ao exibir Hall da Fama: {e}")
            await interaction.followup.send("❌ Erro ao carregar o Hall da Fama.")

    @app_commands.command(name="sortear", description="Sorteia aleatoriamente as chaves ou rodadas da liga")
    @app_commands.describe(id="ID do torneio a ser sorteado")
    @app_commands.checks.has_permissions(manage_events=True)
    async def sortear_torneio(self, interaction: discord.Interaction, id: int):
        await interaction.response.defer()
        try:
            tourney = await self.db.get_tournament(id)
            if not tourney or tourney["guild_id"] != interaction.guild.id:
                await interaction.followup.send("❌ Torneio não encontrado.")
                return

            res = await self.db.shuffle_tournament_participants(id)
            if not res.get("success"):
                await interaction.followup.send(f"⚠️ {res.get('reason', 'Não foi possível realizar o sorteio.')}")
                return

            participants = res["participants"]
            fmt = str(tourney.get("format", "1v1")).lower()
            is_2v2 = any(k in fmt for k in ["2v2", "2x2", "dupla", "duplas"])
            t_type = tourney.get("tournament_type") or "bracket"

            if t_type == "round_robin":
                matches = await self.db.get_tournament_matches(id)
                rounds_map = {}
                for m in matches:
                    r_num = m.get("round_number", 1)
                    rounds_map.setdefault(r_num, []).append(m)

                embed = discord.Embed(
                    title=f"🎲 Rodadas Geradas: {tourney['name']}",
                    description=f"⚡ Formato **Pontos Corridos (Liga)**\nForam geradas **{len(rounds_map)} rodadas** com um total de **{len(matches)} confrontos**.",
                    color=discord.Color.green()
                )

                r1_matches = rounds_map.get(1, [])
                if r1_matches:
                    lines = []
                    for m in r1_matches:
                        ta_names = [interaction.guild.get_member(uid).display_name if interaction.guild.get_member(uid) else f"<@{uid}>" for uid in (m.get("team_a_ids") or [])]
                        tb_names = [interaction.guild.get_member(uid).display_name if interaction.guild.get_member(uid) else f"<@{uid}>" for uid in (m.get("team_b_ids") or [])]
                        lines.append(f"⚔️ **Jogo #{m['match_number']}:** {' & '.join(ta_names)} **vs** {' & '.join(tb_names)}")
                    embed.add_field(name="📅 Confrontos da Rodada 1", value="\n".join(lines), inline=False)

                embed.set_footer(text=f"Use /torneio tabela id:{id} para ver a classificação ou /torneio rodadas para a lista completa.")
                await interaction.followup.send(embed=embed)
            else:
                embed = discord.Embed(
                    title=f"🎲 Sorteio Realizado: {tourney['name']}",
                    description="O sorteio aleatório das chaves do torneio foi concluído com sucesso!",
                    color=discord.Color.green()
                )

                if is_2v2:
                    duos_lines = []
                    for i in range(0, len(participants), 2):
                        duo = participants[i:i + 2]
                        duo_names = []
                        for p in duo:
                            m = interaction.guild.get_member(p["user_id"])
                            duo_names.append(m.mention if m else (p.get("username") or f"<@{p['user_id']}>"))
                        duo_str = " & ".join(duo_names)
                        duos_lines.append(f"⚔️ **Dupla #{(i // 2) + 1}:** {duo_str}")
                    embed.add_field(name="👥 Duplas Sorteadas", value="\n".join(duos_lines) if duos_lines else "Nenhum participante", inline=False)
                else:
                    lines = []
                    for idx, p in enumerate(participants, 1):
                        m = interaction.guild.get_member(p["user_id"])
                        name = m.mention if m else (p.get("username") or f"<@{p['user_id']}>")
                        lines.append(f"`#{idx:02d}` {name}")
                    embed.add_field(name="📋 Ordem dos Seeds / Chaves", value="\n".join(lines), inline=False)

                embed.set_footer(text=f"Use /torneio chaveamento id:{id} para visualizar a imagem oficial do chaveamento")
                await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro ao sortear torneio {id}: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao realizar o sorteio do torneio.")

    @app_commands.command(name="chaveamento", description="Gera a imagem oficial do chaveamento/bracket do torneio (Mata-Mata)")
    @app_commands.describe(id="ID do torneio (opcional, padrão: torneio ativo ou mais recente)")
    async def chaveamento_torneio(self, interaction: discord.Interaction, id: Optional[int] = None):
        await interaction.response.defer()
        try:
            if id is None:
                active = await self.db.get_active_tournaments(interaction.guild.id)
                if active:
                    id = active[0]["id"]
                else:
                    recent = await self.db.get_recent_tournaments(interaction.guild.id, limit=1)
                    if recent:
                        id = recent[0]["id"]
                    else:
                        await interaction.followup.send("❌ Nenhum torneio encontrado neste servidor. Use `/torneio criar` para criar um.")
                        return

            tourney = await self.db.get_tournament(id)
            if not tourney or tourney["guild_id"] != interaction.guild.id:
                await interaction.followup.send("❌ Torneio não encontrado.")
                return

            if tourney.get("tournament_type") == "round_robin":
                await interaction.followup.send("ℹ️ Este é um torneio de Pontos Corridos (Liga). Utilize `/torneio tabela` para ver a classificação.")
                return

            participants = await self.db.get_tournament_participants(id)
            if not participants:
                await interaction.followup.send("⚠️ Este torneio ainda não possui participantes inscritos para gerar o chaveamento.")
                return

            matches = await self.db.get_tournament_matches(id)

            # Gera a imagem através do BracketBuilder
            builder = BracketBuilder()
            image_buffer = await builder.generate_bracket(
                guild=interaction.guild,
                tournament=tourney,
                participants=participants,
                matches=matches
            )

            file = discord.File(fp=image_buffer, filename=f"chaveamento_torneio_{id}.png")
            await interaction.followup.send(file=file)
        except Exception as e:
            logger.error(f"Erro ao gerar chaveamento do torneio {id}: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao gerar a imagem do chaveamento.")

    @app_commands.command(name="tabela", description="Gera a imagem oficial da tabela de classificação da liga (Pontos Corridos)")
    @app_commands.describe(id="ID do torneio (opcional, padrão: torneio ativo ou mais recente)")
    async def tabela_torneio(self, interaction: discord.Interaction, id: Optional[int] = None):
        await interaction.response.defer()
        try:
            if id is None:
                active = await self.db.get_active_tournaments(interaction.guild.id)
                if active:
                    id = active[0]["id"]
                else:
                    recent = await self.db.get_recent_tournaments(interaction.guild.id, limit=1)
                    if recent:
                        id = recent[0]["id"]
                    else:
                        await interaction.followup.send("❌ Nenhum torneio encontrado neste servidor. Use `/torneio criar` para criar um.")
                        return

            tourney = await self.db.get_tournament(id)
            if not tourney or tourney["guild_id"] != interaction.guild.id:
                await interaction.followup.send("❌ Torneio não encontrado.")
                return

            if tourney.get("tournament_type") == "bracket":
                await interaction.followup.send("ℹ️ Este é um torneio de Mata-Mata. Utilize `/torneio chaveamento` para visualizar a árvore de confrontos.")
                return

            standings = await self.db.get_tournament_standings(id)
            if not standings:
                await interaction.followup.send("⚠️ Este torneio ainda não possui participantes para gerar a tabela.")
                return

            matches = await self.db.get_tournament_matches(id)

            builder = LeagueTableBuilder()
            image_buffer = await builder.generate_table(
                guild=interaction.guild,
                tournament=tourney,
                standings=standings,
                matches=matches
            )

            file = discord.File(fp=image_buffer, filename=f"tabela_liga_{id}.png")
            await interaction.followup.send(file=file)
        except Exception as e:
            logger.error(f"Erro ao gerar tabela do torneio {id}: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao gerar a tabela de classificação.")

    @app_commands.command(name="rodadas", description="Exibe o calendário de jogos e resultados das rodadas da liga")
    @app_commands.describe(id="ID do torneio (opcional)", rodada="Número da rodada específica (opcional)")
    async def rodadas_torneio(self, interaction: discord.Interaction, id: Optional[int] = None, rodada: Optional[int] = None):
        await interaction.response.defer()
        try:
            if id is None:
                active = await self.db.get_active_tournaments(interaction.guild.id)
                if active:
                    id = active[0]["id"]
                else:
                    recent = await self.db.get_recent_tournaments(interaction.guild.id, limit=1)
                    if recent:
                        id = recent[0]["id"]
                    else:
                        await interaction.followup.send("❌ Nenhum torneio encontrado neste servidor.")
                        return

            tourney = await self.db.get_tournament(id)
            if not tourney or tourney["guild_id"] != interaction.guild.id:
                await interaction.followup.send("❌ Torneio não encontrado.")
                return

            matches = await self.db.get_tournament_matches(id)
            if not matches:
                await interaction.followup.send("⚠️ As rodadas deste torneio ainda não foram sorteadas. Use `/torneio sortear`.")
                return

            rounds_map = {}
            for m in matches:
                r_num = m.get("round_number", 1)
                rounds_map.setdefault(r_num, []).append(m)

            embed = discord.Embed(
                title=f"📅 Calendário de Rodadas: {tourney['name']}",
                color=discord.Color.blue()
            )

            selected_rounds = [rodada] if (rodada and rodada in rounds_map) else sorted(rounds_map.keys())

            for r_num in selected_rounds:
                r_matches = rounds_map[r_num]
                lines = []
                for m in r_matches:
                    ta_names = [interaction.guild.get_member(uid).display_name if interaction.guild.get_member(uid) else f"<@{uid}>" for uid in (m.get("team_a_ids") or [])]
                    tb_names = [interaction.guild.get_member(uid).display_name if interaction.guild.get_member(uid) else f"<@{uid}>" for uid in (m.get("team_b_ids") or [])]
                    ta_str = " & ".join(ta_names)
                    tb_str = " & ".join(tb_names)

                    if m.get("status") == "completed":
                        sa = m.get("score_a", 0)
                        sb = m.get("score_b", 0)
                        lines.append(f"`#{m['match_number']:02d}` **{ta_str}** `{sa} x {sb}` **{tb_str}** ✅")
                    else:
                        lines.append(f"`#{m['match_number']:02d}` **{ta_str}** *vs* **{tb_str}** ⏳")

                embed.add_field(
                    name=f"📍 Rodada {r_num}",
                    value="\n".join(lines) if lines else "Nenhum jogo nesta rodada",
                    inline=False
                )

            embed.set_footer(text=f"Torneio #{id} • Use /torneio partida para registrar os resultados")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro ao listar rodadas do torneio {id}: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao consultar as rodadas.")
