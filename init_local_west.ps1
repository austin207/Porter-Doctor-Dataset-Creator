$ErrorActionPreference = "Stop"

$westDir = Join-Path $PSScriptRoot ".west"
$configPath = Join-Path $westDir "config"

New-Item -ItemType Directory -Force -Path $westDir | Out-Null

@"
[manifest]
path = .
file = west.yml

[zephyr]
base = zephyr
"@ | Set-Content -Encoding ASCII -Path $configPath

Write-Host "Configured west workspace root at: $PSScriptRoot"
Write-Host "Next: west update"
