param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("power_expert_logger", "motor_expert_logger", "motor_driver_expert_logger", "esp32_expert_logger", "lighting_expert_logger")]
    [string]$Expert,

    [switch]$Flash
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $PSScriptRoot "hardware_config.json"
$config = Get-Content -Raw -Path $configPath | ConvertFrom-Json
$activeBoard = $config.active_board
$board = $config.boards.$activeBoard

if (-not $board) {
    throw "Active board '$activeBoard' was not found in hardware_config.json"
}

$zephyrBoard = $board.zephyr_board
$appPath = "data_collectors/$Expert"
$buildDir = "build/$Expert"

Write-Host "Expert: $Expert"
Write-Host "Hardware config: $activeBoard"
Write-Host "Zephyr board: $zephyrBoard"

Push-Location $repoRoot
try {
    west build -b $zephyrBoard $appPath -d $buildDir

    if ($Flash) {
        west flash -d $buildDir
    }
} finally {
    Pop-Location
}
