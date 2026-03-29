"""
Librus Synergia → Telegram Bot (Webhook Mode)
==============================================
Fetches grades, homework, announcements, attendance, timetable
from multiple Librus accounts and sends AI-formatted reports to Telegram.

Modes:
    python librus_bot.py              # start webhook server (default, for hosting)
    python librus_bot.py --once       # run all accounts once and exit (legacy / Windows Task Scheduler)
    python librus_bot.py --test       # test config + connections, no send
    python librus_bot.py --account "Jan Kowalski"   # run one account only (implies --once)

Webhook server environment variables (.env):
    WEBHOOK_URL      public HTTPS URL of this server (e.g. https://myapp.railway.app)
    PORT             HTTP port to listen on (default: 8080)
    WEBHOOK_SECRET   secret token used to validate incoming Telegram updates
    SCHEDULE_HOUR    hour for the daily report (optional — omit to disable scheduled reports)
    SCHEDULE_MINUTE  minute for the daily report (optional, default: 0 when SCHEDULE_HOUR is set)
"""

import asyncio
import logging
import os
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

from src.config import load_config, resolve_chat_ids, get_allowed_chat_ids
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


# ── Run All Accounts ───────────────────────────────────────────────────────────
async def run_all_accounts(cfg: dict, filter_name: str = None):
    """Run reports for all accounts (or one filtered by name)."""
    accounts = cfg["accounts"]
    if filter_name:
        accounts = [a for a in accounts if filter_name.lower() in a["name"].lower()]
        if not accounts:
            log.error(f"No account matching '{filter_name}'")
            return
    log.info(f"Running for {len(accounts)} account(s)")
    for account in accounts:
        await process_account(account, cfg)
    log.info("All accounts processed.")


# ── Webhook Server ─────────────────────────────────────────────────────────────
def _get_server_settings(cfg: dict) -> dict:
    """Resolve server settings from env vars with config.json fallbacks."""
    wh = cfg.get("webhook", {})
    return {
        "url": os.environ.get("WEBHOOK_URL") or wh.get("url", ""),
        "port": int(os.environ.get("PORT") or wh.get("port", 8080)),
        "secret": os.environ.get("WEBHOOK_SECRET") or wh.get("secret", ""),
        "schedule_hour": int(os.environ["SCHEDULE_HOUR"]) if os.environ.get("SCHEDULE_HOUR") is not None else (int(wh["schedule_hour"]) if "schedule_hour" in wh else None),
        "schedule_minute": int(os.environ["SCHEDULE_MINUTE"]) if os.environ.get("SCHEDULE_MINUTE") is not None else (int(wh["schedule_minute"]) if "schedule_minute" in wh else None),
    }


