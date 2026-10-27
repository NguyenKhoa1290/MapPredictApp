param([switch]$Pull)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$originalLocation = Get-Location
$lockStream = $null
try {
    Set-Location -LiteralPath $workspace
    $secretDirectory = Join-Path $workspace '.secrets'
    $statePath = Join-Path $secretDirectory 'deployment-state.json'
    $configPath = Join-Path $workspace 'deploy/local/nginx/active.conf'
    if (-not (Test-Path -LiteralPath $statePath)) { throw 'Initialize the Docker stack before running an update' }
    $lockStream = [IO.File]::Open((Join-Path $secretDirectory 'deploy.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    if ($Pull) {
        git pull --ff-only origin main
        if ($LASTEXITCODE -ne 0) { throw 'Git pull failed, running services were preserved' }
    }
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    if ($state.active -notin @('blue','green')) { throw 'Invalid active slot' }
    $next = if ($state.active -eq 'blue') { 'green' } else { 'blue' }
    $service = "app-$next"
    $previousService = "app-$($state.active)"
    # Old nginx workers may still have an in-flight request to the inactive slot.
    $deadline = (Get-Date).AddSeconds(190)
    do {
        $processList = @(docker compose exec -T app ps -o args)
        if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the current gateway, no service was changed' }
        $draining = @($processList | Where-Object { $_ -match '^nginx: worker process is shutting down' }).Count -gt 0
        if ($draining) {
            if ((Get-Date) -gt $deadline) { throw 'Previous requests are still draining, no service was changed' }
            Write-Output 'Waiting for previous requests to drain'
            Start-Sleep -Seconds 3
        }
    } while ($draining)
    docker compose build $service
    if ($LASTEXITCODE -ne 0) { throw 'Build failed, active slot was preserved' }
    docker compose up -d --no-deps --force-recreate --wait --wait-timeout 180 $service
    if ($LASTEXITCODE -ne 0) { throw 'Candidate failed health check, active slot was preserved' }
    $probe = @'
from urllib.request import urlopen
import json
base='http://127.0.0.1:8000'
with urlopen(base+'/api/v1/predictions/model',timeout=10) as r:
    assert json.load(r)['data']['ready']
with urlopen(base+'/portal/',timeout=10) as r:
    assert r.status==200
print('Candidate model and frontend are ready')
'@
    $probe | docker compose exec -T $service python -
    if ($LASTEXITCODE -ne 0) { throw 'Candidate verification failed, active slot was preserved' }
    $previousConfiguration = [IO.File]::ReadAllText($configPath)
    $maxUpload = '67108864'
    $override = @(Get-Content -LiteralPath (Join-Path $workspace '.env') | Where-Object { $_ -match '^MAP_PREDICT_MAX_UPLOAD_BYTES=\d+$' })
    if ($override) { $maxUpload = ($override[-1] -split '=',2)[1] }
    $template = [IO.File]::ReadAllText((Join-Path $workspace 'deploy/site.template.conf'))
    $nextConfiguration = $template.Replace('__BACKEND__',$service).Replace('__UPLOAD_BYTES__',$maxUpload)
    try {
        [IO.File]::WriteAllText($configPath,$nextConfiguration,[Text.UTF8Encoding]::new($false))
        docker compose exec -T app nginx -t
        if ($LASTEXITCODE -ne 0) { throw 'Proxy configuration is invalid' }
        docker compose exec -T app nginx -s reload
        if ($LASTEXITCODE -ne 0) { throw 'Proxy reload failed' }
        $stateJson = @{active=$next; updated=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json
        [IO.File]::WriteAllText($statePath,$stateJson,[Text.UTF8Encoding]::new($false))
    } catch {
        [IO.File]::WriteAllText($configPath,$previousConfiguration,[Text.UTF8Encoding]::new($false))
        docker compose exec -T app nginx -s reload
        throw
    }
    # Free standby RAM only after old nginx workers finish their requests.
    $deadline = (Get-Date).AddSeconds(190)
    do {
        $processList = @(docker compose exec -T app ps -o args)
        if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect gateway, previous slot was kept running' }
        $draining = @($processList | Where-Object { $_ -match '^nginx: worker process is shutting down' }).Count -gt 0
        if ($draining) {
            if ((Get-Date) -gt $deadline) { throw 'Deployment switched successfully, previous slot is still draining and was preserved' }
            Start-Sleep -Seconds 3
        }
    } while ($draining)
    docker compose stop $previousService
    if ($LASTEXITCODE -ne 0) { throw 'Deployment switched successfully, cannot stop previous slot' }
    docker compose rm -f $previousService
    if ($LASTEXITCODE -ne 0) { throw 'Deployment switched successfully, stopped slot could not be removed' }
    Write-Output "Deployment complete, active slot: $next. Standby was stopped, gateway, tunnel and host port were preserved."
} finally {
    if ($lockStream) { $lockStream.Dispose() }
    Set-Location -LiteralPath $originalLocation
}
