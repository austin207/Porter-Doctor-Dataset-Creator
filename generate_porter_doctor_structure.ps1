# generate_porter_doctor_structure.ps1
# Clean ASCII-only PowerShell script for Porter Doctor.
# Run from the PORTER DOCTOR root folder:
# powershell -ExecutionPolicy Bypass -File .\generate_porter_doctor_structure.ps1

$ErrorActionPreference = "Stop"
$Root = Get-Location

function EnsureDir($p) {
    if (!(Test-Path $p)) {
        New-Item -ItemType Directory -Force -Path $p | Out-Null
    }
}

function WriteLines($path, $lines) {
    $dir = Split-Path $path -Parent
    if ($dir -and !(Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $lines | Set-Content -Path $path -Encoding UTF8
}

function MakeLogger($name, $title, $purpose, $boards, $sensors, $faults, $columns, $ina226) {
    $project = Join-Path $Root $name
    $src = Join-Path $project "src"
    $boarddir = Join-Path $project "boards"

    EnsureDir $project
    EnsureDir $src
    if ($boards.Count -gt 0) { EnsureDir $boarddir }

    WriteLines (Join-Path $project "CMakeLists.txt") @(
        "cmake_minimum_required(VERSION 3.20.0)",
        "",
        "find_package(Zephyr REQUIRED HINTS `$ENV{ZEPHYR_BASE})",
        "",
        "project($name)",
        "",
        "target_sources(app PRIVATE src/main.c)"
    )

    if ($name -ne "router_dataset_builder") {
        $conf = @(
            "# Zephyr config for $name",
            "",
            "CONFIG_SERIAL=y",
            "CONFIG_CONSOLE=y",
            "CONFIG_UART_CONSOLE=y",
            "CONFIG_LOG=y",
            "CONFIG_PRINTK=y",
            "",
            "CONFIG_GPIO=y",
            "CONFIG_I2C=y",
            "CONFIG_SPI=y",
            "CONFIG_ADC=y",
            "CONFIG_SENSOR=y",
            "",
            "CONFIG_DISK_ACCESS=y",
            "CONFIG_FILE_SYSTEM=y",
            "CONFIG_FAT_FILESYSTEM_ELM=y",
            "CONFIG_FS_FATFS=y",
            "CONFIG_SDMMC_STACK=y",
            "",
            "CONFIG_MAIN_STACK_SIZE=4096",
            "CONFIG_HEAP_MEM_POOL_SIZE=8192",
            "",
            "CONFIG_NEWLIB_LIBC=y",
            "CONFIG_MINIMAL_LIBC=n"
        )
        if ($ina226) {
            $conf += ""
            $conf += "CONFIG_INA226=y"
        }
        WriteLines (Join-Path $project "prj.conf") $conf

        WriteLines (Join-Path $src "main.c") @(
            "#include <zephyr/kernel.h>",
            "#include <zephyr/sys/printk.h>",
            "",
            "int main(void)",
            "{",
            "    printk(""========================================\n"");",
            "    printk(""$title\n"");",
            "    printk(""========================================\n"");",
            "    printk(""$purpose\n"");",
            "    printk(""Skeleton generated.\n"");",
            "",
            "    while (1) {",
            "        k_sleep(K_SECONDS(1));",
            "    }",
            "",
            "    return 0;",
            "}"
        )
    }

    foreach ($b in $boards) {
        $overlayPath = Join-Path $boarddir $b

        if (($name -eq "power_expert_logger") -and ($b -eq "esp32_devkitc_wroom.overlay")) {
            WriteLines $overlayPath @(
                "/* ESP32 DevKitC WROOM overlay for Power Expert Logger */",
                "/* INA226: VCC->3V3, GND->GND, SDA->GPIO21, SCL->GPIO22 */",
                "/* INA226 path: Battery+ -> IN+, IN- -> MotorDriver VIN+ */",
                "/* SD: SCK GPIO18, MISO GPIO19, MOSI GPIO23, CS GPIO25 */",
                "",
                "&i2c0 {",
                "    status = ""okay"";",
                "    clock-frequency = <I2C_BITRATE_FAST>;",
                "",
                "    ina226@40 {",
                "        compatible = ""ti,ina226"";",
                "        reg = <0x40>;",
                "        shunt-resistor-micro-ohms = <100000>;",
                "    };",
                "};",
                "",
                "&spi2 {",
                "    status = ""okay"";",
                "    cs-gpios = <&gpio0 25 GPIO_ACTIVE_LOW>;",
                "",
                "    sdhc0: sdhc@0 {",
                "        compatible = ""zephyr,sdhc-spi-slot"";",
                "        reg = <0>;",
                "        status = ""okay"";",
                "        spi-max-frequency = <24000000>;",
                "    };",
                "};",
                "",
                "/ {",
                "    aliases {",
                "        power-sensor = &{/soc/i2c@0/ina226@40};",
                "    };",
                "};"
            )
        } elseif (($name -eq "power_expert_logger") -and ($b -eq "nucleo_f401re.overlay")) {
            WriteLines $overlayPath @(
                "/* STM32 Nucleo F401RE overlay placeholder. */",
                "/* Fill I2C, SPI and SD card nodes after STM32 pin selection. */",
                "",
                "/ {",
                "    aliases {",
                "        /* power-sensor = &ina226; */",
                "    };",
                "};"
            )
        } else {
            WriteLines $overlayPath @(
                "/* Board overlay placeholder for $title. */",
                "/* Add final pin mapping after hardware is selected. */"
            )
        }
    }

    $folderName = $name.Replace("_logger", "")

    $readme = @()
    $readme += "# $title"
    $readme += ""
    $readme += "## Context"
    $readme += ""
    $readme += "This folder contains the Zephyr logger for one RoboMoE-Diag subsystem expert."
    $readme += "It collects real-world telemetry from Porter or the agri bot for ML training."
    $readme += "This is not synthetic data generation."
    $readme += ""
    $readme += "## Expert Purpose"
    $readme += ""
    $readme += "$purpose"
    $readme += ""
    $readme += "## Sensors / Inputs"
    $readme += ""
    foreach ($s in $sensors) { $readme += "- $s" }
    $readme += ""
    $readme += "## Initial Fault Labels"
    $readme += ""
    foreach ($f in $faults) { $readme += "- $f" }
    $readme += ""
    $readme += "## Common Dataset Columns"
    $readme += ""
    $readme += "timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity"
    $readme += ""
    $readme += "## Expert Specific Columns"
    $readme += ""
    $readme += ($columns -join ",")
    $readme += ""
    $readme += "## Serial Labelling Commands"
    $readme += ""
    $readme += "start <run_id> <fault_label> <severity>"
    $readme += "fault_on"
    $readme += "fault_off"
    $readme += "stop"
    $readme += "status"
    $readme += ""
    $readme += "## Example"
    $readme += ""
    $readme += "start healthy_run_001 healthy 0"
    $readme += "stop"
    $readme += ""
    $readme += "start fault_run_001 fault_label_here 2"
    $readme += "fault_on"
    $readme += "fault_off"
    $readme += "stop"
    $readme += ""
    $readme += "## Dataset Output Structure"
    $readme += ""
    $readme += "datasets/"
    $readme += "  $folderName/"
    $readme += "    raw/"
    $readme += "    events/"
    $readme += "    metadata/"
    $readme += "    features/"
    $readme += ""
    $readme += "## Rules"
    $readme += ""
    $readme += "1. Collect healthy data first."
    $readme += "2. Vary speed, payload, terrain and battery level."
    $readme += "3. Mark fault start and end clearly."
    $readme += "4. Split train/test by full run ID, not random rows."
    $readme += "5. Do not create unsafe faults."

    WriteLines (Join-Path $project "README.md") $readme
}

MakeLogger "power_expert_logger" "Power Expert Logger" "Collects real battery, current, power and regulator telemetry for power-system fault detection." @("esp32_devkitc_wroom.overlay","nucleo_f401re.overlay") @("INA226 battery voltage/current sensor","microSD card logger","Optional 5V and 3.3V rail monitoring") @("healthy","battery_voltage_sag","battery_undervoltage","loose_power_connection","regulator_instability","excessive_system_load") @("battery_voltage_v","battery_current_a","battery_power_w","rail_5v_v","rail_3v3_v") $true

MakeLogger "motor_expert_logger" "Motor Expert Logger" "Collects motor response telemetry for motor-side fault detection." @("esp32_devkit.overlay") @("Encoder or RPM feedback","Motor current sensor","Optional vibration IMU","microSD card logger") @("healthy","motor_stall","excessive_load","motor_disconnected","abnormal_vibration","bearing_degradation") @("pwm_left","pwm_right","rpm_left","rpm_right","current_left_a","current_right_a","vibration_rms") $false

MakeLogger "motor_driver_expert_logger" "Motor Driver Expert Logger" "Collects motor-driver telemetry for driver-stage fault detection." @("esp32_devkit.overlay") @("Motor driver fault pin","Driver temperature sensor","Motor current sensor","PWM command telemetry","microSD card logger") @("healthy","driver_overcurrent","driver_overtemperature","driver_disabled","driver_fault_pin_active","undervoltage_lockout") @("pwm_left","pwm_right","driver_temp_left_c","driver_temp_right_c","driver_fault_left","driver_fault_right","current_left_a","current_right_a") $false

MakeLogger "esp32_expert_logger" "ESP32 Expert Logger" "Collects controller health telemetry for ESP32 reset, heartbeat and communication fault detection." @("esp32_devkit.overlay") @("UART heartbeat telemetry","Reset reason telemetry","Packet counters","Task timing logs","microSD card logger") @("healthy","heartbeat_lost","packet_loss","watchdog_reset","brownout_reset","task_overrun","firmware_freeze") @("heartbeat_interval_ms","reset_reason","watchdog_count","packet_error_count","task_loop_time_ms") $false

MakeLogger "lighting_expert_logger" "Lighting Expert Logger" "Collects lighting-system telemetry for LED, driver and brightness mismatch fault detection." @("esp32_devkit.overlay") @("Light current sensor","Light voltage sensor","Optional light intensity sensor","Brightness command telemetry","microSD card logger") @("healthy","led_disconnected","brightness_mismatch","light_driver_fault","lighting_overcurrent","lighting_short_suspected") @("brightness_command","light_current_a","light_voltage_v","light_sensor_lux","light_driver_temp_c") $false

MakeLogger "router_dataset_builder" "MoE Router Dataset Builder" "Builds the routing dataset that decides which subsystem expert should be activated for each telemetry window." @() @("Feature summaries from all expert datasets","Expert anomaly scores","Expert confidence outputs") @("route_to_power_expert","route_to_motor_expert","route_to_motor_driver_expert","route_to_esp32_expert","route_to_lighting_expert","unknown_fault") @("power_score","motor_score","driver_score","esp32_score","lighting_score","target_expert") $false

WriteLines (Join-Path $Root "README.md") @(
    "# Porter Doctor",
    "",
    "Porter Doctor is the dataset-generation and embedded fault-diagnosis workspace for RoboMoE-Diag.",
    "",
    "## Goal",
    "",
    "Build a modular robot fault diagnosis system using multiple expert datasets and expert models.",
    "",
    "## Expert Folders",
    "",
    "PORTER DOCTOR/",
    "  power_expert_logger/",
    "  motor_expert_logger/",
    "  motor_driver_expert_logger/",
    "  esp32_expert_logger/",
    "  lighting_expert_logger/",
    "  router_dataset_builder/",
    "",
    "## Recommended Build Order",
    "",
    "1. power_expert_logger",
    "2. motor_expert_logger",
    "3. motor_driver_expert_logger",
    "4. esp32_expert_logger",
    "5. lighting_expert_logger",
    "6. router_dataset_builder",
    "",
    "Start with the Power Expert because it only needs ESP32, INA226 and microSD."
)

Write-Host ""
Write-Host "Porter Doctor structure generated successfully." -ForegroundColor Green
Write-Host ""
