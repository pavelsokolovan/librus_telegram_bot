# fly-deploy.ps1
# Deploy to Fly.io and disable the scheduler on all non-primary machines.
# Usage: .\fly-deploy.ps1

$APP = "librus-telegram-bot"   # must match app name in fly.toml

# ── Deploy ────────────────────────────────────────────────────────────────────
Write-Host "Deploying $APP ..." -ForegroundColor Cyan
fly deploy
if ($LASTEXITCODE -ne 0) { Write-Error "fly deploy failed"; exit 1 }

# ── Disable scheduler on non-primary machines ─────────────────────────────────
Write-Host "`nFetching machine list ..." -ForegroundColor Cyan
$json = fly machines list --app $APP --json | Out-String
$machines = $json | ConvertFrom-Json

# Keep only started machines, sorted by ID (smallest = primary / leader)
$started = $machines | Where-Object { $_.state -eq "started" } | Sort-Object id

if ($started.Count -le 1) {
    Write-Host "Only one running machine — nothing to do." -ForegroundColor Green
    exit 0
}

$primary   = $started[0]
$secondary = $started[1..$($started.Count - 1)]

Write-Host "Primary machine  : $($primary.id) (SCHEDULER_ENABLED left as-is)" -ForegroundColor Green

foreach ($m in $secondary) {
    Write-Host "Disabling scheduler on machine $($m.id) ..." -ForegroundColor Yellow
    fly machine update $m.id --app $APP -e SCHEDULER_ENABLED=false --yes
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to update machine $($m.id) — set SCHEDULER_ENABLED=false manually."
    } else {
        Write-Host "  Done: $($m.id)" -ForegroundColor Green
    }
}

Write-Host "`nDeploy complete." -ForegroundColor Cyan
