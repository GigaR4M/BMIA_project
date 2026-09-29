# commands/tournament_commands.py - Comandos de Gerenciamento de Torneios

import discord
from discord import app_commands
from database import Database
from typing import Optional, Any, List, Dict
import logging
import json
from datetime import datetime, timedelta, timezone
from utils.image_generator import BracketBuilder, LeagueTableBuilder

logger = logging.getLogger(__name__)


BRT_TZ = timezone(timedelta(hours=-3))


def _parse_event_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Tenta converter uma string de data/hora no fuso de Brasília (UTC-3) em datetime timezone-aware UTC."""
    if not dt_str:
        return None
    dt_str = dt_str.strip()
    now_brt = datetime.now(BRT_TZ)
    now_utc = datetime.now(timezone.utc)

    # Formatos completos com data e hora
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M"):
        try:
            dt = datetime.strptime(dt_str, fmt)
            dt_brt = dt.replace(tzinfo=BRT_TZ)
            dt_utc = dt_brt.astimezone(timezone.utc)
            if dt_utc < now_utc:
                return None
            return dt_utc
        except ValueError:
            pass

    # Formato DD/MM HH:MM (ex: "28/09 20:00")
    for fmt_suffix in ("%d/%m %H:%M", "%d-%m %H:%M"):
        try:
            full_str = f"{now_brt.year} {dt_str}"
            dt = datetime.strptime(full_str, f"%Y {fmt_suffix}")
            dt_brt = dt.replace(tzinfo=BRT_TZ)
            if dt_brt < now_brt:
                dt_brt = dt_brt.replace(year=now_brt.year + 1)
            return dt_brt.astimezone(timezone.utc)
        except ValueError:
            pass

    # Formato apenas horário HH:MM (ex: "20:00")
    try:
        dt = datetime.strptime(dt_str, "%H:%M")
        combined_brt = now_brt.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
        if combined_brt <= now_brt:
            combined_brt += timedelta(days=1)
        return combined_brt.astimezone(timezone.utc)
    except ValueError:
        pass

    return None


async def _create_tournament_scheduled_event(
    guild: discord.Guild,
    tourney_id: int,
    name: str,
    game_name: str,
    start_time: Optional[datetime],
    end_time: Optional[datetime] = None,
    location: Optional[str] = None,
    channel: Optional[discord.VoiceChannel] = None,
    prize: Optional[str] = None,
    rules: Optional[str] = None
) -> Optional[int]:
    """Cria um Discord Scheduled Event oficial para o torneio apenas com dados válidos."""
    try:
        if not start_time:
            return None

        if not end_time:
            end_time = start_time + timedelta(hours=3)

        desc_parts = [f"🎮 Jogo: {game_name}"]
        if prize:
            desc_parts.append(f"🎁 Premiação: {prize}")
        if rules:
            desc_parts.append(f"📜 Regras: {rules}")
        desc_parts.append(f"\nTorneio Oficial BMIA #{tourney_id} • Inscrições abertas no canal do torneio!")

        loc = (location or "Servidor BMIA • Arena de Torneios")[:100]

        if channel:
            event = await guild.create_scheduled_event(
                name=f"🏆 {name[:95]}",
                description="\n".join(desc_parts)[:990],
                start_time=start_time,
                end_time=end_time,
                channel=channel,
                privacy_level=discord.PrivacyLevel.guild_only
            )
        else:
            event = await guild.create_scheduled_event(
                name=f"🏆 {name[:95]}",
                description="\n".join(desc_parts)[:990],
                start_time=start_time,
                end_time=end_time,
                entity_type=discord.EntityType.external,
                location=loc,
                privacy_level=discord.PrivacyLevel.guild_only
            )
        return event.id
    except Exception as e:
        logger.warning(f"Não foi possível criar Scheduled Event no Discord: {e}")
        return None


VAGAS_CHOICES = [
    app_commands.Choice(name="2 Participantes (Final 1v1)", value=2),
    app_commands.Choice(name="4 Participantes (Semis 1v1 / Final 2v2)", value=4),
    app_commands.Choice(name="6 Participantes (Final 3v3 - 2 Trios)", value=6),
    app_commands.Choice(name="8 Participantes (Quartas 1v1 / Semis 2v2)", value=8),
    app_commands.Choice(name="12 Participantes (Semis 3v3 - 4 Trios)", value=12),
    app_commands.Choice(name="16 Participantes (Oitavas 1v1 / Quartas 2v2)", value=16),
    app_commands.Choice(name="24 Participantes (Quartas 3v3 - 8 Trios)", value=24),
    app_commands.Choice(name="32 Participantes (16 avos 1v1 / Oitavas 2v2)", value=32),
]

FORMATO_CHOICES = [
    app_commands.Choice(name="1v1 (Individual)", value="1v1"),
    app_commands.Choice(name="2v2 (Duplas)", value="2v2"),
    app_commands.Choice(name="3v3 (Trios)", value="3v3"),
    app_commands.Choice(name="5v5 (Equipes)", value="5v5"),
]

TIPO_CHOICES = [
    app_commands.Choice(name="Single Elimination (Mata-Mata Simples)", value="single_elimination"),
    app_commands.Choice(name="Double Elimination (Eliminação Dupla)", value="double_elimination"),
    app_commands.Choice(name="Round Robin (Pontos Corridos / Liga)", value="round_robin"),
    app_commands.Choice(name="Swiss System (Sistema Suíço)", value="swiss"),
    app_commands.Choice(name="Group Stages (Fase de Grupos + Playoffs)", value="group_stages"),
    app_commands.Choice(name="FFA & Race (Lobbies / Corrida)", value="ffa_race"),
]

BEST_OF_CHOICES = [
    app_commands.Choice(name="MD1 (Melhor de 1 partida)", value=1),
    app_commands.Choice(name="MD3 (Melhor de 3 partidas)", value=3),
    app_commands.Choice(name="MD5 (Melhor de 5 partidas)", value=5),
    app_commands.Choice(name="MD7 (Melhor de 7 partidas)", value=7),
]


class TournamentCreateModal(discord.ui.Modal):
    """Modal com formulário visual para criação e configuração de torneios."""

    nome = discord.ui.TextInput(
        label="Nome do Torneio",
        placeholder="ex: Copa BMIA Brawl Stars",
        max_length=60,
        required=True
    )
    jogo = discord.ui.TextInput(
        label="Jogo",
        placeholder="ex: Brawl Stars, Rocket League, Uno, Fall Guys",
        max_length=50,
        required=True
    )
    vagas = discord.ui.TextInput(
        label="Vagas / Participantes (2 a 32)",
        placeholder="ex: 6, 8, 12, 16, 24, 32",
        default="16",
        max_length=4,
        required=True
    )
    premio = discord.ui.TextInput(
        label="Premiação (Opcional)",
        placeholder="ex: 5.000 XP + Cargo Campeão, R$ 50...",
        max_length=100,
        required=False
    )
    regras = discord.ui.TextInput(
        label="Regras / Início (Opcional)",
        style=discord.TextStyle.paragraph,
        placeholder="Insira regras, tolerância de WO, data/hora de início ou observações...",
        max_length=400,
        required=False
    )

    def __init__(
        self,
        db: Database,
        points_manager: Any = None,
        preset_type: str = "single_elimination",
        preset_format: str = "1v1",
        preset_vagas: int = 16,
        preset_best_of: int = 1
    ):
        tipo_labels = {
            "single_elimination": "Mata-Mata",
            "double_elimination": "Elim. Dupla",
            "round_robin": "Liga",
            "swiss": "Suíço",
            "group_stages": "Grupos",
            "ffa_race": "FFA & Corrida"
        }
        lbl = tipo_labels.get(preset_type, "Torneio")
        super().__init__(title=f"Criar: {lbl} ({preset_format.upper()})"[:45])
        self.db = db
        self.points_manager = points_manager
        self.preset_type = preset_type
        self.preset_format = preset_format
        self.preset_vagas = preset_vagas
        self.preset_best_of = preset_best_of
        self.vagas.default = str(preset_vagas)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            try:
                vagas_val = int(self.vagas.value.strip())
            except ValueError:
                vagas_val = self.preset_vagas
            vagas_val = max(2, min(vagas_val, 32))

            tipo_val = self.preset_type or "single_elimination"
            formato_val = self.preset_format or "1v1"
            bo_val = max(1, min(self.preset_best_of or 1, 9))
            premio_val = self.premio.value.strip() if self.premio.value else None
            regras_val = self.regras.value.strip() if self.regras.value else None

            tourney_id = await self.db.create_tournament(
                guild_id=interaction.guild.id,
                name=self.nome.value.strip(),
                game_name=self.jogo.value.strip(),
                format=formato_val,
                max_participants=vagas_val,
                prize=premio_val,
                created_by=interaction.user.id,
                tournament_type=tipo_val,
                rules=regras_val,
                best_of=bo_val
            )

            tipo_labels = {
                "single_elimination": "🏆 Single Elimination (Mata-Mata Simples)",
                "double_elimination": "🔁 Double Elimination (Eliminação Dupla)",
                "round_robin": "⚡ Round Robin (Pontos Corridos / Liga)",
                "swiss": "🇨🇭 Swiss System (Sistema Suíço)",
                "group_stages": "🌐 Group Stages (Grupos + Playoffs)",
                "ffa_race": "🏁 FFA & Race (Lobbies / Corrida)"
            }
            tipo_label = tipo_labels.get(tipo_val, "🏆 Mata-Mata")

            embed = discord.Embed(
                title=f"🏆 NOVO TORNEIO: {self.nome.value.strip()}",
                description="Clique nos botões abaixo para participar do torneio!",
                color=discord.Color.gold()
            )
            embed.add_field(name="🎮 Jogo", value=f"**{self.jogo.value.strip()}**", inline=True)
            embed.add_field(name="⚔️ Formato", value=f"**{formato_val.upper()}**", inline=True)
            embed.add_field(name="📊 Bracket", value=f"**{tipo_label}**", inline=True)
            embed.add_field(name="👥 Vagas / Inscritos", value=f"**0 / {vagas_val}**", inline=True)
            if bo_val > 1:
                embed.add_field(name="🎯 Série", value=f"**Melhor de {bo_val} (MD{bo_val})**", inline=True)
            if premio_val:
                embed.add_field(name="🎁 Premiação", value=f"**{premio_val}**", inline=False)
            if regras_val:
                embed.add_field(name="📜 Regras", value=regras_val, inline=False)

            embed.set_footer(text=f"Torneio ID: #{tourney_id} • Organizado por {interaction.user.display_name}")
            embed.timestamp = datetime.now()

            view = TournamentRegistrationView(self.db, tourney_id)
            message = await interaction.followup.send(embed=embed, view=view)
            await self.db.update_tournament_message(tourney_id, interaction.channel.id, message.id)

        except Exception as e:
            logger.error(f"Erro ao criar torneio via modal: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao criar o torneio.")


class TournamentBracketSelect(discord.ui.Select):
    """Menu Dropdown para selecionar o formato de bracket."""

    def __init__(self, current_val: str = "single_elimination"):
        options = [
            discord.SelectOption(label="Single Elimination (Mata-Mata Simples)", value="single_elimination", emoji="🏆", default=(current_val == "single_elimination")),
            discord.SelectOption(label="Double Elimination (Eliminação Dupla)", value="double_elimination", emoji="🔁", default=(current_val == "double_elimination")),
            discord.SelectOption(label="Round Robin (Pontos Corridos / Liga)", value="round_robin", emoji="⚡", default=(current_val == "round_robin")),
            discord.SelectOption(label="Swiss System (Sistema Suíço)", value="swiss", emoji="🇨🇭", default=(current_val == "swiss")),
            discord.SelectOption(label="Group Stages (Grupos + Playoffs)", value="group_stages", emoji="🌐", default=(current_val == "group_stages")),
            discord.SelectOption(label="FFA & Race (Lobbies / Corrida)", value="ffa_race", emoji="🏁", default=(current_val == "ffa_race")),
        ]
        super().__init__(
            placeholder="1. Selecione o Tipo de Bracket...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
            custom_id="tourney_setup_select_type"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_tipo = self.values[0]
        await self.view.update_selection(interaction)


class TournamentFormatSelect(discord.ui.Select):
    """Menu Dropdown para selecionar a formação da equipe."""

    def __init__(self, current_val: str = "1v1"):
        options = [
            discord.SelectOption(label="1v1 (Individual)", value="1v1", emoji="👤", default=(current_val == "1v1")),
            discord.SelectOption(label="2v2 (Duplas)", value="2v2", emoji="👥", default=(current_val == "2v2")),
            discord.SelectOption(label="3v3 (Trios)", value="3v3", emoji="🔺", default=(current_val == "3v3")),
            discord.SelectOption(label="5v5 (Equipes)", value="5v5", emoji="🛡️", default=(current_val == "5v5")),
        ]
        super().__init__(
            placeholder="2. Selecione a Formação (1v1, 2v2, 3v3, 5v5)...",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
            custom_id="tourney_setup_select_format"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_format = self.values[0]
        await self.view.update_selection(interaction)


class TournamentVagasSelect(discord.ui.Select):
    """Menu Dropdown para selecionar a quantidade de vagas."""

    def __init__(self, current_val: int = 16):
        options = [
            discord.SelectOption(label="2 Participantes (Final 1v1)", value="2", emoji="2️⃣", default=(current_val == 2)),
            discord.SelectOption(label="4 Participantes (Semis 1v1 / Final 2v2)", value="4", emoji="4️⃣", default=(current_val == 4)),
            discord.SelectOption(label="6 Participantes (Final 3v3 - 2 Trios)", value="6", emoji="6️⃣", default=(current_val == 6)),
            discord.SelectOption(label="8 Participantes (Quartas 1v1 / Semis 2v2)", value="8", emoji="8️⃣", default=(current_val == 8)),
            discord.SelectOption(label="12 Participantes (Semis 3v3 - 4 Trios)", value="12", emoji="🔢", default=(current_val == 12)),
            discord.SelectOption(label="16 Participantes (Oitavas 1v1 / Quartas 2v2)", value="16", emoji="🔢", default=(current_val == 16)),
            discord.SelectOption(label="24 Participantes (Quartas 3v3 - 8 Trios)", value="24", emoji="🔢", default=(current_val == 24)),
            discord.SelectOption(label="32 Participantes (16 avos 1v1 / Oitavas 2v2)", value="32", emoji="🔢", default=(current_val == 32)),
        ]
        super().__init__(
            placeholder="3. Selecione a Quantidade de Vagas...",
            min_values=1,
            max_values=1,
            options=options,
            row=2,
            custom_id="tourney_setup_select_vagas"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_vagas = int(self.values[0])
        await self.view.update_selection(interaction)


class TournamentBestOfSelect(discord.ui.Select):
    """Menu Dropdown para selecionar o formato da série (MD1, MD3, etc.)."""

    def __init__(self, current_val: int = 1):
        options = [
            discord.SelectOption(label="MD1 (Melhor de 1 partida)", value="1", emoji="1️⃣", default=(current_val == 1)),
            discord.SelectOption(label="MD3 (Melhor de 3 partidas)", value="3", emoji="3️⃣", default=(current_val == 3)),
            discord.SelectOption(label="MD5 (Melhor de 5 partidas)", value="5", emoji="5️⃣", default=(current_val == 5)),
            discord.SelectOption(label="MD7 (Melhor de 7 partidas)", value="7", emoji="7️⃣", default=(current_val == 7)),
        ]
        super().__init__(
            placeholder="4. Selecione a Série (MD1, MD3, MD5, MD7)...",
            min_values=1,
            max_values=1,
            options=options,
            row=3,
            custom_id="tourney_setup_select_bo"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_best_of = int(self.values[0])
        await self.view.update_selection(interaction)


class TournamentCreationSetupView(discord.ui.View):
    """View interativa com menus suspensos de configuração e botão para abrir o formulário."""

    def __init__(
        self,
        db: Database,
        points_manager: Any = None,
        selected_tipo: str = "single_elimination",
        selected_format: str = "1v1",
        selected_vagas: int = 16,
        selected_best_of: int = 1
    ):
        super().__init__(timeout=300)
        self.db = db
        self.points_manager = points_manager
        self.selected_tipo = selected_tipo
        self.selected_format = selected_format
        self.selected_vagas = selected_vagas
        self.selected_best_of = selected_best_of

        self.add_item(TournamentBracketSelect(self.selected_tipo))
        self.add_item(TournamentFormatSelect(self.selected_format))
        self.add_item(TournamentVagasSelect(self.selected_vagas))
        self.add_item(TournamentBestOfSelect(self.selected_best_of))

    @discord.ui.button(label="📝 Abrir Formulário", style=discord.ButtonStyle.primary, row=4, custom_id="tourney_setup_open_modal")
    async def open_modal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TournamentCreateModal(
            db=self.db,
            points_manager=self.points_manager,
            preset_type=self.selected_tipo,
            preset_format=self.selected_format,
            preset_vagas=self.selected_vagas,
            preset_best_of=self.selected_best_of
        )
        await interaction.response.send_modal(modal)

    async def update_selection(self, interaction: discord.Interaction):
        tipo_labels = {
            "single_elimination": "🏆 Single Elimination (Mata-Mata Simples)",
            "double_elimination": "🔁 Double Elimination (Eliminação Dupla)",
            "round_robin": "⚡ Round Robin (Pontos Corridos / Liga)",
            "swiss": "🇨🇭 Swiss System (Sistema Suíço)",
            "group_stages": "🌐 Group Stages (Grupos + Playoffs)",
            "ffa_race": "🏁 FFA & Race (Lobbies / Corrida)"
        }
        embed = discord.Embed(
            title="⚙️ Assistente de Criação de Torneio",
            description="Configure as opções abaixo nos menus suspensos e clique em **📝 Abrir Formulário** para concluir a criação:",
            color=discord.Color.gold()
        )
        embed.add_field(name="📊 Bracket", value=f"**{tipo_labels.get(self.selected_tipo, self.selected_tipo)}**", inline=True)
        embed.add_field(name="⚔️ Formação", value=f"**{self.selected_format.upper()}**", inline=True)
        embed.add_field(name="👥 Vagas", value=f"**{self.selected_vagas} Participantes**", inline=True)
        embed.add_field(name="🎯 Série", value=f"**MD{self.selected_best_of} (Melhor de {self.selected_best_of})**", inline=True)
        await interaction.response.edit_message(embed=embed, view=self)


class MatchScoreModal(discord.ui.Modal):
    """Modal interativo para submissão e registro de placar de partida (1v1, 2v2, Liga, Mata-Mata)."""

    def __init__(self, db: Database, tournament_id: int, match_number: int, team_a_label: str, team_b_label: str):
        super().__init__(title=f"Lançar Placar — Jogo #{match_number}"[:45])
        self.db = db
        self.tournament_id = tournament_id
        self.match_number = match_number
        self.team_a_label = team_a_label
        self.team_b_label = team_b_label

        self.score_a = discord.ui.TextInput(
            label=f"Placar: {team_a_label[:40]}",
            placeholder="Ex: 2",
            max_length=3,
            required=True
        )
        self.score_b = discord.ui.TextInput(
            label=f"Placar: {team_b_label[:40]}",
            placeholder="Ex: 1",
            max_length=3,
            required=True
        )
        self.add_item(self.score_a)
        self.add_item(self.score_b)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_events and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas organizadores ou administradores podem registrar placares.", ephemeral=True)
            return

        await interaction.response.defer()
        try:
            sa = int(self.score_a.value.strip())
            sb = int(self.score_b.value.strip())
        except ValueError:
            await interaction.followup.send("⚠️ Insira apenas números inteiros válidos nos campos de placar.", ephemeral=True)
            return

        res = await self.db.record_match_result(
            tournament_id=self.tournament_id,
            match_number=self.match_number,
            score_a=sa,
            score_b=sb
        )
        if not res.get("success"):
            await interaction.followup.send(f"❌ {res.get('reason', 'Erro ao registrar resultado.')}", ephemeral=True)
            return

        winner_info = f"\n🏆 **Vencedor:** {self.team_a_label}" if sa > sb else (f"\n🏆 **Vencedor:** {self.team_b_label}" if sb > sa else "\n🤝 **Resultado:** Empate")
        embed = discord.Embed(
            title=f"⚔️ Placar Registrado — Jogo #{self.match_number}",
            description=f"**{self.team_a_label}** (`{sa}`) x (`{sb}`) **{self.team_b_label}**{winner_info}\nO resultado foi gravado com sucesso!",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)


class RaceScoreModal(discord.ui.Modal):
    """Modal interativo para submissão e registro de classificação em Corridas / FFA."""

    def __init__(self, db: Database, tournament_id: int, match_number: int, match_name: str, participants: List[Dict[str, Any]]):
        super().__init__(title=f"Classificação: {match_name}"[:45])
        self.db = db
        self.tournament_id = tournament_id
        self.match_number = match_number
        self.participants = participants

        self.pos_1 = discord.ui.TextInput(
            label="🥇 1º Lugar (Piloto Vencedor)",
            placeholder="Nome, @username ou ID do piloto",
            max_length=60,
            required=True
        )
        self.pos_2 = discord.ui.TextInput(
            label="🥈 2º Lugar",
            placeholder="Nome, @username ou ID do piloto",
            max_length=60,
            required=True
        )
        self.pos_3 = discord.ui.TextInput(
            label="🥉 3º Lugar (Opcional)",
            placeholder="Nome, @username ou ID do piloto",
            max_length=60,
            required=False
        )
        self.pos_4 = discord.ui.TextInput(
            label="4º Lugar (Opcional)",
            placeholder="Nome, @username ou ID do piloto",
            max_length=60,
            required=False
        )
        self.add_item(self.pos_1)
        self.add_item(self.pos_2)
        self.add_item(self.pos_3)
        self.add_item(self.pos_4)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_events and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas organizadores ou administradores podem registrar resultados.", ephemeral=True)
            return

        await interaction.response.defer()
        try:
            import re
            valid_inputs = [
                (1, "1º", self.pos_1.value.strip()),
                (2, "2º", self.pos_2.value.strip()),
                (3, "3º", self.pos_3.value.strip() if self.pos_3.value else None),
                (4, "4º", self.pos_4.value.strip() if self.pos_4.value else None),
            ]
            valid_inputs = [item for item in valid_inputs if item[2]]

            points_dist = {1: 15, 2: 12, 3: 10, 4: 8, 5: 6, 6: 5, 7: 4, 8: 3}
            p_map = {p["user_id"]: p for p in self.participants}
            results_list = []

            for pos_num, pos_label, raw_val in valid_inputs:
                target_uid = None
                display_name = raw_val

                # 1. Extração direta de ID ou menção <@123456>
                id_match = re.search(r'<@!?(\d+)>', raw_val) or re.search(r'\b(\d{15,22})\b', raw_val)
                if id_match:
                    possible_id = int(id_match.group(1))
                    if possible_id in p_map:
                        target_uid = possible_id
                    elif interaction.guild and interaction.guild.get_member(possible_id):
                        target_uid = possible_id

                # 2. Busca exata e depois parcial por texto no mapa de participantes
                if not target_uid:
                    raw_clean = str(raw_val).lower().replace("@", "").strip()
                    # Busca exata por username, display_name ou apelido
                    for uid, p_data in p_map.items():
                        p_username = str(p_data.get("username") or "").lower()
                        m = interaction.guild.get_member(uid) if interaction.guild else None
                        m_display = str(m.display_name).lower() if (m and hasattr(m, "display_name") and not str(type(m.display_name)).endswith("MagicMock'>")) else ""
                        m_name = str(m.name).lower() if (m and hasattr(m, "name") and not str(type(m.name)).endswith("MagicMock'>")) else ""
                        if raw_clean in (p_username, m_display, m_name):
                            target_uid = uid
                            break

                    # Busca parcial (substring)
                    if not target_uid:
                        for uid, p_data in p_map.items():
                            p_username = str(p_data.get("username") or "").lower()
                            m = interaction.guild.get_member(uid) if interaction.guild else None
                            m_display = str(m.display_name).lower() if (m and hasattr(m, "display_name") and not str(type(m.display_name)).endswith("MagicMock'>")) else ""
                            m_name = str(m.name).lower() if (m and hasattr(m, "name") and not str(type(m.name)).endswith("MagicMock'>")) else ""
                            if (raw_clean and raw_clean in p_username) or (raw_clean and raw_clean in m_display) or (raw_clean and raw_clean in m_name):
                                target_uid = uid
                                break

                # 3. Busca no servidor se o membro não estava no mapa inicial
                if not target_uid and interaction.guild:
                    raw_clean = str(raw_val).lower().replace("@", "").strip()
                    for m in interaction.guild.members:
                        if hasattr(m, "bot") and m.bot:
                            continue
                        m_disp = str(m.display_name).lower() if hasattr(m, "display_name") else ""
                        m_user = str(m.name).lower() if hasattr(m, "name") else ""
                        if raw_clean in (m_disp, m_user):
                            target_uid = m.id
                            break

                if target_uid:
                    m = interaction.guild.get_member(target_uid) if interaction.guild else None
                    if m and hasattr(m, "mention") and not str(type(m.mention)).endswith("MagicMock'>"):
                        display_name = m.mention
                    else:
                        display_name = p_map.get(target_uid, {}).get("username", raw_val)

                pts = points_dist.get(pos_num, 5)
                results_list.append({
                    "position": pos_num,
                    "label": pos_label,
                    "name": display_name,
                    "user_id": target_uid,
                    "points": pts
                })

            res_dict = {
                "results": results_list,
                "recorded_by": interaction.user.id
            }

            tourney = await self.db.get_tournament(self.tournament_id)
            if not tourney or tourney["status"] in ("completed", "cancelled"):
                await interaction.followup.send("⚠️ Não é possível registrar resultados em um torneio encerrado ou cancelado.", ephemeral=True)
                return

            async with self.db.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE tournament_matches
                    SET status = 'completed', scores_json = $3
                    WHERE tournament_id = $1 AND match_number = $2
                """, self.tournament_id, self.match_number, json.dumps(res_dict))

            embed = discord.Embed(
                title=f"🏁 Resultado Registrado — Bateria / Corrida #{self.match_number}",
                description="Classificação oficial gravada com sucesso!\n",
                color=discord.Color.green()
            )
            medals = ["🥇", "🥈", "🥉", "4️⃣"]
            lines = []
            for r in results_list:
                m_icon = medals[r["position"] - 1] if r["position"] <= len(medals) else f"#{r['position']}"
                lines.append(f"{m_icon} **{r['position']}º Lugar:** {r['name']} *(+{r['points']} pts)*")
            embed.add_field(name="🏎️ Posições de Chegada", value="\n".join(lines), inline=False)
            embed.set_footer(text=f"Torneio #{self.tournament_id} • Registrado por {interaction.user.display_name}")

            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro ao registrar resultado de corrida: {e}")
            await interaction.followup.send("❌ Erro ao registrar resultado da corrida.")


