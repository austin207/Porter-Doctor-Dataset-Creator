# Lighting Expert Logger

Zephyr logger for lighting-system telemetry used to train the Lighting Expert
for Porter Doctor / RoboMoE-Diag.

This firmware only logs telemetry and labels dataset runs. It does not create
unsafe lighting faults.

## Purpose

Collect lighting data for:

- healthy
- led_disconnected
- brightness_mismatch
- light_driver_fault
- lighting_overcurrent
- lighting_short_suspected

## Inputs

- UART telemetry from a lighting controller or main controller
- Optional current or voltage sensor
- Optional light intensity sensor
- Optional lighting driver fault GPIO
- microSD card over SPI

## UART Telemetry

Line format:

```text
LGT,brightness_command,light_current,light_voltage,light_sensor_lux,light_driver_temp
```

Telemetry is marked invalid if no fresh line arrives within 500 ms.

## Dataset Columns

```csv
timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity,brightness_command,light_current_a,light_voltage_v,light_sensor_lux,light_driver_temp_c,light_fault_gpio,telemetry_valid,telemetry_age_ms
```

Optional sensors that are not configured are logged as `-1`.

## Serial Commands

```text
start <run_id> <fault_label> <severity>
fault_on
fault_off
stop
status
```

## Output Files

```text
datasets/lighting_expert/raw/<run_id>.csv
datasets/lighting_expert/events/<run_id>_events.csv
datasets/lighting_expert/metadata/<run_id>.txt
```

## Build

From the Zephyr workspace root:

```powershell
west build -b esp32_devkitc/esp32/procpu data_collectors/lighting_expert_logger -d build/lighting_expert_logger
```

## Overlay Placeholders

The ESP32 overlay includes SD-card SPI wiring and commented aliases for:

- `light-current-sensor`
- `light-voltage-adc`
- `light-sensor`
- `light-driver-temp-adc`
- `light-fault-gpio`
- `lighting-tel-uart`

Enable those aliases only after final safe pin choices are known.

## Future Model Architecture

This logger feeds the future Lighting Expert model. Firmware inference is not
implemented here yet.

Initial feature windows should include brightness command mean/max, light
current mean/peak/std, light voltage mean/min/std, lux mean/std, brightness-lux
error, current-to-brightness ratio, voltage-current ratio, driver temperature
mean and rise rate, light fault GPIO ratio, and telemetry valid ratio.

Recommended embedded model:

```text
Input: 16 to 20 window features
Dense 16, ReLU
Dense 8, ReLU
Fault head: 6 classes
Action head: 7 bounded actions
```

Expected action mapping starts with:

```text
healthy -> ACTION_NONE
led_disconnected -> ACTION_WARN_OPERATOR
brightness_mismatch -> ACTION_WARN_OPERATOR
light_driver_fault -> ACTION_CONTROLLED_STOP or ACTION_ENTER_SAFE_STATE
lighting_overcurrent -> ACTION_ENTER_SAFE_STATE
lighting_short_suspected -> ACTION_ENTER_SAFE_STATE
```

## Safe Collection Notes

- Disconnect LEDs only when powered off.
- Use a safe dummy load.
- Simulate brightness mismatch in firmware first.
- Do not short LED driver outputs.

