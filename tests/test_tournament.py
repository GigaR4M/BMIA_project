# tests/test_tournament.py - Testes unitários do Sistema de Torneios

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from commands.tournament_commands import TournamentCommands, TournamentRegistrationView
from utils.ai_tools import AIToolkit


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.create_tournament = AsyncMock(return_value=1)
    db.update_tournament_message = AsyncMock()
    db.get_tournament = AsyncMock(return_value={
        "id": 1,
        "guild_id": 123456789,
        "name": "Copa Roblox BMIA",
        "game_name": "Roblox",
        "format": "1v1",
        "max_participants": 16,
        "prize": "1000 pontos",
        "status": "open",
        "winner_id": None
    })
    db.get_active_tournaments = AsyncMock(return_value=[
        {"id": 1, "name": "Copa Roblox BMIA", "game_name": "Roblox", "status": "open", "participant_count": 4, "max_participants": 16}
    ])
    db.get_recent_tournaments = AsyncMock(return_value=[
        {"id": 1, "name": "Copa Roblox BMIA", "game_name": "Roblox", "status": "completed", "winner_name": "Pedrinho", "participant_count": 8, "max_participants": 16, "prize": "1000 pts"}
    ])
    db.add_tournament_participant = AsyncMock(return_value={"success": True, "count": 1, "max": 16})
    db.remove_tournament_participant = AsyncMock(return_value={"success": True, "count": 0, "max": 16})
    db.get_tournament_participants = AsyncMock(return_value=[
        {"user_id": 999, "username": "Gideon", "status": "registered"}
    ])
    db.shuffle_tournament_participants = AsyncMock(return_value={
        "success": True,
        "participants": [
            {"user_id": 999, "username": "Gideon", "status": "registered", "seed_number": 1},
            {"user_id": 888, "username": "Pedrinho", "status": "registered", "seed_number": 2}
        ]
    })
    db.finish_tournament = AsyncMock(return_value=True)
    db.cancel_tournament = AsyncMock(return_value=True)
    db.get_tournament_matches = AsyncMock(return_value=[])
    db.get_tournament_hall_of_fame = AsyncMock(return_value=[
        {"user_id": 999, "username": "Pedrinho", "titles_count": 3},
        {"user_id": 888, "username": "Lucas", "titles_count": 1},
    ])
    db.upsert_user = AsyncMock()
    return db


@pytest.fixture
def mock_points_manager():
    pm = MagicMock()
    pm.add_points = AsyncMock(return_value=True)
    return pm


