# Debug helper (Windows): setup check + task state + recent logs.
$whasp = Join-Path $env:ProgramFiles 'Whasp\whasp.cmd'
if (Test-Path $whasp) { $run = { & $whasp @args } }
else {
  Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
  $run = { if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m whasp @args } else { & python -m whasp @args } }
}
& $run doctor
Write-Host "`n--- scheduled task ---"
$t = Get-ScheduledTask -TaskName 'WhaspPanel' -ErrorAction SilentlyContinue
if ($t) { $t | Get-ScheduledTaskInfo | Format-List TaskName, LastRunTime, LastTaskResult, NextRunTime; "State: $($t.State)" } else { '(not installed as a task)' }
Write-Host "`n--- last 20 server log lines ---"
$log = Join-Path $env:ProgramData 'whasp\logs\server.log'
if (Test-Path $log) { Get-Content $log -Tail 20 } else { '(no server.log yet)' }
Write-Host "`n--- last 10 audit events ---"
& $run logs -n 10
