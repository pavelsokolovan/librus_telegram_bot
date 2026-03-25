"""Tests for the main librus_bot.py orchestration logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestProcessAccount:
    @pytest.mark.asyncio
    @patch("librus_bot.send_message", new_callable=AsyncMock)
    @patch("librus_bot.format_report_fallback", return_value="fallback report")
    @patch("librus_bot.generate_report_with_claude", return_value=None)
    @patch("librus_bot.fetch_all", return_value={"account_name": "Kid", "date": "2026-03-25"})
    @patch("librus_bot.resolve_chat_ids", return_value=["123"])
    async def test_sends_fallback_when_no_claude(self, mock_ids, mock_fetch, mock_claude, mock_fallback, mock_send):
        from librus_bot import process_account

        account = {"name": "Kid"}
        cfg = {"telegram": {"bot_token": "tok"}}
        await process_account(account, cfg)

        mock_fetch.assert_called_once_with(account)
        mock_claude.assert_called_once()
        mock_fallback.assert_called_once()
        mock_send.assert_awaited_once_with("tok", "123", "fallback report", "Kid")

    @pytest.mark.asyncio
    @patch("librus_bot.send_message", new_callable=AsyncMock)
    @patch("librus_bot.format_report_fallback")
    @patch("librus_bot.generate_report_with_claude", return_value="Claude report")
    @patch("librus_bot.fetch_all", return_value={"account_name": "Kid", "date": "2026-03-25"})
    @patch("librus_bot.resolve_chat_ids", return_value=["123"])
    async def test_sends_claude_report_when_available(self, mock_ids, mock_fetch, mock_claude, mock_fallback, mock_send):
        from librus_bot import process_account

        account = {"name": "Kid"}
        cfg = {"telegram": {"bot_token": "tok"}}
        await process_account(account, cfg)

        mock_fallback.assert_not_called()
        mock_send.assert_awaited_once_with("tok", "123", "Claude report", "Kid")

    @pytest.mark.asyncio
    @patch("librus_bot.send_message", new_callable=AsyncMock)
    @patch("librus_bot.resolve_chat_ids", return_value=[])
    async def test_skips_when_no_chat_ids(self, mock_ids, mock_send):
        from librus_bot import process_account

        await process_account({"name": "Kid"}, {"telegram": {"bot_token": "tok"}})
        mock_send.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("librus_bot.send_message", new_callable=AsyncMock)
    @patch("librus_bot.fetch_all", side_effect=Exception("Librus down"))
    @patch("librus_bot.resolve_chat_ids", return_value=["123"])
    async def test_sends_error_msg_on_fetch_failure(self, mock_ids, mock_fetch, mock_send):
        from librus_bot import process_account

        account = {"name": "Kid"}
        cfg = {"telegram": {"bot_token": "tok"}}
        await process_account(account, cfg)

        mock_send.assert_awaited_once()
        sent_text = mock_send.await_args[0][2]
        assert "Nie można pobrać danych" in sent_text

    @pytest.mark.asyncio
    @patch("librus_bot.send_message", new_callable=AsyncMock)
    @patch("librus_bot.fetch_all", side_effect=Exception("Librus down"))
    @patch("librus_bot.resolve_chat_ids", return_value=["123"])
    async def test_test_mode_does_not_send_error(self, mock_ids, mock_fetch, mock_send):
        from librus_bot import process_account

        await process_account({"name": "Kid"}, {"telegram": {"bot_token": "tok"}}, test_mode=True)
        mock_send.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("librus_bot.send_message", new_callable=AsyncMock)
    @patch("librus_bot.format_report_fallback", return_value="report")
    @patch("librus_bot.generate_report_with_claude", return_value=None)
    @patch("librus_bot.fetch_all", return_value={"account_name": "Kid", "date": "2026-03-25"})
    @patch("librus_bot.resolve_chat_ids", return_value=["111", "222"])
    async def test_sends_to_all_chat_ids(self, mock_ids, mock_fetch, mock_claude, mock_fallback, mock_send):
        from librus_bot import process_account

        await process_account({"name": "Kid"}, {"telegram": {"bot_token": "tok"}})

        assert mock_send.await_count == 2
        sent_chat_ids = [call.args[1] for call in mock_send.await_args_list]
        assert sent_chat_ids == ["111", "222"]

    @pytest.mark.asyncio
    @patch("librus_bot.send_message", new_callable=AsyncMock)
    @patch("librus_bot.format_report_fallback", return_value="report")
    @patch("librus_bot.generate_report_with_claude", return_value=None)
    @patch("librus_bot.fetch_all", return_value={"account_name": "Kid", "date": "2026-03-25"})
    @patch("librus_bot.resolve_chat_ids", return_value=["123"])
    async def test_test_mode_does_not_send(self, mock_ids, mock_fetch, mock_claude, mock_fallback, mock_send):
        from librus_bot import process_account

        await process_account({"name": "Kid"}, {"telegram": {"bot_token": "tok"}}, test_mode=True)
        mock_send.assert_not_awaited()
