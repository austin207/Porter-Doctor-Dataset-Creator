# Power Expert Logger

## Context

This folder contains the Zephyr logger for one RoboMoE-Diag subsystem expert.
It collects real-world telemetry from Porter or the agri bot for ML training.
This is not synthetic data generation.

## Expert Purpose

Collects real battery, current, power and regulator telemetry for power-system fault detection.

## Sensors / Inputs

- INA226 battery voltage/current sensor
- microSD card logger
- Optional 5V and 3.3V rail monitoring

## Initial Fault Labels

- healthy
- battery_voltage_sag
- battery_undervoltage
- loose_power_connection
- regulator_instability
- excessive_system_load

## Common Dataset Columns

timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity

## Expert Specific Columns

battery_voltage_v,battery_current_a,battery_power_w,rail_5v_v,rail_3v3_v

## Serial Labelling Commands

start <run_id> <fault_label> <severity>
fault_on
fault_off
stop
status

## Example

start healthy_run_001 healthy 0
stop

start fault_run_001 fault_label_here 2
fault_on
fault_off
stop

## ESP32 DevKitC WROOM Build

From a Zephyr workspace, build this app with:

```powershell
west build -b esp32_devkitc/esp32/procpu data_collectors/power_expert_logger -d build/power_expert_logger
```

If your Zephyr version uses a qualified ESP32 board target, use the matching
board name but keep this app overlay:

```powershell
west build -b <your_esp32_board_target> power_expert_logger -d build/power_expert_logger
```

The default ESP32 overlay uses:

- I2C SDA GPIO21, SCL GPIO22
- SPI SCK GPIO18, MISO GPIO19, MOSI GPIO23, CS GPIO25
- INA226 I2C address `0x40`
- INA226 shunt resistor `100000` micro-ohms

Update `hardware_config.json` if your INA226 module has a different shunt
marking:

- `R100`: `100000` micro-ohms
- `R010`: `10000` micro-ohms
- `R005`: `5000` micro-ohms

The build generates `boards/generated.overlay` from `hardware_config.json`.
Do not edit the generated overlay directly.

## Runtime Output

Each `start` command creates:

- `datasets/power_expert/raw/<run_id>.csv`
- `datasets/power_expert/events/<run_id>_events.csv`
- `datasets/power_expert/metadata/<run_id>.txt`

Raw CSV columns:

```csv
timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity,battery_voltage_v,battery_current_a,battery_power_w
```

Event CSV columns:

```csv
timestamp_ms,elapsed_s,event,fault_active,fault_label,severity
```

## Dataset Output Structure

datasets/
  power_expert/
    raw/
    events/
    metadata/
    features/

## Rules

1. Collect healthy data first.
2. Vary speed, payload, terrain and battery level.
3. Mark fault start and end clearly.
4. Split train/test by full run ID, not random rows.
5. Do not create unsafe faults.

