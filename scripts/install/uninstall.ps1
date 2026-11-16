<#
.SYNOPSIS  Remove Whasp. Keeps %ProgramData%\whasp (config, audit log) unless -Purge is given. Run elevated.
#>
[CmdletBinding()]
param(
  [switch]$Purge,
  [string]$Prefix = (Join-Path $env:ProgramFiles 'Whasp'),
  [string]$Conf = (Join-Path $env:ProgramData 'whasp')
)
$ErrorActionPreference = 'Stop'
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run as Administrator.' }

if (Get-ScheduledTask -TaskName 'WhaspPanel' -ErrorAction SilentlyContinue) {
  Stop-ScheduledTask -TaskName 'WhaspPanel' -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName 'WhaspPanel' -Confirm:$false
}
# A panel started by hand (whasp start) or left over from the task keeps files and logs locked: end it too
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.ProcessId -ne $PID -and $_.Name -match '^pythonw?(\d.*)?\.exe$' -and $_.CommandLine -match '-m\s+whasp' } |
  ForEach-Object { Write-Host "Stopping whasp process $($_.ProcessId)"; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$kept = ($machinePath -split ';') | Where-Object { $_ -and $_ -ne $Prefix }
[Environment]::SetEnvironmentVariable('Path', ($kept -join ';'), 'Machine')
if (Test-Path -LiteralPath $Prefix) { Remove-Item -LiteralPath $Prefix -Recurse -Force }
if ($Purge) {
  if (Test-Path -LiteralPath $Conf) { Remove-Item -LiteralPath $Conf -Recurse -Force }
  Write-Host 'Config and logs removed.'
} else {
  Write-Host "Kept $Conf (use -Purge to delete)."
}
Write-Host 'whasp removed. nginx sites, Task Scheduler tasks (folder \Whasp), firewall rules named "Whasp:*" and backups it created are left in place.'
