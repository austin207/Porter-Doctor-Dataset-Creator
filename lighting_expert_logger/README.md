# Lighting Expert Logger

## Context

This folder contains the Zephyr logger for one RoboMoE-Diag subsystem expert.
It collects real-world telemetry from Porter or the agri bot for ML training.
This is not synthetic data generation.

## Expert Purpose

Collects lighting-system telemetry for LED, driver and brightness mismatch fault detection.

## Sensors / Inputs

- Light current sensor
- Light voltage sensor
- Optional light intensity sensor
- Brightness command telemetry
- microSD card logger

## Initial Fault Labels

- healthy
- led_disconnected
- brightness_mismatch
- light_driver_fault
- lighting_overcurrent
- lighting_short_suspected

## Common Dataset Columns

timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity

## Expert Specific Columns

brightness_command,light_current_a,light_voltage_v,light_sensor_lux,light_driver_temp_c

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
  lighting_expert/
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
