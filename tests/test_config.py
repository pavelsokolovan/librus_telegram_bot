import json
import os
import pytest
from unittest.mock import patch, mock_open
from pathlib import Path


# ── load_config ────────────────────────────────────────────────────────────────

class TestLoadConfig:
    # Account entry now requires 'id'. Credentials can live fully in config.
    MINIMAL_CFG = {
        "accounts": [{"id": "1", "name": "Test", "username": "u", "password": "p", "telegram_chat_ids": ["123"]}],
        "telegram": {"bot_token": "tok123"},
    }

    # All env keys that load_config reads — cleared for every test to prevent
    # real .env values leaking into mocked runs.
    # Suffixes 1-3 are blanked so _discover_env_account_ids() finds nothing by default.
    _CLEAN_ENV = {
        "ACCOUNT_NAME1": "", "ACCOUNT_NAME2": "", "ACCOUNT_NAME3": "",
        "LIBRUS_USERNAME1": "", "LIBRUS_PASSWORD1": "",
        "LIBRUS_USERNAME2": "", "LIBRUS_PASSWORD2": "",
        "LIBRUS_USERNAME3": "", "LIBRUS_PASSWORD3": "",
        "TELEGRAM_CHAT_IDS1": "", "TELEGRAM_CHAT_IDS2": "", "TELEGRAM_CHAT_IDS3": "",
        "TELEGRAM_BOT_TOKEN": "",
        "CLAUDE_API_KEY": "",
    }

    def _patch_config(self, cfg_dict, env_vars=None):
        """Return a context-manager stack that fakes config.json + env vars."""
        import src.config as mod

        json_str = json.dumps(cfg_dict)
        # Start from a clean env (no real .env leakage), then apply test overrides.
        merged_env = {**self._CLEAN_ENV, **(env_vars or {})}
        patches = [
            patch.object(mod, "CONFIG_PATH", new=Path("fake/config.json")),
            patch("src.config._load_env"),
            patch("builtins.open", mock_open(read_data=json_str)),
            patch.object(Path, "exists", return_value=True),
            patch.dict(os.environ, merged_env, clear=False),
        ]
        return patches

    def _run(self, cfg_dict, env_vars=None):
        patches = self._patch_config(cfg_dict, env_vars)
        for p in patches:
            p.start()
        try:
            from src.config import load_config
            return load_config()
        finally:
            for p in patches:
                p.stop()

    def test_loads_minimal_config(self):
        result = self._run(self.MINIMAL_CFG)
        assert result["accounts"][0]["name"] == "Test"
        assert result["telegram"]["bot_token"] == "tok123"

    def test_env_overrides_username(self):
        result = self._run(self.MINIMAL_CFG, {"LIBRUS_USERNAME1": "env_user"})
        assert result["accounts"][0]["username"] == "env_user"

    def test_env_overrides_password(self):
        result = self._run(self.MINIMAL_CFG, {"LIBRUS_PASSWORD1": "env_pass"})
        assert result["accounts"][0]["password"] == "env_pass"

    def test_env_overrides_name(self):
        result = self._run(self.MINIMAL_CFG, {"ACCOUNT_NAME1": "Env Name"})
        assert result["accounts"][0]["name"] == "Env Name"

    def test_env_overrides_chat_ids(self):
        result = self._run(self.MINIMAL_CFG, {"TELEGRAM_CHAT_IDS1": "a, b, c"})
        assert result["accounts"][0]["telegram_chat_ids"] == ["a", "b", "c"]

    def test_env_overrides_bot_token(self):
        result = self._run(self.MINIMAL_CFG, {"TELEGRAM_BOT_TOKEN": "env_token"})
        assert result["telegram"]["bot_token"] == "env_token"

    def test_env_overrides_claude_api_key(self):
        result = self._run(self.MINIMAL_CFG, {"CLAUDE_API_KEY": "sk-ant-test"})
        assert result["claude"]["api_key"] == "sk-ant-test"

    def test_env_claude_api_key_overrides_config(self):
        cfg = {**self.MINIMAL_CFG, "claude": {"api_key": "from-config"}}
        result = self._run(cfg, {"CLAUDE_API_KEY": "from-env"})
        assert result["claude"]["api_key"] == "from-env"

    def test_exits_when_no_valid_accounts(self):
        """Empty config accounts + no env vars → no valid accounts → sys.exit."""
        with pytest.raises(SystemExit):
            self._run({"accounts": [], "telegram": {"bot_token": "t"}})

    # ── new behaviour: env-discovery ──────────────────────────────────────────

    def test_env_only_account_discovered(self):
        """Account defined purely via env vars; no config entry needed."""
        cfg = {"accounts": [], "telegram": {"bot_token": "tok"}}
        result = self._run(cfg, env_vars={
            "LIBRUS_USERNAME1": "u",
            "LIBRUS_PASSWORD1": "p",
            "TELEGRAM_CHAT_IDS1": "123",
        })
        assert len(result["accounts"]) == 1
        assert result["accounts"][0]["username"] == "u"
        assert result["accounts"][0]["id"] == "1"

    def test_config_and_env_merged(self):
        """Config entry provides per-account settings; env provides credentials."""
        cfg = {
            "accounts": [{"id": "1", "grades_new_days": 7}],
            "telegram": {"bot_token": "tok"},
        }
        result = self._run(cfg, env_vars={
            "LIBRUS_USERNAME1": "u",
            "LIBRUS_PASSWORD1": "p",
            "TELEGRAM_CHAT_IDS1": "123",
        })
        account = result["accounts"][0]
        assert account["username"] == "u"
        assert account["grades_new_days"] == 7

    def test_incomplete_env_account_skipped(self):
        """Account with missing password is skipped; app exits when no valid accounts."""
        cfg = {"accounts": [], "telegram": {"bot_token": "tok"}}
        with pytest.raises(SystemExit):
            self._run(cfg, env_vars={"LIBRUS_USERNAME1": "u"})  # no password

    def test_invalid_account_does_not_block_valid_ones(self):
        """One incomplete account is skipped; valid accounts still run."""
        cfg = {"accounts": [], "telegram": {"bot_token": "tok"}}
        result = self._run(cfg, env_vars={
            "LIBRUS_USERNAME1": "u1",
            "LIBRUS_PASSWORD1": "p1",
            "TELEGRAM_CHAT_IDS1": "111",
            "LIBRUS_USERNAME2": "u2",  # LIBRUS_PASSWORD2 stays blank → skipped
        })
        assert len(result["accounts"]) == 1
        assert result["accounts"][0]["username"] == "u1"

    def test_config_account_without_id_skipped(self):
        """Config entry missing 'id' is skipped; app exits when no valid accounts remain."""
        cfg = {
            "accounts": [{"name": "X", "username": "u", "password": "p", "telegram_chat_ids": ["1"]}],
            "telegram": {"bot_token": "tok"},
        }
        with pytest.raises(SystemExit):
            self._run(cfg)

    def test_multiple_env_accounts_discovered(self):
        """Multiple accounts discovered and sorted by ID."""
        cfg = {"accounts": [], "telegram": {"bot_token": "tok"}}
        result = self._run(cfg, env_vars={
            "LIBRUS_USERNAME1": "u1", "LIBRUS_PASSWORD1": "p1", "TELEGRAM_CHAT_IDS1": "111",
            "LIBRUS_USERNAME2": "u2", "LIBRUS_PASSWORD2": "p2", "TELEGRAM_CHAT_IDS2": "222",
        })
        assert len(result["accounts"]) == 2
        usernames = [a["username"] for a in result["accounts"]]
        assert "u1" in usernames
        assert "u2" in usernames

    def test_exits_when_no_bot_token(self):
        cfg = {"accounts": [{"name": "X", "username": "u", "password": "p", "telegram_chat_ids": ["1"]}], "telegram": {}}
        with pytest.raises(SystemExit):
            self._run(cfg)

    def test_exits_when_config_missing(self):
        import src.config as mod
        with patch.object(mod, "CONFIG_PATH", new=Path("nonexistent")), \
             patch("src.config._load_env"), \
             patch.object(Path, "exists", return_value=False):
            with pytest.raises(SystemExit):
                mod.load_config()

    def test_log_level_applied(self):
        import logging
        cfg = {**self.MINIMAL_CFG, "log_level": "WARNING"}
        self._run(cfg)
        assert logging.getLogger().level == logging.WARNING
        # Reset
        logging.getLogger().setLevel(logging.DEBUG)


