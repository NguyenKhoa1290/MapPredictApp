$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$environmentPath = Join-Path $workspace '.env'
if (-not (Test-Path -LiteralPath $environmentPath)) {
    Copy-Item -LiteralPath (Join-Path $workspace '.env.example') -Destination $environmentPath
}
$secretFolder = Join-Path $workspace '.secrets'
$configFolder = Join-Path $workspace 'deploy/local/nginx'
New-Item -ItemType Directory -Path $secretFolder -Force | Out-Null
New-Item -ItemType Directory -Path $configFolder -Force | Out-Null
$statePath = Join-Path $secretFolder 'deployment-state.json'
if (-not (Test-Path -LiteralPath $statePath)) {
    [IO.File]::WriteAllText($statePath,'{"active":"blue"}',[Text.UTF8Encoding]::new($false))
}
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if ($state.active -notin @('blue','green')) { throw 'Invalid active deployment slot' }
$configPath = Join-Path $configFolder 'active.conf'
if (-not (Test-Path -LiteralPath $configPath)) {
    $maxUpload = '67108864'
    $settings = @(Get-Content -LiteralPath $environmentPath | Where-Object { $_ -match '^MAP_PREDICT_MAX_UPLOAD_BYTES=\d+$' })
    if ($settings) { $maxUpload = ($settings[-1] -split '=',2)[1] }
    $template = [IO.File]::ReadAllText((Join-Path $workspace 'deploy/site.template.conf'))
    [IO.File]::WriteAllText($configPath,$template.Replace('__BACKEND__',"app-$($state.active)").Replace('__UPLOAD_BYTES__',$maxUpload),[Text.UTF8Encoding]::new($false))
}
Write-Output 'Local Docker configuration is ready, existing deployment and secrets were preserved'
