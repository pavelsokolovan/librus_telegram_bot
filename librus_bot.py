"""
Librus Synergia → Telegram Bot (Multi-Account)
================================================
Fetches grades, homework, announcements, attendance, timetable
from multiple Librus accounts and sends AI-formatted reports to Telegram.

Usage:
    python librus_bot.py           # run all accounts once immediately
    python librus_bot.py --test    # test config + connections, no send
    python librus_bot.py --account "Jan Kowalski"   # run one account only
"""

import asyncio
import logging
import sys
from pathlib import Path

# ── Logging ────────────────────────────────────────────────────────────────────
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,  # temporary — overridden after config loads
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "librus_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

from src.config import load_config, resolve_chat_ids
from src.fetchers import fetch_all
from src.formatters import generate_report_with_claude, format_report_fallback
from src.telegram_sender import send_message


# ── Process One Account ────────────────────────────────────────────────────────
async def process_account(account_cfg: dict, global_cfg: dict, test_mode: bool = False):
    name = account_cfg["name"]
    log.info(f"\n{'='*50}")
    log.info(f"Processing account: {name}")
    log.info(f"{'='*50}")

    bot_token = global_cfg["telegram"]["bot_token"]
    chat_ids = resolve_chat_ids(account_cfg, global_cfg)

    if not chat_ids:
        log.error(f"[{name}] No telegram chat_id configured — skipping")
        return

    # Fetch data
    try:
        data = fetch_all(account_cfg)
    except Exception as e:
        log.error(f"[{name}] Librus fetch failed: {e}")
        if not test_mode:
            err_msg = f"⚠️ *Librus Bot*\n\nNie można pobrać danych dla konta *{name}*.\n\nBłąd: `{str(e)[:200]}`"
            for cid in chat_ids:
                await send_message(bot_token, cid, err_msg, name)
        return

    # Generate report
    report = generate_report_with_claude(data, account_cfg, global_cfg)
    if not report:
        report = format_report_fallback(data)

    if test_mode:
        log.info(f"\n[{name}] TEST MODE — report preview:\n{'-'*40}\n{report}\n{'-'*40}")
        return

    # Send
    for chat_id in chat_ids:
        try:
            await send_message(bot_token, chat_id, report, name)
        except Exception as e:
            log.error(f"[{name}] Telegram send to {chat_id} failed: {e}")


# ── Main ───────────────────────────────────────────────────────────────────────
async def main():
    cfg = load_config()
    test_mode = "--test" in sys.argv

    # Filter to specific account if requested
    filter_name = None
    if "--account" in sys.argv:
        idx = sys.argv.index("--account")
        if idx + 1 < len(sys.argv):
            filter_name = sys.argv[idx + 1].lower()

    accounts = cfg["accounts"]
    if filter_name:
        accounts = [a for a in accounts if filter_name in a["name"].lower()]
        if not accounts:
            log.error(f"No account matching '{filter_name}'")
            sys.exit(1)

    log.info(f"Running for {len(accounts)} account(s){'  [TEST MODE]' if test_mode else ''}")

    for account in accounts:
        await process_account(account, cfg, test_mode=test_mode)

    log.info("All accounts processed.")


if __name__ == "__main__":
    asyncio.run(main())
