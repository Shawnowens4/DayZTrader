[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repositoryRoot

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host "==> $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Invoke-Checked "Validate Docker Compose configuration" {
    docker compose config --quiet
}

Invoke-Checked "Start the local PostgreSQL service" {
    docker compose up -d db
}

Write-Host "==> Wait for PostgreSQL readiness"
$databaseReady = $false
for ($attempt = 1; $attempt -le 30; $attempt++) {
    docker compose exec -T db pg_isready -U dxemb -d dxemb *> $null
    if ($LASTEXITCODE -eq 0) {
        $databaseReady = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $databaseReady) {
    throw "PostgreSQL did not become ready within 60 seconds"
}

Invoke-Checked "Run harness and schema smoke checks" {
    python.exe -m pytest tests/test_harness_smoke.py tests/test_schema_contracts.py -q
}

Invoke-Checked "Run broad web regression suite" {
    python.exe -m pytest `
        tests/test_wallet_web_routes.py `
        tests/test_wallet_ledger_service.py `
        tests/test_admin_operations_web_routes.py `
        tests/test_local_auth_resolution.py `
        tests/test_catalog_admin_workspace.py `
        tests/test_web_visual_foundation_slice_a.py `
        tests/test_admin_map_web_routes.py `
        tests/test_market_web_routes.py `
        tests/test_auto_trader_web_routes.py `
        tests/test_auto_trader_order_service.py `
        tests/test_games_tasks_missions_web_routes.py `
        tests/test_nitrado_delivery_web_routes.py `
        -q
}

Write-Host "Local acceptance gate passed."
