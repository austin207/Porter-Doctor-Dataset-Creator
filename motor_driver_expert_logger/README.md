# Motor Driver Expert Logger

## Context

This folder contains the Zephyr logger for one RoboMoE-Diag subsystem expert.
It collects real-world telemetry from Porter or the agri bot for ML training.
This is not synthetic data generation.

## Expert Purpose

Collects motor-driver telemetry for driver-stage fault detection.

## Sensors / Inputs

- Motor driver fault pin
- Driver temperature sensor
- Motor current sensor
- PWM command telemetry
- microSD card logger

## Initial Fault Labels

- healthy
- driver_overcurrent
- driver_overtemperature
- driver_disabled
- driver_fault_pin_active
- undervoltage_lockout

## Common Dataset Columns

timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity

## Expert Specific Columns

pwm_left,pwm_right,driver_temp_left_c,driver_temp_right_c,driver_fault_left,driver_fault_right,current_left_a,current_right_a

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
  motor_driver_expert/
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