class TestTournamentCommands:
    @pytest.mark.asyncio
    async def test_criar_torneio(self, mock_db):
        cmd = TournamentCommands(db=mock_db)
        interaction = MagicMock()
        interaction.guild.id = 123456789
        interaction.user.id = 999
        interaction.user.display_name = "Admin"
        interaction.channel.id = 555
        interaction.response.defer = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.id = 777
        interaction.followup.send = AsyncMock(return_value=mock_msg)

        await cmd.criar_torneio.callback(
            cmd,
            interaction,
            nome="Copa Roblox",
            jogo="Roblox",
            vagas=16,
            formato="1v1",
            premio="500 pontos"
        )

        mock_db.create_tournament.assert_awaited_once_with(
            guild_id=123456789,
            name="Copa Roblox",
            game_name="Roblox",
            format="1v1",
            max_participants=16,
            prize="500 pontos",
            created_by=999,
            tournament_type="bracket"
        )
        mock_db.update_tournament_message.assert_awaited_once_with(1, 555, 777)

    @pytest.mark.asyncio
    async def test_sortear_torneio(self, mock_db):
        cmd = TournamentCommands(db=mock_db)
        interaction = MagicMock()
        interaction.guild.id = 123456789
        interaction.guild.get_member.return_value = None
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await cmd.sortear_torneio.callback(cmd, interaction, id=1)

        mock_db.shuffle_tournament_participants.assert_awaited_once_with(1)
        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.call_args[1]["embed"]
        assert "Sorteio Realizado" in embed.title

    @pytest.mark.asyncio
    async def test_encerrar_torneio(self, mock_db, mock_points_manager):
        cmd = TournamentCommands(db=mock_db, points_manager=mock_points_manager)
        interaction = MagicMock()
        interaction.guild.id = 123456789
        interaction.guild.get_channel.return_value = None
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        vencedor = MagicMock()
        vencedor.id = 999
        vencedor.name = "Pedrinho"
        vencedor.discriminator = "0001"
        vencedor.bot = False
        vencedor.mention = "<@999>"
        vencedor.avatar = None

        await cmd.encerrar_torneio.callback(
            cmd,
            interaction,
            id=1,
            vencedor=vencedor,
            pontos_vencedor=1000
        )

        mock_db.finish_tournament.assert_awaited_once_with(
            tournament_id=1,
            winner_id=999,
            second_place_id=None,
            third_place_id=None,
            winner_ids=[999],
            second_place_ids=[],
            third_place_ids=[],
            final_score=None
        )

    @pytest.mark.asyncio
    async def test_registrar_partida(self, mock_db):
        cmd = TournamentCommands(db=mock_db)
        interaction = MagicMock()
        interaction.guild.id = 123456789
        interaction.guild.get_member.return_value = None
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        mock_db.get_tournament_matches = AsyncMock(return_value=[
            {
                "tournament_id": 1,
                "round_name": "final",
                "match_number": 1,
                "team_a_ids": [999],
                "team_b_ids": [888],
                "score_a": 0,
                "score_b": 0,
                "status": "pending"
            }
        ])
        mock_db.record_match_result = AsyncMock(return_value={
            "success": True,
            "is_final": True,
            "next_match_number": None
        })

        vencedor = MagicMock()
        vencedor.id = 999
        vencedor.mention = "<@999>"

        await cmd.registrar_partida.callback(
            cmd,
            interaction,
            id=1,
            jogo=1,
            placar="3x1",
            vencedor=vencedor
        )

        mock_db.record_match_result.assert_awaited_once_with(
            tournament_id=1,
            match_number=1,
            score_a=3,
            score_b=1,
            winner_team_ids=[999]
        )
        interaction.followup.send.assert_awaited_once()


    @pytest.mark.asyncio
    async def test_chaveamento_torneio(self, mock_db):
        cmd = TournamentCommands(db=mock_db)
        interaction = MagicMock()
        interaction.guild.id = 123456789
        interaction.guild.icon = None
        interaction.guild.get_member.return_value = None
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await cmd.chaveamento_torneio.callback(cmd, interaction, id=1)

        mock_db.get_tournament.assert_awaited_once_with(1)
        mock_db.get_tournament_participants.assert_awaited_once_with(1)
        interaction.followup.send.assert_awaited_once()
        # Verifica se o arquivo gerado foi enviado
        call_kwargs = interaction.followup.send.call_args[1]
        assert "file" in call_kwargs
        assert "embed" in call_kwargs