class TournamentMatchSelect(discord.ui.Select):
    """Menu suspenso para escolher qual partida/bateria deseja lançar o resultado."""

    def __init__(self, db: Database, tournament: dict, matches: List[dict], participants: List[dict]):
        self.db = db
        self.tournament = tournament
        self.matches = matches
        self.participants = participants
        p_map = {p["user_id"]: p for p in participants}

        t_type = (tournament.get("tournament_type") or "bracket").lower()
        is_ffa = t_type in ("ffa_race", "ffa", "race")

        options = []
        for m in matches[:25]:
            m_num = m["match_number"]
            st = "✅" if m.get("status") == "completed" else "⏳"
            r_name = m.get("round_name") or f"Jogo #{m_num}"

            if is_ffa or m.get("bracket_group") in ("ffa_lobby", "ffa_heat"):
                desc = f"{len(m.get('team_a_ids') or [])} pilotos no grid"
                label = f"{st} Jogo #{m_num}: {r_name[:35]}"
            else:
                ta_ids = m.get("team_a_ids") or []
                tb_ids = m.get("team_b_ids") or []
                ta_n = p_map.get(ta_ids[0], {}).get("username", "Time A") if ta_ids else "A definir"
                tb_n = p_map.get(tb_ids[0], {}).get("username", "Time B") if tb_ids else "A definir"
                label = f"{st} #{m_num}: {ta_n[:12]} vs {tb_n[:12]}"
                desc = f"{r_name} ({st} {'Concluído' if m.get('status') == 'completed' else 'Pendente'})"

            options.append(discord.SelectOption(
                label=label[:100],
                value=str(m_num),
                description=desc[:100],
                emoji="🎮" if not is_ffa else "🏎️"
            ))

        super().__init__(
            placeholder="Selecione o Jogo / Corrida para abrir o formulário...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="tourney_select_match_to_score"
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_events and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas organizadores ou administradores podem registrar placares.", ephemeral=True)
            return

        m_num = int(self.values[0])
        target_match = next((m for m in self.matches if m["match_number"] == m_num), None)
        if not target_match:
            await interaction.response.send_message("❌ Partida não encontrada.", ephemeral=True)
            return

        t_type = (self.tournament.get("tournament_type") or "bracket").lower()
        if t_type in ("ffa_race", "ffa", "race") or target_match.get("bracket_group") in ("ffa_lobby", "ffa_heat"):
            modal = RaceScoreModal(
                db=self.db,
                tournament_id=self.tournament["id"],
                match_number=m_num,
                match_name=target_match.get("round_name") or f"Corrida #{m_num}",
                participants=self.participants
            )
            await interaction.response.send_modal(modal)
        else:
            p_map = {p["user_id"]: p.get("username", f"Jogador #{p['user_id']}") for p in self.participants}
            ta_ids = target_match.get("team_a_ids") or []
            tb_ids = target_match.get("team_b_ids") or []
            ta_str = "Time A"
            tb_str = "Time B"
            if ta_ids:
                m_a = interaction.guild.get_member(ta_ids[0])
                ta_str = m_a.display_name if m_a else p_map.get(ta_ids[0], f"Jogador #{ta_ids[0]}")
            if tb_ids:
                m_b = interaction.guild.get_member(tb_ids[0])
                tb_str = m_b.display_name if m_b else p_map.get(tb_ids[0], f"Jogador #{tb_ids[0]}")

            modal = MatchScoreModal(self.db, self.tournament["id"], m_num, ta_str, tb_str)
            await interaction.response.send_modal(modal)


class TournamentScoreSelectView(discord.ui.View):
    """View que renderiza o menu de seleção de partidas para lançar resultado."""

    def __init__(self, db: Database, tournament: dict, matches: List[dict], participants: List[dict]):
        super().__init__(timeout=180)
        self.add_item(TournamentMatchSelect(db, tournament, matches, participants))


class TournamentRoundsView(discord.ui.View):
    """View anexada ao calendário de rodadas com botão para lançar resultados."""

    def __init__(self, db: Database, tournament: dict, matches: List[dict], participants: List[dict]):
        super().__init__(timeout=300)
        self.db = db
        self.tournament = tournament
        self.matches = matches
        self.participants = participants

    @discord.ui.button(label="Lançar Resultado", style=discord.ButtonStyle.primary, emoji="📝", custom_id="tourney_rounds_score_btn")
    async def btn_score(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_events and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas organizadores ou administradores podem lançar resultados de partidas.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📝 Lançar Resultado: {self.tournament['name']}",
            description="Selecione o confronto/corrida para abrir o formulário:",
            color=discord.Color.gold()
        )
        view = TournamentScoreSelectView(self.db, self.tournament, self.matches, self.participants)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


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
        jogo="Jogo do torneio (ex: Rocket League, Brawl Stars, Fall Guys, Disney Speedstorm)",
        formato="Formação da equipe (1v1, 2v2, 3v3, 5v5)",
        vagas="Quantidade total de vagas/participantes (2 a 32)",
        tipo="Tipo de bracket (Mata-Mata, Eliminação Dupla, Liga, Suíço, Grupos, FFA)",
        best_of="Formato da série (MD1, MD3, MD5, MD7)",
        premio="Premiação do torneio (ex: 5.000 pontos + Cargo Campeão)",
        inicio="Data e hora de início (ex: Sábado às 20:00)",
        regras="Regras do campeonato ou formato de disputa"
    )
    @app_commands.choices(
        formato=FORMATO_CHOICES,
        vagas=VAGAS_CHOICES,
        tipo=TIPO_CHOICES,
        best_of=BEST_OF_CHOICES
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
        best_of: Optional[app_commands.Choice[int]] = None,
        premio: Optional[str] = None,
        inicio: Optional[str] = None,
        regras: Optional[str] = None
    ):
        await interaction.response.defer()
        try:
            vagas_val = vagas.value if isinstance(vagas, app_commands.Choice) else int(vagas)
            formato_val = formato.value if isinstance(formato, app_commands.Choice) else str(formato)
            tipo_val = tipo.value if isinstance(tipo, app_commands.Choice) else (str(tipo) if tipo else "single_elimination")
            bo_val = best_of.value if isinstance(best_of, app_commands.Choice) else (int(best_of) if best_of else 1)
            vagas_val = max(2, min(vagas_val, 32))
            bo_val = max(1, min(bo_val, 9))

            tourney_id = await self.db.create_tournament(
                guild_id=interaction.guild.id,
                name=nome,
                game_name=jogo,
                format=formato_val,
                max_participants=vagas_val,
                prize=premio,
                created_by=interaction.user.id,
                tournament_type=tipo_val,
                rules=regras,
                best_of=bo_val
            )

            tipo_labels = {
                "single_elimination": "🏆 Single Elimination (Mata-Mata Simples)",
                "double_elimination": "🔁 Double Elimination (Eliminação Dupla)",
                "round_robin": "⚡ Round Robin (Pontos Corridos / Liga)",
                "swiss": "🇨🇭 Swiss System (Sistema Suíço)",
                "group_stages": "🌐 Group Stages (Grupos + Playoffs)",
                "ffa_race": "🏁 FFA & Race (Lobbies / Corrida)"
            }
            tipo_label = tipo_labels.get(tipo_val, "🏆 Mata-Mata")

            # Cria Scheduled Event se data/hora de início válida for fornecida
            event_id = None
            if inicio:
                start_dt = _parse_event_datetime(inicio)
                if start_dt:
                    event_id = await _create_tournament_scheduled_event(
                        guild=interaction.guild,
                        tourney_id=tourney_id,
                        name=nome,
                        game_name=jogo,
                        start_time=start_dt,
                        prize=premio,
                        rules=regras
                    )
                    if event_id:
                        await self.db.update_tournament_event_id(tourney_id, event_id)

            embed = discord.Embed(
                title=f"🏆 NOVO TORNEIO: {nome}",
                description="Clique nos botões abaixo para participar do torneio!",
                color=discord.Color.gold()
            )
            embed.add_field(name="🎮 Jogo", value=f"**{jogo}**", inline=True)
            embed.add_field(name="⚔️ Formato", value=f"**{formato_val.upper()}**", inline=True)
            embed.add_field(name="📊 Bracket", value=f"**{tipo_label}**", inline=True)
            embed.add_field(name="👥 Vagas / Inscritos", value=f"**0 / {vagas_val}**", inline=True)

            if bo_val > 1:
                embed.add_field(name="🎯 Série", value=f"**Melhor de {bo_val} (MD{bo_val})**", inline=True)
            if premio:
                embed.add_field(name="🎁 Premiação", value=f"**{premio}**", inline=False)
            if regras:
                embed.add_field(name="📜 Regras", value=regras, inline=False)
            if inicio:
                embed.add_field(name="⏰ Início", value=f"**{inicio}**", inline=False)
            if event_id:
                embed.add_field(name="📅 Evento Criado", value="Um evento agendado oficial foi publicado no topo do servidor!", inline=False)

            embed.set_footer(text=f"Torneio ID: #{tourney_id} • Organizado por {interaction.user.display_name}")
            embed.timestamp = datetime.now()

            view = TournamentRegistrationView(self.db, tourney_id)
            message = await interaction.followup.send(embed=embed, view=view)

            # Atualiza message_id e channel_id no banco
            await self.db.update_tournament_message(tourney_id, interaction.channel.id, message.id)

        except Exception as e:
            logger.error(f"Erro ao criar torneio: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao criar o torneio. Verifique os parâmetros e tente novamente.")

    @app_commands.command(name="formulario", description="Abre o assistente com formulário (Modal) para criar um torneio")
    @app_commands.describe(
        tipo="Tipo de bracket desejado",
        formato="Formação da equipe (1v1, 2v2, 3v3, 5v5)",
        vagas="Quantidade total de vagas/participantes",
        best_of="Formato da série (MD1, MD3, MD5, MD7)"
    )
    @app_commands.choices(
        tipo=TIPO_CHOICES,
        formato=FORMATO_CHOICES,
        vagas=VAGAS_CHOICES,
        best_of=BEST_OF_CHOICES
    )
    @app_commands.checks.has_permissions(manage_events=True)
    async def formulario_torneio(
        self,
        interaction: discord.Interaction,
        tipo: Optional[app_commands.Choice[str]] = None,
        formato: Optional[app_commands.Choice[str]] = None,
        vagas: Optional[app_commands.Choice[int]] = None,
        best_of: Optional[app_commands.Choice[int]] = None
    ):
        tipo_val = tipo.value if isinstance(tipo, app_commands.Choice) else (str(tipo) if tipo else None)
        formato_val = formato.value if isinstance(formato, app_commands.Choice) else (str(formato) if formato else None)
        vagas_val = vagas.value if isinstance(vagas, app_commands.Choice) else (int(vagas) if vagas else None)
        bo_val = best_of.value if isinstance(best_of, app_commands.Choice) else (int(best_of) if best_of else None)

        if any(x is not None for x in [tipo_val, formato_val, vagas_val, bo_val]):
            modal = TournamentCreateModal(
                db=self.db,
                points_manager=self.points_manager,
                preset_type=tipo_val or "single_elimination",
                preset_format=formato_val or "1v1",
                preset_vagas=vagas_val or 16,
                preset_best_of=bo_val or 1
            )
            await interaction.response.send_modal(modal)
        else:
            tipo_labels = {
                "single_elimination": "🏆 Single Elimination (Mata-Mata Simples)",
                "double_elimination": "🔁 Double Elimination (Eliminação Dupla)",
                "round_robin": "⚡ Round Robin (Pontos Corridos / Liga)",
                "swiss": "🇨🇭 Swiss System (Sistema Suíço)",
                "group_stages": "🌐 Group Stages (Grupos + Playoffs)",
                "ffa_race": "🏁 FFA & Race (Lobbies / Corrida)"
            }
            embed = discord.Embed(
                title="⚙️ Assistente de Criação de Torneio",
                description="Configure as opções abaixo nos menus suspensos e clique em **📝 Abrir Formulário** para concluir a criação:",
                color=discord.Color.gold()
            )
            embed.add_field(name="📊 Bracket", value="**🏆 Single Elimination (Mata-Mata Simples)**", inline=True)
            embed.add_field(name="⚔️ Formação", value="**1V1 (Individual)**", inline=True)
            embed.add_field(name="👥 Vagas", value="**16 Participantes**", inline=True)
            embed.add_field(name="🎯 Série", value="**MD1 (Melhor de 1 partida)**", inline=True)
            view = TournamentCreationSetupView(self.db, self.points_manager)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="resultado", description="Abre o formulário (Modal) para lançar placar ou classificação da partida")
    @app_commands.describe(id="ID do torneio (opcional, padrão: torneio ativo)", jogo="Número da partida/bateria (opcional)")
    @app_commands.checks.has_permissions(manage_events=True)
    async def resultado_cmd(self, interaction: discord.Interaction, id: Optional[int] = None, jogo: Optional[int] = None):
        if id is None:
            active = await self.db.get_active_tournaments(interaction.guild.id)
            if active:
                id = active[0]["id"]
            else:
                recent = await self.db.get_recent_tournaments(interaction.guild.id, limit=1)
                if recent:
                    id = recent[0]["id"]
                else:
                    await interaction.response.send_message("❌ Nenhum torneio encontrado neste servidor.", ephemeral=True)
                    return

        tourney = await self.db.get_tournament(id)
        if not tourney or tourney["guild_id"] != interaction.guild.id:
            await interaction.response.send_message("❌ Torneio não encontrado.", ephemeral=True)
            return

        if tourney["status"] == "cancelled":
            await interaction.response.send_message("⚠️ Não é possível lançar resultados em um torneio cancelado.", ephemeral=True)
            return

        if tourney["status"] == "completed":
            await interaction.response.send_message("⚠️ Este torneio já foi concluído.", ephemeral=True)
            return

        matches = await self.db.get_tournament_matches(id)
        if not matches:
            await interaction.response.send_message("⚠️ As partidas ainda não foram geradas. Use `/torneio sortear` primeiro.", ephemeral=True)
            return

        participants = await self.db.get_tournament_participants(id)
        t_type = (tourney.get("tournament_type") or "bracket").lower()
        is_ffa = t_type in ("ffa_race", "ffa", "race")

        if jogo is not None:
            target = next((m for m in matches if m["match_number"] == jogo), None)
            if not target:
                await interaction.response.send_message(f"❌ Partida #{jogo} não encontrada.", ephemeral=True)
                return

            if is_ffa or target.get("bracket_group") in ("ffa_lobby", "ffa_heat"):
                modal = RaceScoreModal(
                    db=self.db,
                    tournament_id=id,
                    match_number=jogo,
                    match_name=target.get("round_name") or f"Corrida #{jogo}",
                    participants=participants
                )
                await interaction.response.send_modal(modal)
            else:
                p_map = {p["user_id"]: p.get("username", f"Jogador #{p['user_id']}") for p in participants}
                ta_ids = target.get("team_a_ids") or []
                tb_ids = target.get("team_b_ids") or []
                ta_str = "Time A"
                tb_str = "Time B"
                if ta_ids:
                    m_a = interaction.guild.get_member(ta_ids[0])
                    ta_str = m_a.display_name if m_a else p_map.get(ta_ids[0], f"Jogador #{ta_ids[0]}")
                if tb_ids:
                    m_b = interaction.guild.get_member(tb_ids[0])
                    tb_str = m_b.display_name if m_b else p_map.get(tb_ids[0], f"Jogador #{tb_ids[0]}")

                modal = MatchScoreModal(self.db, id, jogo, ta_str, tb_str)
                await interaction.response.send_modal(modal)
        else:
            embed = discord.Embed(
                title=f"📝 Lançar Resultado: {tourney['name']}",
                description="Selecione no menu abaixo qual **jogo ou corrida** você deseja registrar o resultado:",
                color=discord.Color.gold()
            )
            view = TournamentScoreSelectView(self.db, tourney, matches, participants)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="participante_adicionar", description="[ADM] Inscreve manualmente um membro no torneio")
    @app_commands.describe(id="ID do torneio", membro="Membro a ser inscrito", forcar="Ignorar limite de vagas")
    @app_commands.checks.has_permissions(manage_events=True)
    async def adm_add_participant(self, interaction: discord.Interaction, id: int, membro: discord.Member, forcar: bool = False):
        await interaction.response.defer()
        try:
            m_avatar = str(membro.display_avatar.url) if hasattr(membro, 'display_avatar') else None
            await self.db.upsert_user(membro.id, membro.name, membro.discriminator, membro.bot, avatar_url=m_avatar)
            res = await self.db.admin_add_participant(id, membro.id, force=forcar)
            if not res.get("success"):
                await interaction.followup.send(f"⚠️ {res.get('reason', 'Não foi possível adicionar o membro.')}")
                return
            await interaction.followup.send(f"✅ {membro.mention} foi adicionado manualmente ao Torneio #{id}! ({res['count']}/{res['max']} inscritos)")
        except Exception as e:
            logger.error(f"Erro ao adicionar participante no torneio {id}: {e}")
            await interaction.followup.send("❌ Erro ao adicionar participante.")

    @app_commands.command(name="participante_remover", description="[ADM] Remove manualmente um membro do torneio")
    @app_commands.describe(id="ID do torneio", membro="Membro a ser removido")
    @app_commands.checks.has_permissions(manage_events=True)
    async def adm_remove_participant(self, interaction: discord.Interaction, id: int, membro: discord.Member):
        await interaction.response.defer()
        try:
            res = await self.db.admin_remove_participant(id, membro.id)
            if not res.get("success"):
                await interaction.followup.send(f"⚠️ {res.get('reason', 'Não foi possível remover o membro.')}")
                return
            await interaction.followup.send(f"ℹ️ {membro.mention} foi removido do Torneio #{id}. ({res['count']}/{res['max']} vagas preenchidas)")
        except Exception as e:
            logger.error(f"Erro ao remover participante do torneio {id}: {e}")
            await interaction.followup.send("❌ Erro ao remover participante.")

    @app_commands.command(name="participante_substituir", description="[ADM] Substitui um jogador por outro mantendo as chaves")
    @app_commands.describe(id="ID do torneio", membro_antigo="Jogador saindo", novo_membro="Novo jogador entrando")
    @app_commands.checks.has_permissions(manage_events=True)
    async def adm_substitute_participant(self, interaction: discord.Interaction, id: int, membro_antigo: discord.Member, novo_membro: discord.Member):
        await interaction.response.defer()
        try:
            m_avatar = str(novo_membro.display_avatar.url) if hasattr(novo_membro, 'display_avatar') else None
            await self.db.upsert_user(novo_membro.id, novo_membro.name, novo_membro.discriminator, novo_membro.bot, avatar_url=m_avatar)
            res = await self.db.admin_substitute_participant(id, membro_antigo.id, novo_membro.id)
            if not res.get("success"):
                await interaction.followup.send(f"⚠️ {res.get('reason', 'Não foi possível realizar a substituição.')}")
                return
            await interaction.followup.send(f"🔄 Substituição concluída! {membro_antigo.mention} foi substituído por {novo_membro.mention} no Torneio #{id}.")
        except Exception as e:
            logger.error(f"Erro ao substituir participante no torneio {id}: {e}")
            await interaction.followup.send("❌ Erro ao substituir participante.")

    @app_commands.command(name="test_fill", description="[TESTE] Preenche vagas vazias com participantes fictícios (Dummies/Bots)")
    @app_commands.describe(id="ID do torneio", quantidade="Quantidade de dummies a inserir (opcional)")
    @app_commands.checks.has_permissions(manage_events=True)
    async def test_fill_cmd(self, interaction: discord.Interaction, id: int, quantidade: Optional[int] = None):
        await interaction.response.defer()
        try:
            res = await self.db.fill_dummy_participants(id, count=quantidade)
            if not res.get("success"):
                await interaction.followup.send(f"⚠️ {res.get('reason', 'Não foi possível preencher com bots de teste.')}")
                return
            names_preview = ", ".join(f"`{n}`" for n in res["added_names"][:8])
            if len(res["added_names"]) > 8:
                names_preview += f" ... e mais {len(res['added_names']) - 8}"
            await interaction.followup.send(f"🤖 **{res['added_count']} participantes de teste adicionados com sucesso!**\nTotal: **{res['total_count']} / {res['max_participants']}**\n{names_preview}")
        except Exception as e:
            logger.error(f"Erro ao test-fill no torneio {id}: {e}")
            await interaction.followup.send("❌ Erro ao preencher vagas de teste.")

    @app_commands.command(name="evento_vincular", description="Cria um Discord Scheduled Event oficial vinculado ao torneio")
    @app_commands.describe(
        id="ID do torneio",
        data_hora="Data e hora de início (ex: '28/09/2026 20:00', '28/09 20:00' ou '20:00')",
        local="Local do evento (opcional se não usar canal de voz)",
        canal_voz="Canal de voz onde o torneio acontecerá (opcional)"
    )
    @app_commands.checks.has_permissions(manage_events=True)
    async def evento_vincular_cmd(
        self,
        interaction: discord.Interaction,
        id: int,
        data_hora: str,
        local: Optional[str] = None,
        canal_voz: Optional[discord.VoiceChannel] = None
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            tourney = await self.db.get_tournament(id)
            if not tourney or tourney["guild_id"] != interaction.guild.id:
                await interaction.followup.send("❌ Torneio não encontrado.")
                return

            start_dt = _parse_event_datetime(data_hora)
            if not start_dt:
                await interaction.followup.send(
                    "⚠️ Formato de data/hora não reconhecido. Formatos suportados:\n"
                    "• `DD/MM/AAAA HH:MM` (ex: `28/09/2026 20:00`)\n"
                    "• `DD/MM HH:MM` (ex: `28/09 20:00`)\n"
                    "• `HH:MM` (ex: `20:00`)"
                )
                return

            event_id = await _create_tournament_scheduled_event(
                guild=interaction.guild,
                tourney_id=id,
                name=tourney["name"],
                game_name=tourney["game_name"],
                start_time=start_dt,
                location=local,
                channel=canal_voz,
                prize=tourney.get("prize"),
                rules=tourney.get("rules")
            )
            if not event_id:
                await interaction.followup.send("⚠️ Não foi possível criar o evento agendado no servidor. Verifique as permissões de gerenciar eventos.")
                return

            await self.db.update_tournament_event_id(id, event_id)
            await interaction.followup.send(f"📅 **Evento oficial agendado com sucesso!** Vinculado ao Torneio #{id} para `{data_hora}`.")
        except Exception as e:
            logger.error(f"Erro ao vincular evento ao torneio {id}: {e}")
            await interaction.followup.send("❌ Erro ao vincular evento.")


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

            if tourney["status"] == "cancelled":
                await interaction.followup.send("⚠️ Não é possível encerrar um torneio que foi cancelado.")
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

            # Gera a imagem oficial do bracket ou classificação para incorporar no embed final
            final_file = None
            try:
                tourney["status"] = "completed"
                tourney["winner_id"] = vencedor.id
                tourney["final_score"] = final_placar_display
                t_type = tourney.get("tournament_type") or "bracket"
                matches = await self.db.get_tournament_matches(id)
                if t_type == "round_robin":
                    standings = await self.db.get_tournament_standings(id)
                    if standings:
                        builder = LeagueTableBuilder()
                        img_buf = await builder.generate_table(
                            guild=interaction.guild,
                            tournament=tourney,
                            standings=standings,
                            matches=matches
                        )
                        final_file = discord.File(fp=img_buf, filename="classificacao_final.png")
                        podium_embed.set_image(url="attachment://classificacao_final.png")
                else:
                    builder = BracketBuilder()
                    img_buf = await builder.generate_bracket(
                        guild=interaction.guild,
                        tournament=tourney,
                        participants=participants,
                        matches=matches
                    )
                    final_file = discord.File(fp=img_buf, filename="chaveamento_final.png")
                    podium_embed.set_image(url="attachment://chaveamento_final.png")
            except Exception as img_err:
                logger.debug(f"Não foi possível gerar imagem de encerramento do torneio {id}: {img_err}")

            if final_file:
                await interaction.followup.send(embed=podium_embed, file=final_file)
            else:
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

            if tourney["status"] == "cancelled":
                await interaction.followup.send("⚠️ Não é possível registrar resultados em um torneio cancelado.")
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

            if tourney["status"] == "cancelled":
                await interaction.followup.send(f"⚠️ O Torneio #{id} ({tourney['name']}) já foi cancelado anteriormente.")
                return

            if tourney["status"] == "completed":
                await interaction.followup.send("⚠️ Não é possível cancelar um torneio que já foi concluído.")
                return

            res = await self.db.cancel_tournament(id)
            if isinstance(res, dict) and not res.get("success"):
                await interaction.followup.send(f"⚠️ {res.get('reason', 'Não foi possível cancelar o torneio.')}")
                return

            await interaction.followup.send(f"🚫 **Torneio #{id} ({tourney['name']}) foi cancelado com sucesso.**")

            # Cancela evento agendado no Discord se existir
            if tourney.get("event_id"):
                try:
                    event = interaction.guild.get_scheduled_event(tourney["event_id"])
                    if event:
                        await event.cancel()
                except Exception as ev_err:
                    logger.debug(f"Não foi possível cancelar evento agendado: {ev_err}")

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

            if tourney["status"] == "cancelled":
                await interaction.followup.send("⚠️ Não é possível realizar sorteio em um torneio que foi cancelado.")
                return

            if tourney["status"] == "completed":
                await interaction.followup.send("⚠️ Não é possível realizar sorteio em um torneio que já foi concluído.")
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

                p_map = {p["user_id"]: p for p in participants}
                def get_p_name(uid):
                    m = interaction.guild.get_member(uid)
                    if m:
                        return m.display_name
                    if uid in p_map:
                        return p_map[uid].get("username") or f"User_{uid}"
                    if uid < 0:
                        return f"Bot #{abs(uid)}"
                    return f"<@{uid}>"

                r1_matches = rounds_map.get(1, [])
                if r1_matches:
                    lines = []
                    for m in r1_matches:
                        ta_names = [get_p_name(uid) for uid in (m.get("team_a_ids") or [])]
                        tb_names = [get_p_name(uid) for uid in (m.get("team_b_ids") or [])]
                        lines.append(f"⚔️ **Jogo #{m['match_number']}:** {' & '.join(ta_names)} **vs** {' & '.join(tb_names)}")
                    embed.add_field(name="📅 Confrontos da Rodada 1", value="\n".join(lines), inline=False)

                embed.set_footer(text=f"Use /torneio tabela id:{id} para ver a classificação ou /torneio rodadas para a lista completa.")
                await interaction.followup.send(embed=embed)
            elif t_type in ("ffa_race", "ffa", "race"):
                embed = discord.Embed(
                    title=f"🎲 Sorteio do Grid: {tourney['name']}",
                    description="🏁 Formato **FFA & Corrida (Lobby / Grid)**\nTodos os pilotos foram ordenados e posicionados no grid!",
                    color=discord.Color.green()
                )
                lines = []
                for idx, p in enumerate(participants, 1):
                    m = interaction.guild.get_member(p["user_id"])
                    name = m.display_name if m else (p.get("username") or f"Bot #{abs(p['user_id'])}")
                    lines.append(f"`#{idx:02d}` **{name}**")
                embed.add_field(name="🏎️ Grid de Largada / Pilotos", value="\n".join(lines), inline=False)
                embed.set_footer(text=f"Torneio #{id} • Use /torneio rodadas id:{id} para visualizar as corridas.")
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
                            duo_names.append(m.display_name if m else (p.get("username") or f"Bot #{abs(p['user_id'])}"))
                        duo_str = " & ".join(duo_names)
                        duos_lines.append(f"⚔️ **Dupla #{(i // 2) + 1}:** {duo_str}")
                    embed.add_field(name="👥 Duplas Sorteadas", value="\n".join(duos_lines) if duos_lines else "Nenhum participante", inline=False)
                else:
                    lines = []
                    for idx, p in enumerate(participants, 1):
                        m = interaction.guild.get_member(p["user_id"])
                        name = m.display_name if m else (p.get("username") or f"Bot #{abs(p['user_id'])}")
                        lines.append(f"`#{idx:02d}` **{name}**")
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

            t_type = (tourney.get("tournament_type") or "bracket").lower()
            if t_type in ("ffa_race", "ffa", "race"):
                await interaction.followup.send("ℹ️ Este é um torneio de **Corrida / Todos Contra Todos (FFA)**. Utilize `/torneio rodadas` para ver as baterias ou `/torneio resultado` para registrar a classificação.")
                return

            if t_type in ("round_robin",):
                await interaction.followup.send("ℹ️ Este é um torneio de **Pontos Corridos (Liga)**. Utilize `/torneio tabela` para ver a classificação ou `/torneio rodadas` para os confrontos.")
                return

            if t_type in ("swiss",):
                await interaction.followup.send("ℹ️ Este é um torneio no **Sistema Suíço**. Utilize `/torneio rodadas` para acompanhar as rodadas e confrontos.")
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

            t_type = (tourney.get("tournament_type") or "bracket").lower()
            if t_type in ("bracket", "single_elimination", "double_elimination"):
                await interaction.followup.send("ℹ️ Este é um torneio de **Mata-Mata / Eliminatórias**. Utilize `/torneio chaveamento` para visualizar a árvore de confrontos.")
                return

            if t_type in ("ffa_race", "ffa", "race"):
                await interaction.followup.send("ℹ️ Este é um torneio de **Corrida / Todos Contra Todos (FFA)**. Utilize `/torneio rodadas` para acompanhar as baterias ou `/torneio resultado` para registrar a classificação.")
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

            participants = await self.db.get_tournament_participants(id)
            p_map = {p["user_id"]: p for p in participants}

            def get_p_name(uid):
                m = interaction.guild.get_member(uid)
                if m:
                    return m.display_name
                if uid in p_map:
                    return p_map[uid].get("username") or f"User_{uid}"
                if uid < 0:
                    return f"Bot #{abs(uid)}"
                return f"<@{uid}>"

            t_type = (tourney.get("tournament_type") or "bracket").lower()
            is_ffa = t_type in ("ffa_race", "ffa", "race")

            for r_num in selected_rounds:
                r_matches = rounds_map[r_num]
                lines = []
                for m in r_matches:
                    m_ffa = is_ffa or m.get("bracket_group") in ("ffa_lobby", "ffa_heat") or (not m.get("team_b_ids") and m.get("team_a_ids"))

                    if m_ffa:
                        ta_ids = m.get("team_a_ids") or []
                        r_name = m.get("round_name") or f"Bateria #{m['match_number']}"
                        if ta_ids:
                            pilots = [get_p_name(uid) for uid in ta_ids]
                            st_icon = "✅ Concluído" if m.get("status") == "completed" else "⏳ Em Espera"
                            lines.append(f"🏁 **Jogo #{m['match_number']:02d} ({r_name})** — {st_icon}\n   • **Pilotos:** {', '.join(pilots)}")
                        else:
                            lines.append(f"🏆 **Jogo #{m['match_number']:02d} ({r_name})** ⏳ *(Aguardando classificados)*")
                    else:
                        ta_names = [get_p_name(uid) for uid in (m.get("team_a_ids") or [])]
                        tb_names = [get_p_name(uid) for uid in (m.get("team_b_ids") or [])]
                        ta_str = " & ".join(ta_names) if ta_names else "A definir"
                        tb_str = " & ".join(tb_names) if tb_names else "A definir"

                        if m.get("status") == "completed":
                            sa = m.get("score_a", 0)
                            sb = m.get("score_b", 0)
                            lines.append(f"`#{m['match_number']:02d}` **{ta_str}** `{sa} x {sb}` **{tb_str}** ✅")
                        else:
                            lines.append(f"`#{m['match_number']:02d}` **{ta_str}** *vs* **{tb_str}** ⏳")

                r_header = f"🏁 Rodada / Bateria {r_num}" if is_ffa else f"📍 Rodada {r_num}"
                embed.add_field(
                    name=r_header,
                    value="\n".join(lines) if lines else "Nenhum jogo nesta rodada",
                    inline=False
                )

            embed.set_footer(text=f"Torneio #{id} • Clique no botão abaixo ou use /torneio resultado para registrar resultados")
            view = TournamentRoundsView(self.db, tourney, matches, participants)
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Erro ao listar rodadas do torneio {id}: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao consultar as rodadas.")
