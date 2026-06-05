# ESP32 Expert Logger

## Context

This folder contains the Zephyr logger for one RoboMoE-Diag subsystem expert.
It collects real-world telemetry from Porter or the agri bot for ML training.
This is not synthetic data generation.

## Expert Purpose

Collects controller health telemetry for ESP32 reset, heartbeat and communication fault detection.

## Sensors / Inputs

- UART heartbeat telemetry
- Reset reason telemetry
- Packet counters
- Task timing logs
- microSD card logger

## Initial Fault Labels

- healthy
- heartbeat_lost
- packet_loss
- watchdog_reset
- brownout_reset
- task_overrun
- firmware_freeze

## Common Dataset Columns

timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity

## Expert Specific Columns

heartbeat_interval_ms,reset_reason,watchdog_count,packet_error_count,task_loop_time_ms

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

## Dataset Output Structure

datasets/
  esp32_expert/
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
