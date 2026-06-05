# Data Collectors

Zephyr firmware and hardware configuration for Porter Doctor dataset loggers.

This folder contains:

```text
hardware_config.json
build_logger.ps1
common/
scripts/
power_expert_logger/
motor_expert_logger/
motor_driver_expert_logger/
esp32_expert_logger/
lighting_expert_logger/
```

Edit `hardware_config.json` to change board targets, ESP32 pins, SD wiring,
I2C wiring, UART telemetry links, and GPIO aliases.

## Prerequisites

Same as the inference smoke app — see `zephyr_inference/README.md` for the
full list. In particular, the Windows one-time setup (copying ROM linker
scripts to `C:\zld\`) must be done before any logger build.

## Building

Use `build_logger.ps1` from the repository root. Builds are written to
`C:\b\<expert>` to avoid the `(` in the project path breaking the Ninja
linker command line on Windows.

```powershell
.\data_collectors\build_logger.ps1 -Expert power_expert_logger
```

Build and flash:

```powershell
.\data_collectors\build_logger.ps1 -Expert power_expert_logger -Flash
```

Valid `-Expert` values:

```text
power_expert_logger
motor_expert_logger
motor_driver_expert_logger
esp32_expert_logger
lighting_expert_logger
```

To build manually with `west` (e.g. to pass extra CMake flags):

```powershell
west build -b esp32_devkitc/esp32/procpu data_collectors/power_expert_logger -d C:\b\power_expert_logger
west flash -d C:\b\power_expert_logger
```

## Hardware wiring

The active board and all peripheral pins are configured in `hardware_config.json`.
The `generate_zephyr_overlay.py` script reads that file at CMake configure time
and writes `boards/generated.overlay` for each logger app.

The firmware writes datasets to the SD card under `datasets/<expert_name>/`.
