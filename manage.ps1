# manage.ps1 — DayZ Trader Service Manager
param([string]$Action = "status")

$services = @("DayZTraderBot", "DayZTraderWeb", "cloudflared")

switch ($Action) {
    "start" {
        $services | ForEach-Object { Start-Service $_; Write-Host "✅ Started: $_" }
    }
    "stop" {
        $services | ForEach-Object { Stop-Service $_; Write-Host "🛑 Stopped: $_" }
    }
    "restart" {
        $services | ForEach-Object { Restart-Service $_; Write-Host "🔄 Restarted: $_" }
    }
    "status" {
        $services | ForEach-Object {
            $svc = Get-Service $_
            $icon = if ($svc.Status -eq "Running") { "🟢" } else { "🔴" }
            Write-Host "$icon $_ — $($svc.Status)"
        }
    }
    "logs-bot"  { Get-Content C:\DayZTrader\logs\bot.log -Tail 50 -Wait }
    "logs-web"  { Get-Content C:\DayZTrader\logs\web.log -Tail 50 -Wait }
}
