param(
    [switch]$Flash,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"

# Board is driven by hardware_config.json so it stays in sync with the loggers.
$configPath = Join-Path $PSScriptRoot "data_collectors\hardware_config.json"
$config     = Get-Content -Raw -Path $configPath | ConvertFrom-Json
$board      = $config.boards.($config.active_board).zephyr_board

$targets = @(
    [ordered]@{ name = "smoke";                      app = "zephyr_inference/smoke_app"                 },
    [ordered]@{ name = "power_expert_logger";         app = "data_collectors/power_expert_logger"        },
    [ordered]@{ name = "motor_expert_logger";         app = "data_collectors/motor_expert_logger"        },
    [ordered]@{ name = "motor_driver_expert_logger";  app = "data_collectors/motor_driver_expert_logger" },
    [ordered]@{ name = "esp32_expert_logger";         app = "data_collectors/esp32_expert_logger"        },
    [ordered]@{ name = "lighting_expert_logger";      app = "data_collectors/lighting_expert_logger"     }
)

Write-Host ""
Write-Host "Board  : $board"
Write-Host "Targets: $($targets.Count)"
if ($Rebuild) { Write-Host "Mode   : clean rebuild" }
Write-Host ""

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
$results = [System.Collections.Generic.List[hashtable]]::new()

Push-Location $PSScriptRoot
try {
    foreach ($t in $targets) {
        $buildDir = "C:\b\$($t.name)"

        if ($Rebuild -and (Test-Path $buildDir)) {
            Write-Host "-- Removing $buildDir"
            Remove-Item -Recurse -Force $buildDir
        }

        Write-Host "-- Building $($t.name) -> $buildDir"
        $start = Get-Date
        $ok = $true

        try {
            west build -b $board $t.app -d $buildDir
            if ($LASTEXITCODE -ne 0) { throw "exit code $LASTEXITCODE" }
        } catch {
            $ok = $false
            Write-Host "   FAILED: $_" -ForegroundColor Red
        }

        $elapsed = [int](Get-Date).Subtract($start).TotalSeconds
        $results.Add(@{ name = $t.name; buildDir = $buildDir; ok = $ok; elapsed = $elapsed })
        Write-Host ""
    }
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host "==========================================="
Write-Host "Build summary"
Write-Host "==========================================="
$allOk = $true
foreach ($r in $results) {
    if ($r.ok) {
        $status = "OK  "
        $color  = "Green"
    } else {
        $status = "FAIL"
        $color  = "Red"
        $allOk  = $false
    }
    Write-Host ("  {0,-4} {1,-35} {2,4}s" -f $status, $r.name, $r.elapsed) -ForegroundColor $color
}
Write-Host "==========================================="
Write-Host ""

if (-not $allOk) {
    Write-Host "One or more builds failed." -ForegroundColor Yellow
    if (-not $Flash) { exit 1 }
}

# ---------------------------------------------------------------------------
# Flash (optional)
# ---------------------------------------------------------------------------
if ($Flash) {
    $built = @($results | Where-Object { $_.ok })
    if ($built.Count -eq 0) {
        Write-Host "Nothing to flash - all builds failed." -ForegroundColor Red
        exit 1
    }

    Write-Host "Flashing $($built.Count) image(s) one at a time."
    Write-Host "Keep the same ESP32 connected for each, or swap boards between prompts."
    Write-Host ""

    Push-Location $PSScriptRoot
    try {
        foreach ($r in $built) {
            Write-Host "-------------------------------------------"
            Write-Host "Next: $($r.name)"
            Write-Host "-------------------------------------------"
            $null = Read-Host "Connect ESP32 then press Enter to flash (Ctrl+C to stop)"
            west flash -d $r.buildDir
            Write-Host "Flashed $($r.name)" -ForegroundColor Green
            Write-Host ""
        }
    } finally {
        Pop-Location
    }

    Write-Host "All done." -ForegroundColor Green
}
