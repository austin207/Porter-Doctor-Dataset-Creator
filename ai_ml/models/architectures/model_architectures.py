#!/usr/bin/env python3
"""Architecture specifications for RoboMoE-Diag models.

This module defines model shapes and feature contracts. It does not train or
run embedded inference.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List


ACTION_CLASSES = [
    "ACTION_NONE",
    "ACTION_LOG_ONLY",
    "ACTION_WARN_OPERATOR",
    "ACTION_LIMIT_SPEED",
    "ACTION_CONTROLLED_STOP",
    "ACTION_ENTER_SAFE_STATE",
    "ACTION_REQUEST_ESTOP",
]


@dataclass
class DenseLayer:
    units: int
    activation: str


@dataclass
class ModelArchitecture:
    name: str
    deployment_target: str
    model_family: str
    purpose: str
    input_features: List[str]
    output_classes: List[str]
    hidden_layers: List[DenseLayer] = field(default_factory=list)
    output_activation: str = "softmax"
    quantization: str = "int8_candidate"
    max_latency_ms: int = 50
    notes: List[str] = field(default_factory=list)

    @property
    def input_dim(self) -> int:
        return len(self.input_features)

    @property
    def output_dim(self) -> int:
        return len(self.output_classes)


def expert_mlp(
    name: str,
    purpose: str,
    features: List[str],
    classes: List[str],
    hidden_layers: List[DenseLayer] | None = None,
) -> ModelArchitecture:
    if hidden_layers is None:
        hidden_layers = [
            DenseLayer(32, "relu"),
            DenseLayer(16, "relu"),
        ]

    return ModelArchitecture(
        name=name,
        deployment_target="esp32_s3",
        model_family="small_mlp",
        purpose=purpose,
        input_features=features,
        hidden_layers=hidden_layers,
        output_classes=classes,
        output_activation="softmax",
        notes=[
            "Embedded target architecture is a compact MLP over sliding-window features.",
            "Training should include a fault head and action head; deployment may use fault logits plus an action lookup table.",
            "ML output may request bounded actions only; deterministic safety supervisor authorizes critical actions.",
        ],
    )


def architectures() -> Dict[str, ModelArchitecture]:
    return {
        "anomaly_detector": ModelArchitecture(
            name="anomaly_detector",
            deployment_target="esp32_s3",
            model_family="tiny_autoencoder",
            purpose="Always-on abnormal-behavior detector trained primarily on healthy telemetry windows.",
            input_features=[
                "rpm_error_left",
                "rpm_error_right",
                "rpm_mean_left",
                "rpm_mean_right",
                "current_mean_left",
                "current_mean_right",
                "current_peak_left",
                "current_peak_right",
                "voltage_mean",
                "voltage_minimum",
                "voltage_drop",
                "temperature_mean",
                "heartbeat_interval_ms",
                "packet_loss_rate",
                "telemetry_stale_ratio",
                "left_right_rpm_difference",
                "left_right_current_difference",
                "vibration_rms",
                "vibration_peak",
                "driver_fault_count",
            ],
            hidden_layers=[
                DenseLayer(16, "relu"),
                DenseLayer(8, "relu"),
                DenseLayer(16, "relu"),
            ],
            output_classes=["reconstruction_error"],
            output_activation="linear",
            notes=[
                "PRD allows small autoencoder or one-class model.",
                "Unknown fault rule starts as anomaly_score > 0.80 and max_expert_confidence < 0.55.",
                "For current baseline training code, IsolationForest is used until neural export is added.",
            ],
        ),
        "router": ModelArchitecture(
            name="moe_router",
            deployment_target="esp32_s3",
            model_family="small_mlp",
            purpose="Route each telemetry window to top-2 or top-3 subsystem experts.",
            input_features=[
                "power_voltage_drop",
                "power_current_peak",
                "power_regulator_instability_score",
                "motor_rpm_error_peak",
                "motor_vibration_score",
                "motor_current_response_score",
                "driver_temp_rise_rate",
                "driver_fault_pin_ratio",
                "driver_current_to_pwm_score",
                "esp32_heartbeat_age",
                "esp32_packet_error_rate",
                "esp32_task_timing_score",
                "lighting_brightness_error",
                "lighting_current_peak",
                "lighting_fault_pin_ratio",
                "telemetry_valid_ratio",
                "operating_mode_encoded",
            ],
            hidden_layers=[
                DenseLayer(32, "relu"),
                DenseLayer(16, "relu"),
            ],
            output_classes=[
                "power_expert",
                "motor_expert",
                "motor_driver_expert",
                "esp32_expert",
                "lighting_expert",
                "unknown_fault",
            ],
            output_activation="softmax",
            notes=[
                "Router chooses experts only; it does not make the final fault decision.",
                "Runtime must activate top-2 experts by default and top-3 when uncertainty or risk is high.",
                "Later versions can add encoder_expert and pi_expert routes after those datasets exist.",
            ],
        ),
        "power_expert": expert_mlp(
            "power_expert",
            "Diagnose battery, voltage sag, undervoltage, loose connection, regulator, and load faults.",
            [
                "battery_voltage_mean",
                "battery_voltage_min",
                "battery_voltage_std",
                "battery_voltage_drop",
                "battery_current_mean",
                "battery_current_peak",
                "battery_current_std",
                "battery_power_mean",
                "battery_power_peak",
                "rail_5v_mean",
                "rail_5v_min",
                "rail_5v_std",
                "rail_3v3_mean",
                "rail_3v3_min",
                "rail_3v3_std",
                "voltage_current_correlation",
                "voltage_drop_rate",
                "current_rise_rate",
                "power_rise_rate",
            ],
            [
                "healthy",
                "battery_voltage_sag",
                "battery_undervoltage",
                "loose_power_connection",
                "regulator_instability",
                "excessive_system_load",
            ],
        ),
        "motor_expert": expert_mlp(
            "motor_expert",
            "Diagnose mechanical motor-side faults from PWM, RPM, current, temperature, load, and vibration.",
            [
                "pwm_left_mean",
                "pwm_right_mean",
                "rpm_left_mean",
                "rpm_right_mean",
                "rpm_left_std",
                "rpm_right_std",
                "rpm_error_left_mean",
                "rpm_error_right_mean",
                "rpm_error_left_peak",
                "rpm_error_right_peak",
                "encoder_delta_left_mean",
                "encoder_delta_right_mean",
                "current_left_mean",
                "current_right_mean",
                "current_left_peak",
                "current_right_peak",
                "left_right_rpm_difference",
                "left_right_current_difference",
                "vibration_rms_mean",
                "vibration_peak_max",
                "vibration_variance",
                "motor_temp_left_mean",
                "motor_temp_right_mean",
                "motor_temp_rise_rate",
                "telemetry_valid_ratio",
            ],
            [
                "healthy",
                "motor_stall",
                "excessive_load",
                "motor_disconnected",
                "abnormal_vibration",
                "bearing_degradation",
            ],
        ),
        "motor_driver_expert": expert_mlp(
            "motor_driver_expert",
            "Diagnose motor-driver power stage, thermal, enable, and undervoltage faults.",
            [
                "pwm_left_mean",
                "pwm_right_mean",
                "driver_temp_left_mean",
                "driver_temp_right_mean",
                "driver_temp_left_max",
                "driver_temp_right_max",
                "driver_temp_left_rise_rate",
                "driver_temp_right_rise_rate",
                "driver_fault_left_ratio",
                "driver_fault_right_ratio",
                "driver_enable_left_ratio",
                "driver_enable_right_ratio",
                "current_left_mean",
                "current_right_mean",
                "current_left_peak",
                "current_right_peak",
                "battery_voltage_mean",
                "battery_voltage_min",
                "battery_voltage_drop",
                "current_to_pwm_ratio_left",
                "current_to_pwm_ratio_right",
                "fault_pin_transition_count",
                "telemetry_valid_ratio",
            ],
            [
                "healthy",
                "driver_overcurrent",
                "driver_overtemperature",
                "driver_disabled",
                "driver_fault_pin_active",
                "undervoltage_lockout",
            ],
        ),
        "esp32_expert": expert_mlp(
            "esp32_expert",
            "Diagnose main ESP32 firmware, reset, heartbeat, task timing, and communication faults.",
            [
                "heartbeat_interval_mean",
                "heartbeat_interval_max",
                "heartbeat_interval_std",
                "heartbeat_missed_count",
                "reset_reason_encoded",
                "watchdog_count_delta",
                "packet_error_count_delta",
                "packet_loss_rate",
                "task_loop_time_mean_ms",
                "task_loop_time_max_ms",
                "task_loop_time_std_ms",
                "control_loop_jitter_mean",
                "control_loop_jitter_max",
                "uart_rx_error_delta",
                "telemetry_age_mean",
                "telemetry_age_max",
                "telemetry_valid_ratio",
                "stale_window_flag",
            ],
            [
                "healthy",
                "heartbeat_lost",
                "packet_loss",
                "watchdog_reset",
                "brownout_reset",
                "task_overrun",
                "firmware_freeze",
            ],
            hidden_layers=[
                DenseLayer(24, "relu"),
                DenseLayer(12, "relu"),
            ],
        ),
        "encoder_expert": expert_mlp(
            "encoder_expert",
            "Diagnose encoder pulse, direction, signal-noise, and mismatch faults.",
            [
                "encoder_count_left_delta",
                "encoder_count_right_delta",
                "calculated_rpm_left",
                "calculated_rpm_right",
                "motor_current_left_mean",
                "motor_current_right_mean",
                "vibration_rms",
                "pwm_left_mean",
                "pwm_right_mean",
                "direction_command_left",
                "direction_command_right",
                "pulse_timing_variance_left",
                "pulse_timing_variance_right",
                "rpm_encoder_motor_mismatch_left",
                "rpm_encoder_motor_mismatch_right",
            ],
            [
                "healthy",
                "encoder_disconnected",
                "encoder_signal_noise",
                "incorrect_pulse_count",
                "direction_mismatch",
                "intermittent_encoder_failure",
            ],
        ),
        "lighting_expert": expert_mlp(
            "lighting_expert",
            "Diagnose LED, wiring, driver, short/open circuit, brightness mismatch, and thermal faults.",
            [
                "brightness_command_mean",
                "brightness_command_max",
                "light_current_mean",
                "light_current_peak",
                "light_current_std",
                "light_voltage_mean",
                "light_voltage_min",
                "light_voltage_std",
                "light_sensor_lux_mean",
                "light_sensor_lux_std",
                "brightness_lux_error",
                "current_to_brightness_ratio",
                "voltage_current_ratio",
                "light_driver_temp_mean",
                "light_driver_temp_rise_rate",
                "light_fault_gpio_ratio",
                "telemetry_valid_ratio",
            ],
            [
                "healthy",
                "led_disconnected",
                "brightness_mismatch",
                "light_driver_fault",
                "lighting_overcurrent",
                "lighting_short_suspected",
            ],
            hidden_layers=[
                DenseLayer(16, "relu"),
                DenseLayer(8, "relu"),
            ],
        ),
        "pi_expert": expert_mlp(
            "pi_expert",
            "Diagnose Raspberry Pi or Jetson health faults from heartbeat and system metrics.",
            [
                "pi_heartbeat_interval_ms",
                "pi_heartbeat_missed_count",
                "cpu_usage_mean",
                "cpu_usage_peak",
                "memory_usage_mean",
                "memory_usage_peak",
                "cpu_temperature_mean",
                "cpu_temperature_peak",
                "disk_usage",
                "main_process_alive",
                "ros_node_failure_count",
                "command_latency_ms",
            ],
            [
                "healthy",
                "pi_heartbeat_lost",
                "process_crash",
                "cpu_overload",
                "memory_exhaustion",
                "thermal_throttling",
                "ros_node_failure",
                "command_pipeline_delay",
            ],
        ),
        "unknown_fault_sequence_analyzer": ModelArchitecture(
            name="unknown_fault_sequence_analyzer",
            deployment_target="raspberry_pi_or_jetson",
            model_family="temporal_autoencoder_plus_clustering",
            purpose="Embed unknown-fault sequences for clustering, similarity search, and root-cause ranking.",
            input_features=[
                "pre_fault_30s_multisignal_sequence",
                "post_fault_10s_multisignal_sequence",
                "robot_operating_mode",
                "router_probabilities",
                "expert_confidences",
                "executed_action",
                "historical_fault_context",
            ],
            hidden_layers=[
                DenseLayer(64, "relu"),
                DenseLayer(32, "relu"),
                DenseLayer(16, "linear_embedding"),
                DenseLayer(32, "relu"),
                DenseLayer(64, "relu"),
            ],
            output_classes=[
                "sequence_embedding",
                "reconstruction_error",
                "cluster_id",
                "ranked_root_cause_candidates",
            ],
            output_activation="mixed",
            quantization="not_required_for_pi",
            max_latency_ms=1000,
            notes=[
                "PRD suggests 1D CNN autoencoder, LSTM autoencoder, or temporal convolutional autoencoder.",
                "Clustering can use DBSCAN, HDBSCAN, or K-Means.",
                "Similarity search should retrieve confirmed historical events.",
                "This is Pi/Jeston-side analysis, not ESP32 real-time inference.",
            ],
        ),
    }


def to_jsonable(specs: Dict[str, ModelArchitecture]) -> Dict[str, Dict]:
    data = {}
    for name, spec in specs.items():
        row = asdict(spec)
        row["input_dim"] = spec.input_dim
        row["output_dim"] = spec.output_dim
        data[name] = row
    return data


def write_summary(path: Path) -> None:
    path.write_text(json.dumps(to_jsonable(architectures()), indent=2, sort_keys=True) + "\n", encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show or write RoboMoE-Diag model architecture specs.")
    parser.add_argument("--summary", action="store_true", help="Write architecture_summary.json next to this file.")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("architecture_summary.json"))
    args = parser.parse_args()

    if args.summary:
        write_summary(args.output)
        print(f"wrote {args.output}")
    else:
        print(json.dumps(to_jsonable(architectures()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
