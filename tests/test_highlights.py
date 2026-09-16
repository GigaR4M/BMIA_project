# tests/test_highlights.py - Testes do Sistema de Destaques do Ano (BMIA Wrapped)

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from io import BytesIO


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.pool = MagicMock()
    db.get_guild_annual_highlights = AsyncMock(return_value={
        "highestScore": [{"user_id": 101, "username": "GigaR4M", "value": 15420}],
        "mostMessages": [{"user_id": 102, "username": "Shadow", "value": 8420}],
        "mostVoice": [{"user_id": 103, "username": "CyberValk", "value_seconds": 360000}],
        "nightOwl": [{"user_id": 104, "username": "NightOwl", "value_seconds": 180000}],
        "longestStreaming": [{"user_id": 105, "username": "StreamerPro", "value_seconds": 72000}],
        "topGamers": [{"user_id": 106, "username": "PlayerOne", "value_seconds": 540000}],
        "gameOfTheYear": [{"activity_name": "VALORANT", "value_seconds": 980000}],
        "mostReactionsReceived": [{"user_id": 101, "username": "GigaR4M", "value": 350}],
        "mostReactionsGiven": [{"user_id": 102, "username": "Shadow", "value": 520}],
        "mediaKing": [{"user_id": 107, "username": "MemeLord", "value": 412}],
        "omnipresent": [{"user_id": 101, "username": "GigaR4M", "value": 310}],
    })
    return db


class TestHighlightsScanner:
    def test_is_media_message_with_attachment(self):
        from utils.highlights_scanner import HighlightsScanner

        msg = MagicMock(spec=discord.Message)
        att = MagicMock()
        att.content_type = "image/png"
        att.filename = "print_top.png"
        msg.attachments = [att]
        msg.content = "olha esse print!"

        assert HighlightsScanner._is_media_message(msg) is True

    def test_is_media_message_with_link(self):
        from utils.highlights_scanner import HighlightsScanner

        msg = MagicMock(spec=discord.Message)
        msg.attachments = []
        msg.content = "vejam essa jogada https://medal.tv/games/valorant/clips/abc"

        assert HighlightsScanner._is_media_message(msg) is True

    def test_is_media_message_plain_text(self):
        from utils.highlights_scanner import HighlightsScanner

        msg = MagicMock(spec=discord.Message)
        msg.attachments = []
        msg.content = "bom dia pessoal, tudo bem?"

        assert HighlightsScanner._is_media_message(msg) is False


class TestHighlightsBuilder:
    @pytest.mark.asyncio
    async def test_generate_cover_slide(self):
        from utils.image_generator import HighlightsBuilder

        guild = MagicMock(spec=discord.Guild)
        guild.name = "Barões da Pinad"
        guild.icon = None

        buf = await HighlightsBuilder.generate_cover_slide(guild=guild, year=2026)
        assert isinstance(buf, BytesIO)
        assert len(buf.getvalue()) > 0

    @pytest.mark.asyncio
    async def test_generate_category_slide(self):
        from utils.image_generator import HighlightsBuilder

        guild = MagicMock(spec=discord.Guild)
        guild.name = "Barões da Pinad"
        guild.get_member.return_value = None

        winners = [
            {"user_id": 1, "username": "GigaR4M", "value": 15000},
            {"user_id": 2, "username": "Shadow", "value": 12000},
            {"user_id": 3, "username": "Valkyrie", "value": 9000},
            {"user_id": 4, "username": "Player4", "value": 6000},
            {"user_id": 5, "username": "Player5", "value": 4000},
        ]

        buf = await HighlightsBuilder.generate_category_slide(
            guild=guild,
            year=2026,
            category_title="MVP DO SERVIDOR",
            category_subtitle="Maior pontuação de XP acumulada",
            category_icon="⚡",
            theme_color="#ffd700",
            winners=winners,
            unit_label="XP",
            is_time=False
        )
        assert isinstance(buf, BytesIO)
        assert len(buf.getvalue()) > 0

    @pytest.mark.asyncio
    async def test_generate_media_slide(self):
        from utils.image_generator import HighlightsBuilder

        guild = MagicMock(spec=discord.Guild)
        guild.name = "Barões da Pinad"
        guild.get_member.return_value = None

        clip_data = {
            "username": "GigaR4M",
            "avatar_url": None,
            "reaction_count": 48,
            "reaction_summary": "🔥 32  😂 10  ❤️ 6",
            "channel_name": "🤳prints-e-clips",
            "created_at": "15/09/2026",
            "content": "Jogada inacreditável no clutch!",
            "media_url": None
        }

        buf = await HighlightsBuilder.generate_media_slide(
            guild=guild,
            year=2026,
            clip_data=clip_data
        )
        assert isinstance(buf, BytesIO)
        assert len(buf.getvalue()) > 0


class TestHighlightsCarousel:
    @pytest.mark.asyncio
    async def test_view_initialization(self, mock_db):
        from commands.stats_commands import HighlightsCarouselView, HIGHLIGHTS_CATEGORIES

        guild = MagicMock(spec=discord.Guild)
        guild.name = "Barões da Pinad"

        view = HighlightsCarouselView(
            guild=guild,
            year=2026,
            highlights_data={},
            top_clip=None
        )

        assert view.total_slides == len(HIGHLIGHTS_CATEGORIES)
        assert view.current_index == 0
        assert len(view.children) >= 5
