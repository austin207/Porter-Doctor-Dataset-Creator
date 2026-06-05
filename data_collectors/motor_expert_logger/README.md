# Motor Expert Logger

Zephyr logger for real motor-response telemetry used to train the Motor Expert
for Porter Doctor / RoboMoE-Diag.

This firmware only logs telemetry and labels dataset runs. It does not run ML and
does not create unsafe motor faults.

## Purpose

Collect motor-side behaviour data for:

- healthy
- motor_stall
- excessive_load
- motor_disconnected
- abnormal_vibration
- bearing_degradation

## Inputs

- UART telemetry from the main motor controller
- Optional vibration sensor
- Optional left and right current sensors
- Optional future direct encoder GPIO module
- microSD card over SPI

This logger needs the main controller ESP32 when encoder, PWM, and RPM data are
not directly wired to the logger MCU.

## UART Telemetry

Line format:

```text
TEL,pwm_left,pwm_right,rpm_left,rpm_right,encoder_left,encoder_right,current_left,current_right
```

Telemetry is marked invalid if no fresh line arrives within 500 ms.

## Dataset Columns

```csv
timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity,pwm_left,pwm_right,rpm_left,rpm_right,encoder_count_left,encoder_count_right,current_left_a,current_right_a,vibration_rms,vibration_peak,motor_temp_left_c,motor_temp_right_c,telemetry_valid,telemetry_age_ms
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
datasets/motor_expert/raw/<run_id>.csv
datasets/motor_expert/events/<run_id>_events.csv
datasets/motor_expert/metadata/<run_id>.txt
```

## Build

From the Zephyr workspace root:

```powershell
west build -b esp32_devkitc/esp32/procpu data_collectors/motor_expert_logger -d build/motor_expert_logger
```

If your Zephyr board target name differs, use that board target and keep the app
overlay in `boards/`.

## Overlay Placeholders

The ESP32 overlay includes SD-card SPI wiring and commented aliases for:

- `motor-tel-uart`
- `vibration-sensor`
- `left-current-sensor`
- `right-current-sensor`

Enable those aliases only after final pin choices are known.

## Safe Collection Notes

- Collect healthy data first.
- Vary speed, payload, terrain, and battery level.
- Mark test events with `fault_on` and `fault_off`.
- Do not intentionally stall motors in a way that overheats or damages them.
- Do not create mechanical faults that can damage the robot.

