# 📚 Librus Telegram Bot

Automatic bot that sends daily reports from **multiple Librus Synergia accounts** to Telegram.
Fetches grades, homework, announcements, messages, attendance, timetable and lesson topics.
Optionally: AI-generated reports (Claude) using your own custom prompt.

---

## 📦 Package Contents

```
librus_telegram_bot/
├── librus_bot.py       ← main script
├── config.json         ← configuration (non-sensitive settings)
├── .env                ← credentials & personal values (created by you, never committed)
├── .env.example        ← template for the above
├── setup_env.ps1       ← interactive script to create .env
├── requirements.txt    ← Python dependencies
├── run_bot.bat         ← launcher for Windows Task Scheduler
├── check.py            ← diagnostics before first run
└── logs/               ← log files (created automatically)
```

---

## 🚀 Step 1 — Install Python

Download Python **3.10 or newer** from https://python.org/downloads/

> ⚠️ During installation check ✅ **"Add Python to PATH"**

---

## 🚀 Step 2 — Install Dependencies

Open **PowerShell** in the folder containing the files:

```powershell
# Create a virtual environment (isolates dependencies)
python -m venv venv

# Activate it
venv\Scripts\activate

# Install libraries
pip install -r requirements.txt
```

> ⚠️ You need to run `venv\Scripts\activate` each time you open a new terminal.
> The `run_bot.bat` launcher does this automatically for Task Scheduler runs.

---

## 🚀 Step 3 — Set Up Credentials (`.env`)

All personal values (credentials, names, chat IDs) are stored in a `.env` file, **not** in `config.json`.

### Option A: Interactive script (recommended)

Run this once — it asks for everything and creates the file:

```powershell
powershell -ExecutionPolicy Bypass -File setup_env.ps1
```

### Option B: Manual

Copy the template and fill it in yourself:

```powershell
copy .env.example .env
```

Open `.env` and fill in all values:

```env
# Telegram bot token (from @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ

# Account 1 — first child
ACCOUNT_NAME1=Anna Kowalska
LIBRUS_USERNAME1=1234567
LIBRUS_PASSWORD1=password123
TELEGRAM_CHAT_IDS1=987654321

# Account 2 — second child (delete this block if you only have one account)
ACCOUNT_NAME2=Piotr Kowalski
LIBRUS_USERNAME2=7654321
LIBRUS_PASSWORD2=otherpassword
TELEGRAM_CHAT_IDS2=987654321
```

> 💡 **Getting your Telegram Chat ID:** Message **@userinfobot** on Telegram — it replies with your numeric ID.

> 💡 **Before the bot can message you:** Send `/start` to your bot first!

> 🔒 `.env` is in `.gitignore` and will never be committed to git.

---

## 🚀 Step 4 — Configure the Bot (`config.json`)

Open `config.json` in Notepad or VS Code. Credentials are no longer stored here.

### 4a. Librus Accounts

The accounts array in `config.json` controls **how many accounts** exist and their settings. All personal values are loaded from `.env` — leave the credential fields empty in `config.json`.

```json
"accounts": [
  {
    "name": "",
    "username": "",
    "password": "",
    "telegram_chat_ids": [],
    "grades_new_days": 1
  }
]
```

> Values are matched by position: the 1st account block uses `ACCOUNT_NAME1`, `LIBRUS_USERNAME1`, `LIBRUS_PASSWORD1`, `TELEGRAM_CHAT_IDS1` from `.env`; the 2nd block uses the `2` variants, and so on.

| Field | Source | Description |
|-------|--------|-------------|
| `name` | `.env` → `ACCOUNT_NAME1` | Display name used in reports |
| `username` | `.env` → `LIBRUS_USERNAME1` | Librus login |
| `password` | `.env` → `LIBRUS_PASSWORD1` | Librus password |
| `telegram_chat_ids` | `.env` → `TELEGRAM_CHAT_IDS1` | Telegram chat ID(s) to send the report to |
| `grades_new_days` | `config.json` | How many days back to look for new grades (`1` = today only) |
| `report_prompt` | `config.json` | *(optional)* Custom AI prompt for this account |

### 4b. Telegram Bot

**1.** Open Telegram → message **@BotFather** → send `/newbot`
**2.** Give the bot a name and username (e.g. `LibrusDailyReport_bot`)
**3.** Copy the **token** → put it in `.env` as `TELEGRAM_BOT_TOKEN=...`

**4.** Message **@userinfobot** on Telegram → it replies with your numeric chat ID
**5.** Put that ID in `.env` as `TELEGRAM_CHAT_IDS1=987654321` (for the first account)

