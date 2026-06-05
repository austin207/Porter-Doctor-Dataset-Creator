# Motor Driver Expert Logger

Zephyr logger for real motor-driver telemetry used to train the Motor Driver
Expert for Porter Doctor / RoboMoE-Diag.

This firmware only logs telemetry and labels dataset runs. It does not run ML and
does not control emergency stop.

## Purpose

Collect driver-stage data for:

- healthy
- driver_overcurrent
- driver_overtemperature
- driver_disabled
- driver_fault_pin_active
- undervoltage_lockout

## Inputs

- Driver fault GPIO pins
- Optional driver enable GPIO pins
- Optional driver temperature ADC or sensor inputs
- UART telemetry from the main controller
- microSD card over SPI

## UART Telemetry

Line format:

```text
DRV,pwm_left,pwm_right,current_left,current_right,battery_voltage
```

Telemetry is marked invalid if no fresh line arrives within 500 ms.

## Dataset Columns

```csv
timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity,pwm_left,pwm_right,driver_temp_left_c,driver_temp_right_c,driver_fault_left,driver_fault_right,driver_enable_left,driver_enable_right,current_left_a,current_right_a,battery_voltage_v,telemetry_valid,telemetry_age_ms
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
datasets/motor_driver_expert/raw/<run_id>.csv
datasets/motor_driver_expert/events/<run_id>_events.csv
datasets/motor_driver_expert/metadata/<run_id>.txt
```

## Build

From the Zephyr workspace root:

```powershell
west build -b esp32_devkitc/esp32/procpu data_collectors/motor_driver_expert_logger -d build/motor_driver_expert_logger
```

## Overlay Placeholders

The ESP32 overlay includes SD-card SPI wiring and commented aliases for:

- `driver-fault-left-gpio`
- `driver-fault-right-gpio`
- `driver-enable-left-gpio`
- `driver-enable-right-gpio`
- `driver-temp-left-adc`
- `driver-temp-right-adc`
- `driver-tel-uart`

Enable those aliases only after final safe pin choices are known.

## Safe Collection Notes

- Do not short motor phases.
- Do not intentionally destroy MOSFETs.
- Do not exceed the rated driver temperature.
- Use safe software-emulated driver faults first.
- Use current-limited bench supplies when testing driver fault cases.

