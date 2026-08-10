[CmdletBinding()]
param(
    [string]$EnvironmentFile = ".env.host"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repositoryRoot

if (-not (Test-Path $EnvironmentFile -PathType Leaf)) {
    throw "Missing $EnvironmentFile. Copy .env.host.example to .env.host and replace placeholders."
}

$environmentText = Get-Content $EnvironmentFile -Raw
if ($environmentText -match "CHANGE_ME") {
    throw "$EnvironmentFile still contains CHANGE_ME placeholders."
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose is unavailable."
}

$previousHostEnvironmentFile = $env:HOST_ENV_FILE
$env:HOST_ENV_FILE = $EnvironmentFile
docker compose --env-file $EnvironmentFile -f docker-compose.host.yml config --quiet
$env:HOST_ENV_FILE = $previousHostEnvironmentFile
if ($LASTEXITCODE -ne 0) {
    throw "Hosted Compose configuration is invalid."
}

Write-Host "Host preflight passed. No containers were changed."
