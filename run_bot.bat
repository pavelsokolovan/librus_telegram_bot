@echo off
REM ============================================================
REM  Librus Bot — Windows Task Scheduler Launcher
REM  Called automatically by Windows Task Scheduler each morning.
REM ============================================================

REM Change this to the full path of your librus_telegram_bot folder:
set BOT_DIR=%~dp0

cd /d "%BOT_DIR%"

echo [%DATE% %TIME%] Starting Librus Bot... >> logs\scheduler.log

call "%BOT_DIR%venv\Scripts\activate.bat"

python librus_bot.py --once >> logs\scheduler.log 2>&1

echo [%DATE% %TIME%] Done. >> logs\scheduler.log
