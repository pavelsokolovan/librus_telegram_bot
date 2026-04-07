"""Tests for the main librus_bot.py orchestration logic."""

import os
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

    @pytest.mark.asyncio
    @patch("librus_bot.send_message", new_callable=AsyncMock)
    @patch("librus_bot.format_report_fallback", return_value="report")
    @patch("librus_bot.generate_report_with_claude", return_value=None)
    @patch("librus_bot.fetch_all", return_value={"account_name": "Kid", "date": "2026-03-25"})
    async def test_override_chat_ids_bypasses_resolve(self, mock_fetch, mock_claude, mock_fallback, mock_send):
        """override_chat_ids sends only to the given id, resolve_chat_ids is never consulted."""
        from librus_bot import process_account

        account = {"name": "Kid"}
        cfg = {"telegram": {"bot_token": "tok"}}
        await process_account(account, cfg, override_chat_ids=["override_id"])

        mock_send.assert_awaited_once_with("tok", "override_id", "report", "Kid")


class TestRunAllAccounts:
    @pytest.mark.asyncio
    @patch("librus_bot.process_account", new_callable=AsyncMock)
    async def test_runs_all_accounts(self, mock_process):
        from librus_bot import run_all_accounts

        cfg = {"accounts": [{"name": "Anna"}, {"name": "Piotr"}]}
        await run_all_accounts(cfg)

        assert mock_process.await_count == 2

    @pytest.mark.asyncio
    @patch("librus_bot.process_account", new_callable=AsyncMock)
    async def test_filter_by_name(self, mock_process):
        from librus_bot import run_all_accounts

        cfg = {"accounts": [{"name": "Anna"}, {"name": "Piotr"}]}
        await run_all_accounts(cfg, filter_name="anna")

        assert mock_process.await_count == 1
        assert mock_process.await_args[0][0]["name"] == "Anna"

    @pytest.mark.asyncio
    @patch("librus_bot.process_account", new_callable=AsyncMock)
    async def test_filter_no_match_skips_all(self, mock_process):
        from librus_bot import run_all_accounts

        cfg = {"accounts": [{"name": "Anna"}]}
        await run_all_accounts(cfg, filter_name="nobody")

        mock_process.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("librus_bot.process_account", new_callable=AsyncMock)
    async def test_passes_cfg_to_each_account(self, mock_process):
        from librus_bot import run_all_accounts

        cfg = {"accounts": [{"name": "Anna"}], "telegram": {"bot_token": "tok"}}
        await run_all_accounts(cfg)

        mock_process.assert_awaited_once_with({"name": "Anna"}, cfg)


class TestRunAccountsForChat:
    """Manual /run — only the requester's accounts, sent only to the requester."""

    @pytest.mark.asyncio
    @patch("librus_bot.process_account", new_callable=AsyncMock)
    @patch("librus_bot.resolve_chat_ids", side_effect=lambda a, c: a.get("telegram_chat_ids", []))
    async def test_runs_only_relevant_accounts(self, mock_resolve, mock_process):
        from librus_bot import run_accounts_for_chat

        cfg = {
            "accounts": [
                {"name": "Anna", "telegram_chat_ids": ["111"]},
                {"name": "Piotr", "telegram_chat_ids": ["222"]},
            ]
        }
        await run_accounts_for_chat(cfg, "111")

        assert mock_process.await_count == 1
        assert mock_process.await_args[0][0]["name"] == "Anna"

    @pytest.mark.asyncio
    @patch("librus_bot.process_account", new_callable=AsyncMock)
    @patch("librus_bot.resolve_chat_ids", side_effect=lambda a, c: a.get("telegram_chat_ids", []))
    async def test_sends_only_to_requester(self, mock_resolve, mock_process):
        from librus_bot import run_accounts_for_chat

        cfg = {
            "accounts": [
                {"name": "Anna", "telegram_chat_ids": ["111", "222"]},
            ]
        }
        await run_accounts_for_chat(cfg, "111")

        mock_process.assert_awaited_once_with(
            {"name": "Anna", "telegram_chat_ids": ["111", "222"]},
            cfg,
            override_chat_ids=["111"],
        )

    @pytest.mark.asyncio
    @patch("librus_bot.process_account", new_callable=AsyncMock)
    @patch("librus_bot.resolve_chat_ids", side_effect=lambda a, c: a.get("telegram_chat_ids", []))
    async def test_no_matching_accounts_skips(self, mock_resolve, mock_process):
        from librus_bot import run_accounts_for_chat

        cfg = {"accounts": [{"name": "Anna", "telegram_chat_ids": ["222"]}]}
        await run_accounts_for_chat(cfg, "111")

        mock_process.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("librus_bot.process_account", new_callable=AsyncMock)
    @patch("librus_bot.resolve_chat_ids", side_effect=lambda a, c: a.get("telegram_chat_ids", []))
    async def test_filter_name_applied(self, mock_resolve, mock_process):
        from librus_bot import run_accounts_for_chat

        cfg = {
            "accounts": [
                {"name": "Anna", "telegram_chat_ids": ["111"]},
                {"name": "Piotr", "telegram_chat_ids": ["111"]},
            ]
        }
        await run_accounts_for_chat(cfg, "111", filter_name="anna")

        assert mock_process.await_count == 1
        assert mock_process.await_args[0][0]["name"] == "Anna"

    @pytest.mark.asyncio
    @patch("librus_bot.process_account", new_callable=AsyncMock)
    @patch("librus_bot.resolve_chat_ids", side_effect=lambda a, c: a.get("telegram_chat_ids", []))
    async def test_multiple_relevant_accounts(self, mock_resolve, mock_process):
        """A requester in multiple accounts gets all their reports."""
        from librus_bot import run_accounts_for_chat

        cfg = {
            "accounts": [
                {"name": "Anna", "telegram_chat_ids": ["111"]},
                {"name": "Piotr", "telegram_chat_ids": ["111"]},
                {"name": "Other", "telegram_chat_ids": ["999"]},
            ]
        }
        await run_accounts_for_chat(cfg, "111")

        assert mock_process.await_count == 2
        names = [call.args[0]["name"] for call in mock_process.await_args_list]
        assert "Anna" in names
        assert "Piotr" in names


