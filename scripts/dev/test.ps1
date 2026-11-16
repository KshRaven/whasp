# Everything that can be checked without admin rights or network: syntax, JS syntax, unit + end-to-end tests (Windows).
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
function Py { if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 @args } else { & python @args } }
Py -m compileall -q whasp
if ($LASTEXITCODE) { exit $LASTEXITCODE }
if (Get-Command node -ErrorAction SilentlyContinue) {
  Get-ChildItem whasp\web -Recurse -Filter *.js | ForEach-Object { & node --check $_.FullName; if ($LASTEXITCODE) { exit $LASTEXITCODE } }
} else { Write-Host '(node not found: skipping JS syntax check)' }
Py -W ignore -m unittest discover -s tests -v @args
exit $LASTEXITCODE
