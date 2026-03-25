"""Tests for src.telegram_sender."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.telegram_sender import send_message


class TestSendMessage:
    @pytest.mark.asyncio
    @patch("telegram.Bot")
    async def test_sends_message_with_markdown(self, MockBot):
        bot_instance = AsyncMock()
        MockBot.return_value = bot_instance

        await send_message("tok", "123", "Hello *bold*", "Kid")

        bot_instance.send_message.assert_awaited_once_with(
            chat_id="123", text="Hello *bold*", parse_mode="Markdown"
        )

    @pytest.mark.asyncio
    @patch("telegram.Bot")
    async def test_splits_long_messages(self, MockBot):
        bot_instance = AsyncMock()
        MockBot.return_value = bot_instance

        long_text = "A" * 8500  # Should produce 3 chunks: 4000 + 4000 + 500
        await send_message("tok", "123", long_text, "Kid")

        assert bot_instance.send_message.await_count == 3

    @pytest.mark.asyncio
    @patch("telegram.Bot")
    async def test_falls_back_to_plain_text_on_markdown_error(self, MockBot):
        bot_instance = AsyncMock()
        # First call (Markdown) fails, second call (plain) succeeds
        bot_instance.send_message.side_effect = [
            Exception("Bad Markdown"),
            None,
        ]
        MockBot.return_value = bot_instance

        await send_message("tok", "123", "Text", "Kid")

        calls = bot_instance.send_message.await_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["parse_mode"] == "Markdown"
        assert "parse_mode" not in calls[1].kwargs
