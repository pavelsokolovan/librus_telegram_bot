import json
import logging
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
ENV_PATH = PROJECT_ROOT / ".env"


def _load_env():
    load_dotenv(ENV_PATH)


def _discover_env_account_ids() -> list[str]:
    """Return sorted list of account IDs inferred from LIBRUS_USERNAME{id} env vars.

    Only considers vars with non-empty values so that test helpers that blank
    out env vars do not inadvertently create ghost accounts.
    """
    pattern = re.compile(r"^LIBRUS_USERNAME(.+)$")
    ids = []
    for key, val in os.environ.items():
        m = pattern.match(key)
        if m and val.strip():
            ids.append(m.group(1))
    return sorted(ids)


def _build_accounts(cfg: dict) -> list[dict]:
    """Merge config.json account entries (keyed by 'id') with env-discovered accounts.

    Account sources:
    - Env vars: any LIBRUS_USERNAME{id} with a non-empty value auto-discovers the ID.
    - config.json accounts array: entries must have an 'id' field.

    For each ID (union of both sources) env vars override config values for
    username, password, name, and telegram_chat_ids.

    Accounts still missing username or password after merging are logged as
    warnings and skipped. The app continues as long as at least one account is valid.
    """
    # Index config accounts by id
    config_accounts: dict[str, dict] = {}
    for account in cfg.get("accounts", []):
        acc_id = str(account.get("id", "")).strip()
        if not acc_id:
            log.warning("config.json account entry is missing the 'id' field — skipped")
            continue
        config_accounts[acc_id] = dict(account)

    # Discover IDs from env
    env_ids = set(_discover_env_account_ids())

    # Union of both sources, sorted for deterministic processing order
    all_ids = sorted(set(config_accounts.keys()) | env_ids)

    valid_accounts = []
    for acc_id in all_ids:
        account = dict(config_accounts.get(acc_id, {}))
        account["id"] = acc_id

        # Inject credentials from env — env takes priority over config values
        for field, env_key in [
            ("username", f"LIBRUS_USERNAME{acc_id}"),
            ("password", f"LIBRUS_PASSWORD{acc_id}"),
            ("name", f"ACCOUNT_NAME{acc_id}"),
        ]:
            val = os.environ.get(env_key, "").strip()
            if val:
                account[field] = val

        chat_ids_env = os.environ.get(f"TELEGRAM_CHAT_IDS{acc_id}", "").strip()
        if chat_ids_env:
            account["telegram_chat_ids"] = [cid.strip() for cid in chat_ids_env.split(",")]

        # Validate: username and password are mandatory per account
        missing = []
        if not account.get("username"):
            missing.append(f"LIBRUS_USERNAME{acc_id}")
        if not account.get("password"):
            missing.append(f"LIBRUS_PASSWORD{acc_id}")

        # telegram_chat_ids: account-level OR a global fallback is sufficient
        has_chat_ids = (
            bool(account.get("telegram_chat_ids"))
            or bool(cfg.get("telegram", {}).get("chat_ids"))
            or bool(cfg.get("telegram", {}).get("chat_id"))
        )
        if not has_chat_ids:
            missing.append(f"TELEGRAM_CHAT_IDS{acc_id}")

        if missing:
            log.warning(
                f"Account id='{acc_id}' skipped — missing: {', '.join(missing)}. "
                "Set these in .env or add them to the account entry in config.json."
            )
            continue

        account.setdefault("telegram_chat_ids", [])
        account.setdefault("grades_new_days", 1)
        account.setdefault("report_prompt", "")

        valid_accounts.append(account)

    return valid_accounts


def load_config() -> dict:
    """Load config.json, discover & merge accounts from env vars, validate, apply log level."""
    _load_env()

    if not CONFIG_PATH.exists():
        log.error("config.json not found! See README.md for setup.")
        sys.exit(1)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)

    # Build the final accounts list by merging config entries + env-discovered accounts
    cfg["accounts"] = _build_accounts(cfg)

    if not cfg["accounts"]:
        log.error(
            "No valid accounts configured. "
            "Set LIBRUS_USERNAME1, LIBRUS_PASSWORD1, TELEGRAM_CHAT_IDS1 in .env "
            "or add a fully configured account entry (with 'id') to config.json."
        )
        sys.exit(1)

    # Inject bot token
    bot_token_env = os.environ.get("TELEGRAM_BOT_TOKEN")
    if bot_token_env:
        cfg.setdefault("telegram", {})["bot_token"] = bot_token_env

    # Inject Claude API key
    claude_key_env = os.environ.get("CLAUDE_API_KEY")
    if claude_key_env:
        cfg.setdefault("claude", {})["api_key"] = claude_key_env

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


def get_allowed_chat_ids(cfg: dict) -> set[str]:
    """Return the set of all chat IDs that are allowed to interact with the bot.

    Combines every per-account TELEGRAM_CHAT_IDS* value and the global
    telegram.chat_ids fallback so a single authoritative allowlist is used
    for command gating in the webhook handler.
    """
    allowed: set[str] = set()
    for account in cfg.get("accounts", []):
        for cid in account.get("telegram_chat_ids", []):
            allowed.add(str(cid))
        single = account.get("telegram_chat_id")
        if single:
            allowed.add(str(single))
    for cid in cfg.get("telegram", {}).get("chat_ids", []):
        allowed.add(str(cid))
    single_global = cfg.get("telegram", {}).get("chat_id")
    if single_global:
        allowed.add(str(single_global))
    return allowed
