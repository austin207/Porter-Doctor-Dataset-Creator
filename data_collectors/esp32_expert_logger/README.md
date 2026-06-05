# ESP32 Expert Logger

Zephyr logger for main-controller health telemetry used to train the ESP32
Expert for Porter Doctor / RoboMoE-Diag.

This firmware only logs telemetry and labels dataset runs. It does not reset or
control the main ESP32.

## Purpose

Collect controller health data for:

- healthy
- heartbeat_lost
- packet_loss
- watchdog_reset
- brownout_reset
- task_overrun
- firmware_freeze

## Inputs

- UART health telemetry from the main controller ESP32
- microSD card over SPI

## UART Telemetry

Line format:

```text
ESP,heartbeat_counter,reset_reason,watchdog_count,packet_error_count,task_loop_time_ms,control_loop_jitter_ms
```

The logger calculates `heartbeat_interval_ms` from receive timestamps.
Telemetry is marked invalid if no fresh line arrives within 500 ms.

## Dataset Columns

```csv
timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity,heartbeat_counter,heartbeat_interval_ms,reset_reason,watchdog_count,packet_error_count,task_loop_time_ms,control_loop_jitter_ms,uart_rx_errors,telemetry_valid,telemetry_age_ms
```

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
datasets/esp32_expert/raw/<run_id>.csv
datasets/esp32_expert/events/<run_id>_events.csv
datasets/esp32_expert/metadata/<run_id>.txt
```

## Build

From the Zephyr workspace root:

```powershell
west build -b esp32_devkitc/esp32/procpu data_collectors/esp32_expert_logger -d build/esp32_expert_logger
```

## Overlay Placeholder

The ESP32 overlay includes SD-card SPI wiring and a commented alias for:

- `esp32-health-uart`

Enable the alias only after final UART pins are known.

## Future Model Architecture

This logger feeds the future ESP32 Expert model. Firmware inference is not
implemented here yet.

Initial feature windows should include heartbeat interval mean/max/std, missed
heartbeat count, encoded reset reason, watchdog and packet-error deltas, packet
error rate, task loop timing mean/max/std, control-loop jitter mean/max, UART RX
error delta, telemetry age mean/max, telemetry valid ratio, and stale-window
flag.

Recommended embedded model:

```text
Input: 16 to 24 window features
Dense 24, ReLU
Dense 12, ReLU
Fault head: 7 classes
Action head: 7 bounded actions
```

Expected action mapping starts with:

```text
healthy -> ACTION_NONE
heartbeat_lost -> ACTION_ENTER_SAFE_STATE or ACTION_REQUEST_ESTOP
packet_loss -> ACTION_WARN_OPERATOR
watchdog_reset -> ACTION_ENTER_SAFE_STATE
brownout_reset -> ACTION_ENTER_SAFE_STATE
task_overrun -> ACTION_WARN_OPERATOR or ACTION_LIMIT_SPEED
firmware_freeze -> ACTION_ENTER_SAFE_STATE or ACTION_REQUEST_ESTOP
```

If main-controller heartbeat is lost while motors are enabled, deterministic
safety supervisor logic should stop the robot.

## Safe Fault Injection Examples

- Stop the heartbeat task in test firmware.
- Simulate packet loss.
- Send bad checksums from test firmware.
- Add artificial task delay.
- Trigger controlled software reset in test firmware only.

Do not use this logger to reset or control the main ESP32.