async def start_webhook_server(cfg: dict):
    """Start the aiohttp server with APScheduler for the hosted webhook mode."""
    from aiohttp import web
    from telegram import Bot, Update
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    settings = _get_server_settings(cfg)
    bot = Bot(token=cfg["telegram"]["bot_token"])
    scheduler = AsyncIOScheduler()

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def health(request):
        return web.Response(text="OK")

    async def webhook_handler(request):
        """Receive Telegram updates pushed by Telegram servers."""
        if settings["secret"]:
            token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if token != settings["secret"]:
                raise web.HTTPForbidden()
        try:
            data = await request.json()
        except Exception:
            raise web.HTTPBadRequest()

        update = Update.de_json(data, bot)
        message = update.message or update.edited_message
        if message and message.text:
            text = message.text.strip()
            chat_id = str(message.chat_id)

            allowed_ids = get_allowed_chat_ids(cfg)
            if allowed_ids and chat_id not in allowed_ids:
                log.warning(f"Unauthorized access attempt from chat_id={chat_id} — ignoring")
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "⛔ *Access denied.*\n\n"
                        "Your chat ID is not authorised to use this bot.\n"
                        f"Ask the owner to add `{chat_id}` to the allowed list."
                    ),
                    parse_mode="Markdown",
                )
                return web.Response()

            if text.startswith("/run"):
                parts = text.split(maxsplit=1)
                fname = parts[1] if len(parts) > 1 else None
                asyncio.create_task(run_all_accounts(cfg, fname))
                reply = (
                    f"🚀 Running report for *{fname}*..."
                    if fname
                    else "🚀 Running reports for all accounts..."
                )
                await bot.send_message(chat_id=chat_id, text=reply, parse_mode="Markdown")
            elif text.startswith("/status"):
                count = len(cfg["accounts"])
                await bot.send_message(chat_id=chat_id, text=f"✅ Bot is running.\nMonitoring {count} account(s).")
            elif text.startswith("/help"):
                help_text = (
                    "*Librus Bot commands:*\n"
                    "/run — send reports for all accounts now\n"
                    "/run <name> — send report for one account\n"
                    "/status — show bot status\n"
                    "/help — show this message"
                )
                await bot.send_message(chat_id=chat_id, text=help_text, parse_mode="Markdown")
        return web.Response()

    async def trigger_handler(request):
        """HTTP POST /trigger — manually triggers all accounts; protected by WEBHOOK_SECRET."""
        if settings["secret"]:
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {settings['secret']}":
                raise web.HTTPForbidden()
        asyncio.create_task(run_all_accounts(cfg))
        return web.Response(text="Triggered")

    # ── Startup / Cleanup ──────────────────────────────────────────────────────

    async def on_startup(app: web.Application):
        if settings["url"]:
            hook_url = settings["url"].rstrip("/") + "/webhook"
            set_kwargs = {"url": hook_url}
            if settings["secret"]:
                set_kwargs["secret_token"] = settings["secret"]
            await bot.set_webhook(**set_kwargs)
            log.info(f"Telegram webhook registered → {hook_url}")
        else:
            log.warning("WEBHOOK_URL not set — Telegram webhook NOT registered. Bot won't receive /run commands.")

        if settings["schedule_hour"] is not None:
            scheduler.add_job(
                run_all_accounts,
                "cron",
                args=[cfg],
                hour=settings["schedule_hour"],
                minute=settings["schedule_minute"] or 0,
            )
            scheduler.start()
            log.info(
                f"Scheduler started — daily reports at "
                f"{settings['schedule_hour']:02d}:{(settings['schedule_minute'] or 0):02d}"
            )
        else:
            log.info("Scheduler disabled — SCHEDULE_HOUR not set. Use /run or POST /trigger to send reports.")

    async def on_cleanup(app: web.Application):
        scheduler.shutdown(wait=False)
        if settings["url"]:
            await bot.delete_webhook()
        log.info("Shutdown complete")

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_post("/webhook", webhook_handler)
    app.router.add_post("/trigger", trigger_handler)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings["port"])
    await site.start()
    log.info(f"Server listening on 0.0.0.0:{settings['port']}")
    log.info("Endpoints: GET /health  POST /webhook  POST /trigger")

    try:
        await asyncio.Event().wait()  # run until interrupted
    finally:
        await runner.cleanup()


# ── Main ───────────────────────────────────────────────────────────────────────
async def main():
    cfg = load_config()
    test_mode = "--test" in sys.argv
    once_mode = "--once" in sys.argv

    filter_name = None
    if "--account" in sys.argv:
        idx = sys.argv.index("--account")
        if idx + 1 < len(sys.argv):
            filter_name = sys.argv[idx + 1]

    if test_mode:
        accounts = cfg["accounts"]
        if filter_name:
            accounts = [a for a in accounts if filter_name.lower() in a["name"].lower()]
        log.info(f"TEST MODE — {len(accounts)} account(s)")
        for account in accounts:
            await process_account(account, cfg, test_mode=True)
        return

    if once_mode or filter_name:
        # Legacy / Task Scheduler mode: run once and exit
        await run_all_accounts(cfg, filter_name)
        return

    # Default: start webhook server (for cloud hosting)
    await start_webhook_server(cfg)


if __name__ == "__main__":
    asyncio.run(main())
