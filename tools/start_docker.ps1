$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$originalLocation = Get-Location
try {
    Set-Location -LiteralPath $workspace
    & (Join-Path $PSScriptRoot 'initialize_docker.ps1')
    $state = Get-Content -LiteralPath '.secrets/deployment-state.json' -Raw | ConvertFrom-Json
    if ($state.active -notin @('blue','green')) { throw 'Invalid active slot' }
    $service = "app-$($state.active)"
    docker compose up -d --no-deps --wait --wait-timeout 180 $service
    if ($LASTEXITCODE -ne 0) { throw 'Active application did not become ready' }
    docker compose up -d --no-deps --wait --wait-timeout 120 app cloudflared
    if ($LASTEXITCODE -ne 0) { throw 'Gateway or tunnel did not become ready' }
    Write-Output "Started $service, gateway and tunnel only"
} finally {
    Set-Location -LiteralPath $originalLocation
}
