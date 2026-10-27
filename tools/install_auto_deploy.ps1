$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $workspace 'venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'The local venv with pythonw.exe is required' }
if (-not (Test-Path -LiteralPath (Join-Path $workspace '.secrets\deployment-state.json'))) {
    throw 'Initialize and deploy the Docker stack first'
}
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments = '-B "' + (Join-Path $PSScriptRoot 'auto_deploy.py') + '"'
$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $workspace
$timer = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$logon = New-ScheduledTaskTrigger -AtLogOn -User $user
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'MapPredictApp-AutoDeploy' -Action $action `
    -Trigger @($timer,$logon) -Settings $settings -Principal $principal `
    -Description 'Deploy CI-verified main revisions using the existing Docker stack' -Force | Out-Null
Write-Output 'Auto deployment installed, checks every five minutes while this user is logged in'
