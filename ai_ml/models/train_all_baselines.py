#!/usr/bin/env python3
"""Train all baseline models that have sample data available."""

from __future__ import annotations

from pathlib import Path

from common.training_utils import train_anomaly_detector, train_classifier


ROOT = Path(__file__).resolve().parent

CLASSIFIER_CONFIGS = [
    ROOT / "power_expert" / "config.json",
    ROOT / "motor_expert" / "config.json",
    ROOT / "motor_driver_expert" / "config.json",
    ROOT / "esp32_expert" / "config.json",
    ROOT / "lighting_expert" / "config.json",
]


def main() -> int:
    for config in CLASSIFIER_CONFIGS:
        train_classifier(config)
    train_anomaly_detector(ROOT / "anomaly_detector" / "config.json")
    print("baseline training complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
