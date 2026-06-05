# RoboMoE-Diag Model Architecture

This document is the current model architecture plan for Porter Doctor /
RoboMoE-Diag.

Do not treat this as embedded inference implementation. It defines dataset
features, training targets, export artifacts, and future deployment constraints.

## Embedded Target

Primary target:

```text
ESP32-S3 fault detector
```

Future target:

```text
STM32 through Zephyr portability
```

Preferred deployment format:

```text
INT8 quantized model
TFLite Micro / LiteRT Micro style deployment
ESP-DL may be evaluated for ESP32-S3
```

Targets:

```text
Router: less than 10k parameters
Each expert: 2k to 20k parameters
Total embedded ML: preferably less than 100k parameters
Inference: less than 50 ms for router plus top-2 experts
```

## Input Style

Embedded models use sliding-window features, not long raw telemetry sequences.

Initial window:

```text
Window duration: 1 second
Overlap: 50 percent
Raw logging rate: 20 Hz to 100 Hz depending on signal
```

Common features:

```text
mean
min
max
standard deviation
peak
change rate
command-response difference
heartbeat interval
stale telemetry indicator
left-right mismatch
voltage/current/temperature rise rate
```

## Shared Outputs

Every expert should eventually produce:

```c
typedef struct {
    uint8_t fault_id;
    float fault_confidence;
    uint8_t subsystem_id;
    uint8_t requested_action;
    float action_confidence;
    float anomaly_score;
} expert_output_t;
```

Training targets:

```text
fault_id
fault_label
fault_subsystem
recommended_action
```

Action enum:

```c
typedef enum {
    ACTION_NONE = 0,
    ACTION_LOG_ONLY = 1,
    ACTION_WARN_OPERATOR = 2,
    ACTION_LIMIT_SPEED = 3,
    ACTION_CONTROLLED_STOP = 4,
    ACTION_ENTER_SAFE_STATE = 5,
    ACTION_REQUEST_ESTOP = 6
} fault_action_t;
```

Safety rule:

```text
ML may request ACTION_REQUEST_ESTOP.
Deterministic supervisor must authorize actual emergency stop.
```

## Shared Expert Pattern

Default embedded expert:

```text
Input feature vector
    -> Dense 32
    -> ReLU
    -> Dropout 0.05 during training only where useful
    -> Dense 16
    -> ReLU
    -> Fault classification head
    -> Action recommendation head
    -> Optional anomaly/confidence head
```

Very small expert:

```text
Input feature vector
    -> Dense 16
    -> ReLU
    -> Dense 8
    -> ReLU
    -> Fault classification head
    -> Action recommendation head
```

Training loss:

```text
total_loss =
    fault_classification_loss
  + 0.3 * action_classification_loss
  + 0.2 * anomaly_binary_loss
```

Start simpler if needed:

```text
1. Fault classification only
2. Add action output
3. Add anomaly/unknown handling
```

## Power Expert

Fault labels:

```text
healthy
battery_voltage_sag
battery_undervoltage
loose_power_connection
regulator_instability
excessive_system_load
```

Feature vector:

```text
battery_voltage_mean
battery_voltage_min
battery_voltage_std
battery_voltage_drop
battery_current_mean
battery_current_peak
battery_current_std
battery_power_mean
battery_power_peak
rail_5v_mean
rail_5v_min
rail_5v_std
rail_3v3_mean
rail_3v3_min
rail_3v3_std
voltage_current_correlation
voltage_drop_rate
current_rise_rate
power_rise_rate
```

Architecture:

```text
Input: 18 to 24 features
Dense 32 -> ReLU
Dropout 0.05 during training only
Dense 16 -> ReLU
Fault head: Dense 6 -> Softmax
Action head: Dense 7 -> Softmax
```

Expected actions:

