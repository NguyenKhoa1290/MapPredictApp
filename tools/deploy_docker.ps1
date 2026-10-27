param([switch]$Pull)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $workspace 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
$arguments = @('-B', (Join-Path $PSScriptRoot 'docker_stack.py'), 'deploy')
if ($Pull) { $arguments += '--pull' }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Deployment failed, inspect the error above' }
