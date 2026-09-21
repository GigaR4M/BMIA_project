# tests/test_ai_tools.py - Testes unitários para AIToolkit e ChatHandler com Tools

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from utils.ai_tools import AIToolkit
from utils.chat_handler import ChatHandler


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_top_activities = AsyncMock(return_value=[
        {"activity_name": "Roblox", "total_seconds": 36000, "unique_users": 5, "session_count": 12},
        {"activity_name": "Valorant", "total_seconds": 18000, "unique_users": 3, "session_count": 8},
    ])
    db.get_game_top_users = AsyncMock(return_value=[
        {"username": "Pedrinho", "activity_name": "Roblox", "total_seconds": 72000, "session_count": 15},
        {"username": "Lucas", "activity_name": "Roblox", "total_seconds": 36000, "session_count": 10},
    ])
    db.get_top_users_by_voice = AsyncMock(return_value=[
        {"username": "Maria", "total_seconds": 18000},
        {"username": "Joao", "total_seconds": 7200},
    ])
    db.get_top_users_by_messages = AsyncMock(return_value=[
        {"username": "Carlos", "message_count": 450},
        {"username": "Ana", "message_count": 320},
    ])
    db.find_user_by_username = AsyncMock(return_value={"user_id": 999, "username": "Gideon", "is_bot": False})
    db.get_detailed_user_stats = AsyncMock(return_value={
        "total_messages": 120,
        "voice_minutes": 300,
        "game_minutes": 600,
        "total_points": 50,
    })
    return db


@pytest_asyncio.fixture
async def toolkit(mock_db):
    return AIToolkit(db=mock_db, guild_id=123456789)


class TestAIToolkit:
    @pytest.mark.asyncio
    async def test_get_top_games(self, toolkit, mock_db):
        res = await toolkit.get_top_games(days=30, limit=5)
        assert len(res) == 2
        assert res[0]["jogo"] == "Roblox"
        assert res[0]["horas_totais"] == 10.0
        assert res[0]["jogadores_unicos"] == 5

    @pytest.mark.asyncio
    async def test_get_game_leaderboard(self, toolkit, mock_db):
        res = await toolkit.get_game_leaderboard(game_name="Roblox", days=30, limit=5)
        assert len(res) == 2
        assert res[0]["posicao"] == 1
        assert res[0]["usuario"] == "Pedrinho"
        assert res[0]["horas_jogadas"] == 20.0
        mock_db.get_game_top_users.assert_awaited_once_with(123456789, game_name="Roblox", limit=5, days=30)

    @pytest.mark.asyncio
    async def test_get_voice_leaderboard(self, toolkit, mock_db):
        res = await toolkit.get_voice_leaderboard(days=7, limit=5)
        assert len(res) == 2
        assert res[0]["usuario"] == "Maria"
        assert res[0]["horas_em_voz"] == 5.0

    @pytest.mark.asyncio
    async def test_get_messages_leaderboard(self, toolkit, mock_db):
        res = await toolkit.get_messages_leaderboard(days=30, limit=5)
        assert len(res) == 2
        assert res[0]["usuario"] == "Carlos"
        assert res[0]["quantidade_mensagens"] == 450

    @pytest.mark.asyncio
    async def test_get_user_stats_summary(self, toolkit, mock_db):
        res = await toolkit.get_user_stats_summary(username="Gideon", days=30)
        assert res["usuario"] == "Gideon"
        assert res["total_mensagens"] == 120
        assert res["horas_em_voz"] == 5.0
        assert res["horas_em_jogos"] == 10.0

    def test_get_tool_callables(self, toolkit):
        callables = toolkit.get_tool_callables()
        assert len(callables) == 8
        names = [c.__name__ for c in callables]
        assert "get_top_games" in names
        assert "get_game_leaderboard" in names
        assert "get_voice_leaderboard" in names
        assert "get_tournament_history" in names
        assert "get_tournament_hall_of_fame" in names
        assert "buscar_gif" in names


class TestChatHandlerWithTools:
    @pytest.mark.asyncio
    async def test_generate_response_without_tools(self):
        handler = ChatHandler(api_key="test-key", model_name="gemini-2.0-flash")
        
        with patch("google.generativeai.GenerativeModel") as MockModel:
            mock_model_instance = MagicMock()
            mock_chat = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Olá! Tudo bem?"
            mock_response.candidates = []
            mock_chat.send_message_async = AsyncMock(return_value=mock_response)
            mock_model_instance.start_chat.return_value = mock_chat
            MockModel.return_value = mock_model_instance

            res = await handler.generate_response("Olá BMIA!")
            assert res == "Olá! Tudo bem?"

    @pytest.mark.asyncio
    async def test_generate_response_with_tool_call(self, toolkit):
        handler = ChatHandler(api_key="test-key", model_name="gemini-2.0-flash")

        with patch("google.generativeai.GenerativeModel") as MockModel:
            mock_model_instance = MagicMock()
            mock_chat = MagicMock()

            # 1º turno: Gemini pede para chamar get_game_leaderboard
            mock_part_fn = MagicMock()
            mock_part_fn.function_call.name = "get_game_leaderboard"
            mock_part_fn.function_call.args = {"game_name": "Roblox", "limit": 3}
            mock_candidate_1 = MagicMock()
            mock_candidate_1.content.parts = [mock_part_fn]
            mock_response_1 = MagicMock()
            mock_response_1.candidates = [mock_candidate_1]
            mock_response_1.text = None

            # 2º turno: Gemini recebe resultado e devolve texto final
            mock_part_text = MagicMock()
            mock_part_text.function_call = None
            mock_part_text.text = "O Pedrinho é o top 1 de Roblox com 20h!"
            mock_candidate_2 = MagicMock()
            mock_candidate_2.content.parts = [mock_part_text]
            mock_response_2 = MagicMock()
            mock_response_2.candidates = [mock_candidate_2]
            mock_response_2.text = "O Pedrinho é o top 1 de Roblox com 20h!"

            mock_chat.send_message_async = AsyncMock(side_effect=[mock_response_1, mock_response_2])
            mock_model_instance.start_chat.return_value = mock_chat
            MockModel.return_value = mock_model_instance

            res = await handler.generate_response(
                "Quem mais joga Roblox?",
                toolkit=toolkit
            )
            assert "Pedrinho é o top 1 de Roblox" in res

    def test_format_history_identifies_authors(self):
        handler = ChatHandler(api_key="test-key")
        bot_user = MagicMock()
        bot_user.id = 1
        
        user_1 = MagicMock()
        user_1.display_name = "Carlos"
        user_2 = MagicMock()
        user_2.display_name = "Maria"

        msg1 = MagicMock()
        msg1.author = user_1
        msg1.content = "E aí galera"

        msg2 = MagicMock()
        msg2.author = user_2
        msg2.content = "Alguém joga Roblox?"

        msg3 = MagicMock()
        msg3.author = bot_user
        msg3.content = "Eu posso ver quem joga mais!"

        history = handler.format_history([msg1, msg2, msg3], bot_user)
        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[0]["parts"][0] == "Carlos: E aí galera"
        assert history[1]["role"] == "user"
        assert history[1]["parts"][0] == "Maria: Alguém joga Roblox?"
        assert history[2]["role"] == "model"
        assert history[2]["parts"][0] == "Eu posso ver quem joga mais!"