```text
healthy -> ACTION_NONE
battery_voltage_sag -> ACTION_LIMIT_SPEED or ACTION_CONTROLLED_STOP
battery_undervoltage -> ACTION_ENTER_SAFE_STATE
loose_power_connection -> ACTION_ENTER_SAFE_STATE
regulator_instability -> ACTION_CONTROLLED_STOP
excessive_system_load -> ACTION_LIMIT_SPEED
```

## Motor Expert

Fault labels:

```text
healthy
motor_stall
excessive_load
motor_disconnected
abnormal_vibration
bearing_degradation
```

Feature vector:

```text
pwm_left_mean
pwm_right_mean
rpm_left_mean
rpm_right_mean
rpm_left_std
rpm_right_std
rpm_error_left_mean
rpm_error_right_mean
rpm_error_left_peak
rpm_error_right_peak
encoder_delta_left_mean
encoder_delta_right_mean
current_left_mean
current_right_mean
current_left_peak
current_right_peak
left_right_rpm_difference
left_right_current_difference
vibration_rms_mean
vibration_peak_max
vibration_variance
motor_temp_left_mean
motor_temp_right_mean
motor_temp_rise_rate
telemetry_valid_ratio
```

Architecture:

```text
Input: 24 to 32 features
Dense 32 -> ReLU
Dense 16 -> ReLU
Fault head: Dense 6 -> Softmax
Action head: Dense 7 -> Softmax
```

Do not implement raw vibration CNN first. Start with feature-based MLP.

## Motor Driver Expert

Fault labels:

```text
healthy
driver_overcurrent
driver_overtemperature
driver_disabled
driver_fault_pin_active
undervoltage_lockout
```

Feature vector:

```text
pwm_left_mean
pwm_right_mean
driver_temp_left_mean
driver_temp_right_mean
driver_temp_left_max
driver_temp_right_max
driver_temp_left_rise_rate
driver_temp_right_rise_rate
driver_fault_left_ratio
driver_fault_right_ratio
driver_enable_left_ratio
driver_enable_right_ratio
current_left_mean
current_right_mean
current_left_peak
current_right_peak
battery_voltage_mean
battery_voltage_min
battery_voltage_drop
current_to_pwm_ratio_left
current_to_pwm_ratio_right
fault_pin_transition_count
telemetry_valid_ratio
```

Architecture:

```text
Input: 20 to 28 features
Dense 32 -> ReLU
Dense 16 -> ReLU
Fault head: Dense 6 -> Softmax
Action head: Dense 7 -> Softmax
```

ML may request emergency stop for overcurrent, but deterministic current
thresholds or driver fault pin rules must authorize actual emergency stop.

## ESP32 Expert

Feature vector:

```text
heartbeat_interval_mean
heartbeat_interval_max
heartbeat_interval_std
heartbeat_missed_count
reset_reason_encoded
watchdog_count_delta
packet_error_count_delta
packet_error_rate
task_loop_time_mean
task_loop_time_max
task_loop_time_std
control_loop_jitter_mean
control_loop_jitter_max
uart_rx_error_delta
telemetry_age_mean
telemetry_age_max
telemetry_valid_ratio
stale_window_flag
```

Architecture:

```text
Input: 16 to 24 features
Dense 24 -> ReLU
Dense 12 -> ReLU
Fault head: Dense 7 -> Softmax
Action head: Dense 7 -> Softmax
```

## Lighting Expert

Feature vector:

```text
brightness_command_mean
brightness_command_max
light_current_mean
light_current_peak
light_current_std
light_voltage_mean
light_voltage_min
light_voltage_std
light_sensor_lux_mean
light_sensor_lux_std
brightness_lux_error
current_to_brightness_ratio
voltage_current_ratio
light_driver_temp_mean
light_driver_temp_rise_rate
light_fault_gpio_ratio
telemetry_valid_ratio
```

Architecture:

```text
Input: 16 to 20 features
Dense 16 -> ReLU
Dense 8 -> ReLU
Fault head: Dense 6 -> Softmax
Action head: Dense 7 -> Softmax
```

