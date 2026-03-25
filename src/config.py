import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
ENV_PATH = PROJECT_ROOT / ".env"


def _load_env():
    load_dotenv(ENV_PATH)


def load_config() -> dict:
    """Load config.json, inject .env overrides, validate, and apply log level."""
    _load_env()

    if not CONFIG_PATH.exists():
        log.error("config.json not found! See README.md for setup.")
        sys.exit(1)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)

    if not cfg.get("accounts"):
        log.error("No accounts defined in config.json")
        sys.exit(1)

    # Inject per-account credentials from environment variables
    for i, account in enumerate(cfg["accounts"], start=1):
        for field, env_key in [
            ("username", f"LIBRUS_USERNAME{i}"),
            ("password", f"LIBRUS_PASSWORD{i}"),
            ("name", f"ACCOUNT_NAME{i}"),
        ]:
            val = os.environ.get(env_key)
            if val:
                account[field] = val

        chat_ids_env = os.environ.get(f"TELEGRAM_CHAT_IDS{i}")
        if chat_ids_env:
            account["telegram_chat_ids"] = [cid.strip() for cid in chat_ids_env.split(",")]

    # Inject bot token
    bot_token_env = os.environ.get("TELEGRAM_BOT_TOKEN")
    if bot_token_env:
        cfg.setdefault("telegram", {})["bot_token"] = bot_token_env

    if not cfg.get("telegram", {}).get("bot_token"):
        log.error("Telegram bot_token missing — set TELEGRAM_BOT_TOKEN in .env or config.json")
        sys.exit(1)

    # Apply log level from config
    level_str = cfg.get("log_level", "DEBUG").upper()
    level = getattr(logging, level_str, logging.DEBUG)
    logging.getLogger().setLevel(level)
    log.debug(f"Log level set to {level_str}")

    return cfg


def resolve_chat_ids(account_cfg: dict, global_cfg: dict) -> list[str]:
    """Return the list of Telegram chat IDs for an account (account-level overrides global)."""
    chat_ids = account_cfg.get("telegram_chat_ids") or global_cfg.get("telegram", {}).get("chat_ids") or []
    if not chat_ids:
        single = account_cfg.get("telegram_chat_id") or global_cfg.get("telegram", {}).get("chat_id")
        if single:
            chat_ids = [single]
    return [str(cid) for cid in chat_ids]