> 💡 **Before the bot can message you:** Send `/start` to your bot first!

> The `telegram.bot_token` and `telegram.chat_ids` fields in `config.json` can be left empty — `.env` values take priority.

### 4c. Report Prompt (optional but recommended)

The `report_prompt` field controls **how the report looks**. Edit it freely:

```json
"report_prompt": "You are a school assistant. Write a concise daily summary in Polish for a parent.
Highlight urgent items: homework due tomorrow, low grades, unread messages.
Use Telegram Markdown: *bold*, _italic_, • bullet points."
```

You can also set a **different prompt per account** by adding `"report_prompt"` inside an account:

```json
{
  "name": "Anna Kowalska",
  "report_prompt": "Focus only on homework and grades. Be very brief."
}
```

### 4d. Claude AI (optional)

Without an API key the bot works for free using the built-in formatter.
With a key — reports are smarter and better formatted.

```json
"claude": {
  "api_key": "sk-ant-api03-...",
  "model": "claude-haiku-4-5-20251001",
  "max_tokens": 1500
}
```

| Model | Cost | Quality |
|-------|------|---------|
| `claude-haiku-4-5-20251001` | Cheapest (~$0.36/month for 2 accounts) | Good |
| `claude-sonnet-4-6` | Balanced | Better |
| `claude-opus-4-6` | Most expensive | Best |

Get your API key at: https://console.anthropic.com

---

## 🚀 Step 5 — Diagnostics

Check that everything is configured correctly:

```powershell
venv\Scripts\activate
python check.py
```

You should see all green ✔

---

## 🚀 Step 6 — Test Run (no sending)

```powershell
python librus_bot.py --test
```

The bot fetches data from Librus and shows a report preview in the console — nothing is sent to Telegram.

---

## 🚀 Step 7 — First Send

```powershell
python librus_bot.py
```

Check Telegram — you should receive a report for each account.

---

## 🚀 Step 8 — Automatic Scheduling (Windows Task Scheduler)

1. Press `Win + R` → type `taskschd.msc` → Enter

2. On the right: **"Create Basic Task..."**

3. Fill in:
   - **Name:** `Librus Bot`
   - **Trigger:** Daily, at **07:00** (or another time)
   - **Action:** Start a program
   - **Program:** enter the full path to `run_bot.bat`:
     ```
     C:\Users\YourName\Desktop\librus_telegram_bot\run_bot.bat
     ```

4. Click **"Open the Properties dialog when I click Finish"** ✅

5. In the **Conditions** tab:
   - Uncheck **"Start the task only if the computer is on AC power"**
   - (laptops on battery will also run the bot)

6. In the **Settings** tab:
   - Check **"Run task as soon as possible after a scheduled start is missed"**
   - (if the laptop was off at 7:00, it will run when turned on)

---

## ⌨️ Command-Line Options

| Command | Description |
|---------|-------------|
| `python librus_bot.py` | Run all accounts |
| `python librus_bot.py --test` | Preview reports, no sending |
| `python librus_bot.py --account "Anna"` | Run one account only (by name) |

---

## 📋 What the Report Contains

| Section | Data |
|---------|------|
| 🕐 Today's lessons | Timetable for today with hours |
| 📅 Tomorrow's lessons | Timetable for tomorrow with hours |
| 📋 Recent lesson topics | Topics/tasks from completed lessons (last 3 days) |
| 📝 Homework | All assignments due in the next 7 days |
| 🏆 Grades | New grades from the last N days (configurable per account via `grades_new_days`) |
| 📢 Announcements | Today's school announcements with full text |
| ✉️ Messages | Today's received messages (Wiadomości) with full body; unread marked 🔴 |
| 📊 Attendance | % for both semesters and overall |

---

## 🔧 Troubleshooting

**"ModuleNotFoundError"**
→ Make sure you activated the venv: `venv\Scripts\activate`

**"Login failed" / Librus login error**
→ Check your username and password in your `.env` file (`LIBRUS_USERNAME1` / `LIBRUS_PASSWORD1`)

**Telegram: "Chat not found"**
→ Send `/start` to your bot first, then verify your chat_id via @userinfobot

**Telegram: "Unauthorized"**
→ Bot token is invalid. Generate a new one via @BotFather

**Bot doesn't run via Task Scheduler**
→ Open `logs\scheduler.log` and check for errors
→ Make sure the path to `run_bot.bat` is absolute (not relative)

**Claude API: error 401**
→ API key is invalid or expired. Generate a new one at https://console.anthropic.com

All logs are saved to the `logs/` folder.