## Always-On Anomaly Detector

Input:

```text
3 to 5 summary features per subsystem
20 to 30 combined health features total
```

Architecture:

```text
Input combined health vector
Encoder: Dense 16 -> ReLU
Encoder: Dense 8 -> ReLU
Decoder: Dense 16 -> ReLU
Decoder: Dense input_dim -> Linear
Output: reconstruction_error
```

Unknown condition:

```text
reconstruction_error > threshold
AND
max_expert_confidence < confidence_threshold
```

Initial threshold:

```text
general_anomaly_score > 0.80
max_expert_confidence < 0.55
```

## MoE Router

Router labels:

```text
power_expert
motor_expert
motor_driver_expert
esp32_expert
lighting_expert
unknown_fault
```

Feature vector:

```text
power_voltage_drop
power_current_peak
power_regulator_instability_score
motor_rpm_error_peak
motor_vibration_score
motor_current_response_score
driver_temp_rise_rate
driver_fault_pin_ratio
driver_current_to_pwm_score
esp32_heartbeat_age
esp32_packet_error_rate
esp32_task_timing_score
lighting_brightness_error
lighting_current_peak
lighting_fault_pin_ratio
telemetry_valid_ratio
operating_mode_encoded
```

Architecture:

```text
Input: 16 to 24 features
Dense 32 -> ReLU
Dense 16 -> ReLU
Dense 6 -> Softmax
```

Routing rule:

```text
Activate top-2 experts by default.
Activate top-3 experts when:
    max_router_probability < 0.65
    OR general anomaly score is high
    OR safety supervisor marks situation as risky
```

Do not use top-1 routing for real robot faults.

Router output:

```c
typedef struct {
    float expert_prob[6];
    uint8_t top_expert_1;
    uint8_t top_expert_2;
    uint8_t top_expert_3;
} router_output_t;
```

## Fault Aggregator

Use a rule-based aggregator first. Do not start with a learned aggregator.

Inputs:

```text
router probabilities
top expert outputs
general anomaly score
safety rule flags
telemetry validity
```

Rules:

```text
If hard safety rule is active:
    safety rule decides action.
    ML diagnosis is explanation only.

If anomaly high and all expert confidences low:
    fault_status = unknown_fault

If two experts agree on related fault:
    increase confidence slightly.

If telemetry invalid:
    reduce confidence and report telemetry issue.

If primary expert confidence below threshold:
    report uncertain diagnosis and log event.
```

## Raspberry Pi Log Analyzer

Runs on Pi, Jetson, or laptop. Not ESP32.

Inputs:

```text
30 seconds before fault
10 seconds after fault
all telemetry signals
router output
expert outputs
safety action
human notes
maintenance outcome
```

Initial architecture:

```text
Conv1D 16, kernel 5
ReLU
MaxPool
Conv1D 32, kernel 3
ReLU
GlobalAveragePooling
Dense 32
Output: event_embedding_32
```

Similarity search:

```text
Store event embeddings.
Find top-5 nearest historical events for a new unknown fault.
```

Root-cause ranker:

```text
event_embedding_32 + summary_features
    -> root cause probabilities
```

## Training Pipeline Requirements

Every expert should eventually have:

```text
build_features.py
train_model.py
evaluate_model.py
export_tflite_int8.py
```

Required behavior:

```text
Read raw CSV logs.
Use event markers to assign labels.
Build sliding-window features.
Split by run_id, not random rows.
Train compact TensorFlow/Keras MLP for embedded deployment.
Optionally train Random Forest or XGBoost only as comparison models.
Evaluate confusion matrix.
Export INT8 quantized model.
Save feature ordering JSON.
Save label mapping JSON.
```

Artifacts per model:

```text
model_float32.keras
model_float32.tflite
model_int8.tflite
feature_order.json
action_map.json
label_map.json
normalization_stats.json
evaluation_report.md
confusion_matrix.csv
```