class TestBracketBuilder:
    @pytest.mark.asyncio
    async def test_generate_bracket_image_2_teams(self):
        from utils.image_generator import BracketBuilder
        builder = BracketBuilder()
        guild = MagicMock()
        guild.icon = None
        guild.get_member.return_value = None

        tournament = {
            "id": 1,
            "name": "Torneio 2x2 Piores do Mundo Rocket League 2026",
            "game_name": "Rocket League",
            "format": "2v2",
            "max_participants": 4,
            "prize": "10.000 pontos",
            "status": "open",
            "winner_id": None
        }

        participants = [
            {"user_id": 101, "username": "Gideon"},
            {"user_id": 102, "username": "Henrique"},
            {"user_id": 103, "username": "Gato"},
        ]

        buf = await builder.generate_bracket(guild, tournament, participants)
        assert buf is not None
        assert buf.getvalue().startswith(b"\x89PNG")

    @pytest.mark.asyncio
    async def test_generate_bracket_image_4_teams(self):
        from utils.image_generator import BracketBuilder
        builder = BracketBuilder()
        guild = MagicMock()
        guild.icon = None
        guild.get_member.return_value = None

        tournament = {
            "id": 2,
            "name": "Copa BMIA 1v1",
            "game_name": "Valorant",
            "format": "1v1",
            "max_participants": 4,
            "prize": "5.000 pts",
            "status": "open",
            "winner_id": None
        }

        participants = [
            {"user_id": 101, "username": "Gideon"},
            {"user_id": 102, "username": "Henrique"},
            {"user_id": 103, "username": "Gato"},
            {"user_id": 104, "username": "Lucas"},
        ]

        buf = await builder.generate_bracket(guild, tournament, participants)
        assert buf is not None
        assert buf.getvalue().startswith(b"\x89PNG")

    @pytest.mark.asyncio
    async def test_generate_bracket_image_8_teams(self):
        from utils.image_generator import BracketBuilder
        builder = BracketBuilder()
        guild = MagicMock()
        guild.icon = None
        guild.get_member.return_value = None

        tournament = {
            "id": 3,
            "name": "Grande Torneio 1v1",
            "game_name": "League of Legends",
            "format": "1v1",
            "max_participants": 16,
            "prize": "5.000 pts",
            "status": "open",
            "winner_id": None
        }

        participants = [
            {"user_id": i, "username": f"Player{i}"} for i in range(1, 9)
        ]

        buf = await builder.generate_bracket(guild, tournament, participants)
        assert buf is not None
        assert buf.getvalue().startswith(b"\x89PNG")


    @pytest.mark.asyncio
    async def test_view_join(self, mock_db):
        view = TournamentRegistrationView(db=mock_db, tournament_id=1)
        interaction = MagicMock()
        interaction.user.id = 999
        interaction.user.name = "Gideon"
        interaction.user.discriminator = "0"
        interaction.user.bot = False
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.message = None

        await view.callback_join(interaction)

        mock_db.add_tournament_participant.assert_awaited_once_with(1, 999)
        interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_view_leave(self, mock_db):
        view = TournamentRegistrationView(db=mock_db, tournament_id=1)
        interaction = MagicMock()
        interaction.user.id = 999
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.message = None

        await view.callback_leave(interaction)

        mock_db.remove_tournament_participant.assert_awaited_once_with(1, 999)


class TestTournamentAITools:
    @pytest.mark.asyncio
    async def test_get_tournament_history(self, mock_db):
        toolkit = AIToolkit(db=mock_db, guild_id=123456789)
        res = await toolkit.get_tournament_history(limit=5)
        assert len(res) == 1
        assert res[0]["nome"] == "Copa Roblox BMIA"
        assert res[0]["campeao"] == "Pedrinho"

    @pytest.mark.asyncio
    async def test_get_tournament_hall_of_fame(self, mock_db):
        toolkit = AIToolkit(db=mock_db, guild_id=123456789)
        res = await toolkit.get_tournament_hall_of_fame(limit=5)
        assert len(res) == 2
        assert res[0]["posicao"] == 1
        assert res[0]["usuario"] == "Pedrinho"
        assert res[0]["titulos"] == 3


