param(
    [string]$Python = "python",
    [switch]$SkipPrepare,
    [switch]$IncludePlaceholders,
    [switch]$InstallDeps
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot
$env:TF_CPP_MIN_LOG_LEVEL = "2"

$UserSite = (& $Python -c "import site; print(site.getusersitepackages())").Trim()
if ($LASTEXITCODE -eq 0 -and $UserSite) {
    if ($env:PYTHONPATH) {
        $env:PYTHONPATH = "$UserSite;$env:PYTHONPATH"
    } else {
        $env:PYTHONPATH = $UserSite
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [string[]]$CommandArgs
    )

    Write-Host "==> $Name"
    & $Python @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

if ($InstallDeps) {
    Invoke-Step "Install training dependencies" @("-m", "pip", "install", "-r", "requirements.txt")
}

Invoke-Step "Check training dependencies" @("-c", "import pandas, sklearn, joblib, numpy, yaml, tensorflow")

if (-not $SkipPrepare) {
    Invoke-Step "Merge raw dataset runs" @("ai_ml/dataset_tools/merge_raw_runs.py", "--expert", "all")
    Invoke-Step "Merge per-expert raw dataset runs" @("ai_ml/dataset_tools/merge_raw_runs.py", "--per-expert")
    Invoke-Step "Build router dataset" @("ai_ml/router_dataset_builder/build_router_dataset.py")
}

$TrainJobs = @(
    @{ Name = "power_expert"; Script = "ai_ml/models/power_expert/train.py" },
    @{ Name = "motor_expert"; Script = "ai_ml/models/motor_expert/train.py" },
    @{ Name = "motor_driver_expert"; Script = "ai_ml/models/motor_driver_expert/train.py" },
    @{ Name = "esp32_expert"; Script = "ai_ml/models/esp32_expert/train.py" },
    @{ Name = "lighting_expert"; Script = "ai_ml/models/lighting_expert/train.py" },
    @{ Name = "router"; Script = "ai_ml/models/router/train.py" },
    @{ Name = "anomaly_detector"; Script = "ai_ml/models/anomaly_detector/train.py" }
)

if ($IncludePlaceholders) {
    $TrainJobs += @(
        @{ Name = "encoder_expert"; Script = "ai_ml/models/encoder_expert/train.py" },
        @{ Name = "pi_expert"; Script = "ai_ml/models/pi_expert/train.py" }
    )
}

Write-Host "==> Starting parallel training jobs"
$Jobs = foreach ($Item in $TrainJobs) {
    Start-Job -Name $Item.Name -ScriptBlock {
        param($RepoRoot, $Python, $ScriptPath, $PythonPath)

        Set-Location $RepoRoot
        $env:TF_CPP_MIN_LOG_LEVEL = "2"
        $Output = & $Python $ScriptPath 2>&1 | Out-String
        [PSCustomObject]@{
            ScriptPath = $ScriptPath
            ExitCode = $LASTEXITCODE
            Output = $Output.TrimEnd()
        }
    } -ArgumentList $RepoRoot, $Python, $Item.Script, $env:PYTHONPATH
}

$null = Wait-Job -Job $Jobs
$Failed = @()

foreach ($Job in $Jobs) {
    Write-Host ""
    Write-Host "==> Output: $($Job.Name)"
    $Result = Receive-Job -Job $Job -ErrorAction Continue
    foreach ($Item in $Result) {
        if ($Item.Output) {
            Write-Host $Item.Output
        }
        if ($Item.ExitCode -ne 0) {
            Write-Host "$($Item.ScriptPath) failed with exit code $($Item.ExitCode)"
            $Failed += $Job.Name
        }
    }

    if ($Job.State -ne "Completed") {
        $Failed += $Job.Name
    }
}

Remove-Job -Job $Jobs

if ($Failed.Count -gt 0) {
    Write-Error "Training failed for: $($Failed -join ', ')"
    exit 1
}

Write-Host ""
Write-Host "Training complete. Artifacts are under ai_ml/models/<model_name>/artifacts/."
Write-Host "Current artifacts include model_float32.keras, model_float32.tflite, and model_int8.tflite."
