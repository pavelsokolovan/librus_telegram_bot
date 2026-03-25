"""Telegram message delivery."""

import logging

log = logging.getLogger(__name__)


async def send_message(bot_token: str, chat_id: str, text: str, account_name: str):
    """Send a message (auto-splits at 4000 chars, falls back to plain text on Markdown errors)."""
    import telegram

    bot = telegram.Bot(token=bot_token)
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        try:
            await bot.send_message(chat_id=chat_id, text=chunk, parse_mode="Markdown")
        except Exception:
            await bot.send_message(chat_id=chat_id, text=chunk)
    log.info(f"[{account_name}]  Telegram sent to chat_id={chat_id}")