# ── resolve_chat_ids ───────────────────────────────────────────────────────────

class TestResolveChatIds:
    def test_account_level_chat_ids(self):
        from src.config import resolve_chat_ids
        result = resolve_chat_ids(
            {"telegram_chat_ids": [111, 222]},
            {"telegram": {"chat_ids": [999]}},
        )
        assert result == ["111", "222"]

    def test_falls_back_to_global_chat_ids(self):
        from src.config import resolve_chat_ids
        result = resolve_chat_ids({}, {"telegram": {"chat_ids": [999]}})
        assert result == ["999"]

    def test_falls_back_to_single_chat_id(self):
        from src.config import resolve_chat_ids
        result = resolve_chat_ids(
            {"telegram_chat_id": 42},
            {"telegram": {}},
        )
        assert result == ["42"]

    def test_global_single_chat_id(self):
        from src.config import resolve_chat_ids
        result = resolve_chat_ids({}, {"telegram": {"chat_id": 7}})
        assert result == ["7"]

    def test_empty_when_nothing_configured(self):
        from src.config import resolve_chat_ids
        result = resolve_chat_ids({}, {"telegram": {}})
        assert result == []


# ── get_allowed_chat_ids ───────────────────────────────────────────────────────

class TestGetAllowedChatIds:
    def test_collects_all_account_chat_ids(self):
        from src.config import get_allowed_chat_ids
        cfg = {
            "accounts": [
                {"telegram_chat_ids": ["111", "222"]},
                {"telegram_chat_ids": ["333"]},
            ],
            "telegram": {},
        }
        assert get_allowed_chat_ids(cfg) == {"111", "222", "333"}

    def test_includes_global_chat_ids(self):
        from src.config import get_allowed_chat_ids
        cfg = {
            "accounts": [{"telegram_chat_ids": ["10"]}],
            "telegram": {"chat_ids": ["20", "30"]},
        }
        assert get_allowed_chat_ids(cfg) == {"10", "20", "30"}

    def test_includes_single_account_chat_id(self):
        from src.config import get_allowed_chat_ids
        cfg = {
            "accounts": [{"telegram_chat_id": 42}],
            "telegram": {},
        }
        assert get_allowed_chat_ids(cfg) == {"42"}

    def test_includes_single_global_chat_id(self):
        from src.config import get_allowed_chat_ids
        cfg = {"accounts": [], "telegram": {"chat_id": 99}}
        assert get_allowed_chat_ids(cfg) == {"99"}

    def test_empty_when_nothing_configured(self):
        from src.config import get_allowed_chat_ids
        cfg = {"accounts": [], "telegram": {}}
        assert get_allowed_chat_ids(cfg) == set()

    def test_deduplicates_ids(self):
        from src.config import get_allowed_chat_ids
        cfg = {
            "accounts": [{"telegram_chat_ids": ["5"]}],
            "telegram": {"chat_ids": ["5", "6"]},
        }
        assert get_allowed_chat_ids(cfg) == {"5", "6"}
