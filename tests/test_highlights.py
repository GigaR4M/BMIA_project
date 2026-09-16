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
        "mostOffensive": [{"user_id": 108, "username": "BocaSujaPro", "value": 45}],
        "mostReactionsReceived": [{"user_id": 101, "username": "GigaR4M", "value": 350}],
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


class TestHighlightsGallery:
    @pytest.mark.asyncio
    async def test_generate_all_slides_files(self):
        from utils.image_generator import HighlightsBuilder
        from commands.stats_commands import HIGHLIGHTS_CATEGORIES

        guild = MagicMock(spec=discord.Guild)
        guild.name = "Barões da Pinad"
        guild.get_member.return_value = None

        with patch.object(HighlightsBuilder, "generate_cover_slide", new=AsyncMock(return_value=BytesIO(b"fake_cover"))), \
             patch.object(HighlightsBuilder, "generate_category_slide", new=AsyncMock(return_value=BytesIO(b"fake_cat"))), \
             patch.object(HighlightsBuilder, "generate_media_slide", new=AsyncMock(return_value=BytesIO(b"fake_media"))):

            files = await HighlightsBuilder.generate_all_slides_files(
                guild=guild,
                year=2026,
                highlights_data={},
                top_clip=None,
                categories=HIGHLIGHTS_CATEGORIES
            )

            assert len(files) == len(HIGHLIGHTS_CATEGORIES)
            assert all(isinstance(f, discord.File) for f in files)

    @pytest.mark.asyncio
    async def test_handle_highlights_carousel_sends_batches(self, mock_db):
        from commands.stats_commands import handle_highlights_carousel

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = MagicMock()
        interaction.guild.id = 12345
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()

        fake_files = [MagicMock(spec=discord.File) for _ in range(13)]

        with patch("utils.image_generator.HighlightsBuilder.generate_all_slides_files", new=AsyncMock(return_value=fake_files)), \
             patch("utils.highlights_scanner.HighlightsScanner.find_top_clips_and_prints", new=AsyncMock(return_value=[])):

            await handle_highlights_carousel(mock_db, interaction, 2026)

            interaction.response.defer.assert_awaited_once()
            assert interaction.followup.send.await_count == 2
            # First batch (7 slides)
            call1_kwargs = interaction.followup.send.await_args_list[0].kwargs
            assert len(call1_kwargs["files"]) == 7
            # Second batch (6 slides)
            call2_kwargs = interaction.followup.send.await_args_list[1].kwargs
            assert len(call2_kwargs["files"]) == 6