class TestRoundRobinSystem:
    @pytest.mark.asyncio
    async def test_init_round_robin_matches_berger_4_teams(self):
        """Testa o algoritmo Berger para 4 equipes (deve gerar 3 rodadas, 6 jogos)."""
        from database import Database
        db = Database("postgresql://fake")
        db.pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        db.pool.acquire.return_value.__aenter__.return_value = mock_conn

        participants = [{"user_id": 1}, {"user_id": 2}, {"user_id": 3}, {"user_id": 4}]
        matches = await db.init_round_robin_matches(1, "1v1", participants)
        assert mock_conn.execute.await_count == 7  # 1 DELETE + 6 INSERTs

    @pytest.mark.asyncio
    async def test_init_round_robin_matches_berger_3_teams_odd(self):
        """Testa o algoritmo Berger para 3 equipes (número ímpar com bye, deve gerar 3 rodadas e 3 jogos)."""
        from database import Database
        db = Database("postgresql://fake")
        db.pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        db.pool.acquire.return_value.__aenter__.return_value = mock_conn

        participants = [{"user_id": 1}, {"user_id": 2}, {"user_id": 3}]
        matches = await db.init_round_robin_matches(1, "1v1", participants)
        assert mock_conn.execute.await_count == 4  # 1 DELETE + 3 INSERTs

    @pytest.mark.asyncio
    async def test_get_tournament_standings_calculation(self):
        """Testa o cálculo da tabela de classificação, saldo de gols, pontuação e ordenação."""
        from database import Database
        db = Database("postgresql://fake")
        db.pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "format": "1v1"})
        mock_conn.fetch = AsyncMock()
        db.pool.acquire.return_value.__aenter__.return_value = mock_conn

        db.get_tournament_participants = AsyncMock(return_value=[
            {"user_id": 1, "username": "Alpha"},
            {"user_id": 2, "username": "Beta"},
            {"user_id": 3, "username": "Gamma"}
        ])

        db.get_tournament_matches = AsyncMock(return_value=[
            # Jogo 1: Alpha 3 x 1 Beta (Alpha vence)
            {"match_number": 1, "team_a_ids": [1], "team_b_ids": [2], "score_a": 3, "score_b": 1, "status": "completed", "is_draw": False},
            # Jogo 2: Gamma 2 x 2 Alpha (Empate)
            {"match_number": 2, "team_a_ids": [3], "team_b_ids": [1], "score_a": 2, "score_b": 2, "status": "completed", "is_draw": True},
            # Jogo 3: Beta 0 x 1 Gamma (Gamma vence)
            {"match_number": 3, "team_a_ids": [2], "team_b_ids": [3], "score_a": 0, "score_b": 1, "status": "completed", "is_draw": False},
        ])

        standings = await db.get_tournament_standings(1)
        assert len(standings) == 3

        # 1º lugar: Alpha ou Gamma (ambos com 4 pts, mas Alpha tem 5 GP e Gamma tem 3 GP)
        assert standings[0]["points"] == 4
        assert standings[0]["rank"] == 1
        assert standings[0]["played"] == 2

        # Beta deve estar em último com 0 pts e 2 derrotas
        beta_stat = next(s for s in standings if s["team_ids"] == [2])
        assert beta_stat["points"] == 0
        assert beta_stat["lost"] == 2
        assert beta_stat["goal_diff"] == -3

    @pytest.mark.asyncio
    async def test_league_table_builder(self):
        """Testa a geração de imagem da tabela de classificação da liga."""
        from utils.image_generator import LeagueTableBuilder
        builder = LeagueTableBuilder()

        guild = MagicMock()
        guild.icon = None
        guild.get_member.return_value = None

        tournament = {
            "id": 1,
            "name": "Liga dos Campeões BMIA",
            "game_name": "Rocket League",
            "format": "1v1",
            "prize": "1000 Pontos",
            "status": "open",
            "is_shuffled": True
        }

        standings = [
            {"rank": 1, "team_name": "Alpha", "points": 9, "played": 3, "won": 3, "drawn": 0, "lost": 0, "goals_for": 8, "goals_against": 2, "goal_diff": 6, "win_rate": 100.0, "members": [{"user_id": 1, "username": "Alpha"}]},
            {"rank": 2, "team_name": "Beta", "points": 4, "played": 3, "won": 1, "drawn": 1, "lost": 1, "goals_for": 4, "goals_against": 4, "goal_diff": 0, "win_rate": 44.4, "members": [{"user_id": 2, "username": "Beta"}]},
        ]

        buf = await builder.generate_table(guild, tournament, standings)
        assert buf is not None
        assert buf.getvalue().startswith(b"\x89PNG")

