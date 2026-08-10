[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:5000"
)

$ErrorActionPreference = "Stop"
$base = $BaseUrl.TrimEnd("/")
$checks = @(
    @{ Path = "/health"; Label = "Health" },
    @{ Path = "/"; Label = "Dashboard" },
    @{ Path = "/catalog"; Label = "Catalog" },
    @{ Path = "/vehicles?as_role=admin"; Label = "Vehicles" },
    @{ Path = "/wallet/me?discord_user_id=demo-player"; Label = "Player wallet" },
    @{ Path = "/wallet/admin?as_role=admin"; Label = "Admin wallet" },
    @{ Path = "/admin/operations?as_role=admin"; Label = "Operations" },
    @{ Path = "/admin/map?as_role=admin"; Label = "Map" }
)

foreach ($check in $checks) {
    $uri = "$base$($check.Path)"
    $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 15
    if ($response.StatusCode -ne 200) {
        throw "$($check.Label) returned HTTP $($response.StatusCode): $uri"
    }
    Write-Host "OK $($check.Label): $uri"
}

Write-Host "Web smoke passed for $base."
