$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $workspace 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
& $python -B (Join-Path $PSScriptRoot 'docker_stack.py') initialize
if ($LASTEXITCODE -ne 0) { throw 'Stack initialization failed, inspect the error above' }