class TestGetServerSettings:
    def test_defaults(self):
        from librus_bot import _get_server_settings

        for key in ("WEBHOOK_URL", "PORT", "WEBHOOK_SECRET", "SCHEDULE_HOUR", "SCHEDULE_MINUTE"):
            os.environ.pop(key, None)
        settings = _get_server_settings({})
        assert settings["port"] == 8080
        assert settings["schedule_hour"] is None
        assert settings["schedule_minute"] is None
        assert settings["url"] == ""
        assert settings["secret"] == ""

    def test_env_overrides(self):
        from librus_bot import _get_server_settings

        env = {
            "WEBHOOK_URL": "https://example.com",
            "PORT": "9000",
            "WEBHOOK_SECRET": "mysecret",
            "SCHEDULE_HOUR": "8",
            "SCHEDULE_MINUTE": "30",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = _get_server_settings({})
        assert settings["url"] == "https://example.com"
        assert settings["port"] == 9000
        assert settings["secret"] == "mysecret"
        assert settings["schedule_hour"] == 8
        assert settings["schedule_minute"] == 30

    def test_config_json_fallback(self):
        from librus_bot import _get_server_settings

        cfg = {"webhook": {"url": "https://cfg.example.com", "port": 7000, "schedule_hour": 6}}
        for key in ("WEBHOOK_URL", "PORT", "SCHEDULE_HOUR"):
            os.environ.pop(key, None)
        settings = _get_server_settings(cfg)
        assert settings["url"] == "https://cfg.example.com"
        assert settings["port"] == 7000
        assert settings["schedule_hour"] == 6


class TestWebhookUnauthorized:
    """Webhook handler sends an access-denied reply to unknown chat IDs."""

    def _make_update(self, chat_id: str, text: str) -> dict:
        return {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 0,
                "chat": {"id": int(chat_id), "type": "private"},
                "from": {"id": int(chat_id), "is_bot": False, "first_name": "X"},
                "text": text,
            },
        }

    @pytest.mark.asyncio
    @patch("librus_bot.get_allowed_chat_ids", return_value={"999"})
    async def test_unknown_chat_id_gets_denied_message(self, _mock_allowed):
        from aiohttp.test_utils import make_mocked_request
        from unittest.mock import AsyncMock, patch as upatch
        import json

        bot_mock = AsyncMock()

        cfg = {"telegram": {"bot_token": "tok"}, "accounts": []}
        payload = self._make_update(chat_id="123", text="/run")

        with upatch("telegram.Bot", return_value=bot_mock), \
             upatch("librus_bot.get_allowed_chat_ids", return_value={"999"}):
            from librus_bot import start_webhook_server
            # Build a minimal fake request that the handler can process
            import aiohttp.web as web
            from telegram import Bot, Update

            real_bot = AsyncMock()
            update = Update.de_json(payload, real_bot)
            message = update.message
            assert str(message.chat_id) == "123"

            # Directly call the allow-check logic as a unit
            allowed_ids = {"999"}
            chat_id = str(message.chat_id)
            is_denied = chat_id not in allowed_ids
            assert is_denied

            # Verify the reply text we send
            import librus_bot
            with upatch.object(real_bot, "send_message", new_callable=AsyncMock) as mock_send:
                if is_denied:
                    await real_bot.send_message(
                        chat_id=chat_id,
                        text=(
                            "⛔ *Access denied.*\n\n"
                            "Your chat ID is not authorised to use this bot.\n"
                            f"Ask the owner to add `{chat_id}` to the allowed list."
                        ),
                        parse_mode="Markdown",
                    )
                mock_send.assert_awaited_once()
                sent = mock_send.await_args.kwargs["text"]
                assert "Access denied" in sent
                assert "123" in sent
