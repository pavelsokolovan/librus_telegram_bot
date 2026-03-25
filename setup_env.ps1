# =============================================================
#  Librus Telegram Bot — Interactive .env Setup
#  Run once to create your .env file with all credentials.
#
#  Usage:
#      powershell -ExecutionPolicy Bypass -File setup_env.ps1
# =============================================================

$envPath = Join-Path $PSScriptRoot ".env"

Write-Host ""
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "   Librus Telegram Bot -- Interactive Setup" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will create your .env file with all credentials."
Write-Host "Press Ctrl+C at any time to cancel."
Write-Host ""

# ── Telegram Bot Token ─────────────────────────────────────────────────────────
Write-Host "-- Telegram Bot Token --" -ForegroundColor Yellow
Write-Host "1. Open Telegram and message @BotFather"
Write-Host "2. Send: /newbot"
Write-Host "3. Follow the steps, then copy the token (looks like 1234567890:ABC...)"
Write-Host ""
do {
    $botToken = Read-Host "Paste your TELEGRAM_BOT_TOKEN"
} while ([string]::IsNullOrWhiteSpace($botToken))

# ── Number of Accounts ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "-- Librus Accounts --" -ForegroundColor Yellow
Write-Host "How many children / Librus accounts do you want to configure?"
Write-Host "(Match the number of accounts in config.json)"
Write-Host ""
do {
    $countStr = Read-Host "Number of accounts (1 or 2)"
    $accountCount = 0
    [int]::TryParse($countStr, [ref]$accountCount) | Out-Null
} while ($accountCount -lt 1)

# ── Telegram Chat ID hint ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "-- How to get your Telegram Chat ID --" -ForegroundColor Yellow
Write-Host "  1. Open Telegram and message @userinfobot"
Write-Host "  2. It replies with your numeric ID (e.g. 987654321)"
Write-Host "  3. IMPORTANT: also send /start to your new bot first!"
Write-Host ""
Read-Host "Press Enter when ready to fill in account details"

# ── Per-Account Details ────────────────────────────────────────────────────────
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("# Telegram")
$lines.Add("TELEGRAM_BOT_TOKEN=$botToken")
$lines.Add("")

for ($i = 1; $i -le $accountCount; $i++) {
    Write-Host ""
    Write-Host "-- Account $i --" -ForegroundColor Yellow

    do {
        $name = Read-Host "  Child's name (shown in reports, e.g. Anna)"
    } while ([string]::IsNullOrWhiteSpace($name))

    do {
        $username = Read-Host "  Librus login (e-dziennik username)"
    } while ([string]::IsNullOrWhiteSpace($username))

    # Read password without echoing it
    $securePwd = Read-Host "  Librus password" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePwd)
    $password = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

    do {
        $chatIds = Read-Host "  Telegram Chat ID for $name (from @userinfobot)"
    } while ([string]::IsNullOrWhiteSpace($chatIds))

    $lines.Add("# Account $i -- $name")
    $lines.Add("ACCOUNT_NAME$i=$name")
    $lines.Add("LIBRUS_USERNAME$i=$username")
    $lines.Add("LIBRUS_PASSWORD$i=$password")
    $lines.Add("TELEGRAM_CHAT_IDS$i=$chatIds")
    $lines.Add("")
}

# ── Write File ─────────────────────────────────────────────────────────────────
if (Test-Path $envPath) {
    Write-Host ""
    Write-Host ".env already exists at: $envPath" -ForegroundColor Yellow
    $overwrite = Read-Host "Overwrite? (y/n)"
    if ($overwrite -notin @("y", "Y")) {
        Write-Host "Cancelled. Existing .env was not changed." -ForegroundColor Red
        exit
    }
}

# Write UTF-8 without BOM (important for Python dotenv)
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllLines($envPath, $lines, $utf8NoBom)

Write-Host ""
Write-Host "====================================================" -ForegroundColor Green
Write-Host "  .env created: $envPath" -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Activate venv:   venv\Scripts\activate"
Write-Host "  2. Run diagnostics: python check.py"
Write-Host "  3. Test report:     python librus_bot.py --test"
Write-Host "  4. Send for real:   python librus_bot.py"
Write-Host ""
