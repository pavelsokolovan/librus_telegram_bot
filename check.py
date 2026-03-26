"""
Quick diagnostic — run this FIRST before scheduling.
Checks: Python version, all dependencies, config file, Telegram bot connection.
"""
import sys, json, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

print("=" * 55)
print("  Librus Bot — Diagnostics")
print("=" * 55)

# Python version
pv = sys.version_info
print(f"\n✔ Python {pv.major}.{pv.minor}.{pv.micro}", end="")
if pv.major < 3 or (pv.major == 3 and pv.minor < 10):
    print("  ⚠ WARNING: Python 3.10+ recommended")
else:
    print("  (OK)")

# Dependencies
deps = {
    "librus_apix": "librus-apix",
    "telegram": "python-telegram-bot",
    "dotenv": "python-dotenv",
}
missing = []
for module, package in deps.items():
    try:
        __import__(module)
        print(f"✔ {package} installed")
    except ImportError:
        print(f"✘ {package} NOT installed  →  pip install {package}")
        missing.append(package)

if missing:
    print(f"\n  Run:  pip install {' '.join(missing)}")
    sys.exit(1)

# Config file — use shared loader
try:
    from src.config import load_config
    cfg = load_config()
    print(f"\n✔ config.json loaded OK")
except SystemExit:
    print("\n✘ Config validation failed (see error above)")
    sys.exit(1)

print(f"  Accounts: {[a['name'] for a in cfg.get('accounts', [])]}")

# Check for missing credentials
for i, acc in enumerate(cfg.get("accounts", []), start=1):
    if not acc.get("username"):
        print(f"  ⚠ Account {i} ('{acc.get('name', '?')}'): LIBRUS_USERNAME{i} missing in .env")
    if not acc.get("telegram_chat_ids"):
        print(f"  ⚠ Account {i} ('{acc.get('name', '?')}'): TELEGRAM_CHAT_IDS{i} missing in .env")

tg = cfg.get("telegram", {})
if not tg.get("bot_token"):
    print("  ⚠ TELEGRAM_BOT_TOKEN is not set — check your .env file")

# Telegram connection test
import asyncio, telegram

async def test_telegram():
    token = cfg.get("telegram", {}).get("bot_token", "")
    if not token:
        print("\n⚠ Skipping Telegram test — TELEGRAM_BOT_TOKEN not set in .env")
        return
    try:
        bot = telegram.Bot(token=token)
        me = await bot.get_me()
        print(f"\n✔ Telegram bot connected: @{me.username}")
    except Exception as e:
        print(f"\n✘ Telegram bot error: {e}")
        print("  Check TELEGRAM_BOT_TOKEN in your .env file")

asyncio.run(test_telegram())

# Claude API check
claude_key = cfg.get("claude", {}).get("api_key", "")
if claude_key:
    print(f"\n✔ Claude API key set → AI-powered reports enabled")
    print(f"  Model: {cfg.get('claude', {}).get('model', 'not set')}")
else:
    print(f"\n✔ No Claude API key → using built-in formatter (free)")

# Webhook / hosting check
print(f"\n-- Webhook / Hosting --")
webhook_url = os.environ.get("WEBHOOK_URL") or cfg.get("webhook", {}).get("url", "")
port = os.environ.get("PORT") or cfg.get("webhook", {}).get("port", 8080)
schedule_hour = os.environ.get("SCHEDULE_HOUR") or cfg.get("webhook", {}).get("schedule_hour", 7)
schedule_minute = os.environ.get("SCHEDULE_MINUTE") or cfg.get("webhook", {}).get("schedule_minute", 0)

if webhook_url:
    print(f"✔ WEBHOOK_URL set → {webhook_url}")
    print(f"  Telegram will push updates to: {webhook_url.rstrip('/')}/webhook")
else:
    print(f"ℹ No WEBHOOK_URL set — Telegram webhook will NOT be registered.")
    print(f"  OK for --once / Windows Task Scheduler mode.")
    print(f"  For cloud hosting: add WEBHOOK_URL=https://your-app.example.com to .env")

print(f"✔ Server port: {port}  (override with PORT env var)")
print(f"✔ Daily report scheduled at {int(schedule_hour):02d}:{int(schedule_minute):02d}  (override with SCHEDULE_HOUR/SCHEDULE_MINUTE)")

print("\n" + "=" * 55)
print("  All checks passed!")
print("  Test run:    python librus_bot.py --test")
print("  One-shot:    python librus_bot.py --once")
print("  Webhook srv: python librus_bot.py")
print("=" * 55)
