# setup.ps1 — One-time setup script for DayZ Trader Bot
# Run as Administrator in PowerShell

Write-Host "🚀 DayZ Trader Bot — Setup Script" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# 1. Create virtual environment
Write-Host "`n[1/6] Creating Python virtual environment..." -ForegroundColor Yellow
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
Write-Host "`n[2/6] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# 3. Create logs folder
Write-Host "`n[3/6] Creating logs directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path .\logs | Out-Null

# 4. Copy .env if not exists
Write-Host "`n[4/6] Setting up .env file..." -ForegroundColor Yellow
if (-Not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "  ⚠️  .env created — EDIT IT before starting the bot!" -ForegroundColor Red
} else {
    Write-Host "  ✅ .env already exists" -ForegroundColor Green
}

# 5. Initialize database
Write-Host "`n[5/6] Initializing database..." -ForegroundColor Yellow
python -c "import aiosqlite, asyncio; print('DB modules OK')"

# 6. Install NSSM services
Write-Host "`n[6/6] Installing Windows services via NSSM..." -ForegroundColor Yellow
$projectPath = (Get-Location).Path
$pythonPath = "$projectPath\venv\Scripts\python.exe"

nssm install DayZTraderBot $pythonPath
nssm set DayZTraderBot AppParameters "$projectPath\main.py"
nssm set DayZTraderBot AppDirectory $projectPath
nssm set DayZTraderBot AppEnvironmentExtra "PYTHONUNBUFFERED=1"
nssm set DayZTraderBot DisplayName "DayZ Trader Discord Bot"
nssm set DayZTraderBot Start SERVICE_AUTO_START
nssm set DayZTraderBot AppStdout "$projectPath\logs\bot.log"
nssm set DayZTraderBot AppStderr "$projectPath\logs\bot_err.log"

nssm install DayZTraderWeb $pythonPath
nssm set DayZTraderWeb AppParameters "$projectPath\web\app.py"
nssm set DayZTraderWeb AppDirectory $projectPath
nssm set DayZTraderWeb DisplayName "DayZ Trader Web GUI"
nssm set DayZTraderWeb Start SERVICE_AUTO_START
nssm set DayZTraderWeb AppStdout "$projectPath\logs\web.log"
nssm set DayZTraderWeb AppStderr "$projectPath\logs\web_err.log"

Write-Host "`n✅ Setup complete!" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit .env with your tokens" -ForegroundColor White
Write-Host "  2. Run: cloudflared tunnel login" -ForegroundColor White
Write-Host "  3. Run: cloudflared tunnel create dayz-trader" -ForegroundColor White
Write-Host "  4. Run: .\manage.ps1 start" -ForegroundColor White
