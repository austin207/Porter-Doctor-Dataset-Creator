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

Build from the repository root:

```powershell
.\data_collectors\build_logger.ps1 -Expert power_expert_logger
```

Build and flash:

```powershell
.\data_collectors\build_logger.ps1 -Expert power_expert_logger -Flash
```

The firmware writes datasets to the SD card under `datasets/<expert_name>/`.
