# PowerShell 24/7 Watchdog Loop for Cheat Code Telegram Bot
$ErrorActionPreference = "Continue"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  CHEAT CODE TELEGRAM BOT - 24/7 LOCAL WATCHDOG" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$pythonExe = Join-Path $scriptDir "venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "py"
}

if (-not (Test-Path ".env")) {
    Write-Host "[!] .env file not found. Creating from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[!] Please edit .env with your TELEGRAM_BOT_TOKEN and API key before running." -ForegroundColor Red
    pause
    exit 1
}

while ($true) {
    Write-Host "[+] Starting bot process at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')..." -ForegroundColor Green
    & $pythonExe bot.py
    $exitCode = $LASTEXITCODE
    Write-Host "[!] Bot stopped with exit code $exitCode at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Yellow
    Write-Host "[!] Restarting in 5 seconds... Press Ctrl+C to stop watchdog." -ForegroundColor Gray
    Start-Sleep -Seconds 5
}
