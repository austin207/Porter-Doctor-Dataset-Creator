# MoE Router Dataset Builder

## Context

This folder contains the Zephyr logger for one RoboMoE-Diag subsystem expert.
It collects real-world telemetry from Porter or the agri bot for ML training.
This is not synthetic data generation.

## Expert Purpose

Builds the routing dataset that decides which subsystem expert should be activated for each telemetry window.

## Sensors / Inputs

- Feature summaries from all expert datasets
- Expert anomaly scores
- Expert confidence outputs

## Initial Fault Labels

- route_to_power_expert
- route_to_motor_expert
- route_to_motor_driver_expert
- route_to_esp32_expert
- route_to_lighting_expert
- unknown_fault

## Common Dataset Columns

timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,fault_label,fault_subsystem,severity

## Expert Specific Columns

power_score,motor_score,driver_score,esp32_score,lighting_score,target_expert

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
  router_dataset_builder/
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
