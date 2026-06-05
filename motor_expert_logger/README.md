# Motor Expert Logger

## Context

This folder contains the Zephyr logger for one RoboMoE-Diag subsystem expert.
It collects real-world telemetry from Porter or the agri bot for ML training.
This is not synthetic data generation.

## Expert Purpose

Collects motor response telemetry for motor-side fault detection.

## Sensors / Inputs

- Encoder or RPM feedback
- Motor current sensor
- Optional vibration IMU
- microSD card logger

## Initial Fault Labels

- healthy
- motor_stall
- excessive_load
- motor_disconnected
- abnormal_vibration
- bearing_degradation

## Common Dataset Columns

timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity

## Expert Specific Columns

pwm_left,pwm_right,rpm_left,rpm_right,current_left_a,current_right_a,vibration_rms

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
  motor_expert/
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
