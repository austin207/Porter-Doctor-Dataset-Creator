#!/usr/bin/env python3
"""Evaluate all TensorFlow models and write batch reports plus plots."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

sys.path.append(str(Path(__file__).resolve().parent / "common"))
from inference_utils import MODEL_CONFIGS, default_input_csv, predict_dataframe, repo_path  # noqa: E402
from training_utils import load_json, require_tensorflow_deps, write_json  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER_MODELS = ["power_expert", "motor_expert", "motor_driver_expert", "esp32_expert", "lighting_expert", "router"]
ANOMALY_MODELS = ["anomaly_detector"]


def write_csv(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="ascii", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_bar(path: Path, labels: List[str], values: List[float], title: str, ylabel: str) -> None:
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig_width = max(7.0, len(labels) * 0.9)
    fig, ax = plt.subplots(figsize=(fig_width, 4.5))
    ax.bar(labels, values, color="#3478b8")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_histogram(path: Path, values: List[float], title: str, xlabel: str) -> None:
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    ax.hist(values, bins=min(20, max(5, len(values) // 3)), color="#2d8f6f", edgecolor="#1f1f1f")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Rows")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_confusion_matrix(path: Path, labels: List[str], matrix: List[List[int]], title: str) -> None:
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig_size = max(6.0, len(labels) * 0.9)
    fig, ax = plt.subplots(figsize=(fig_size, fig_size))
    image = ax.imshow(matrix, cmap="Blues")
    ax.set_title(title)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_xticks(range(len(labels)), labels=labels, rotation=35, ha="right")
    ax.set_yticks(range(len(labels)), labels=labels)
    for row_index, row in enumerate(matrix):
        for col_index, value in enumerate(row):
            ax.text(col_index, row_index, str(value), ha="center", va="center", color="#111111")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_layer_architecture(path: Path, layer_rows: List[Dict], title: str) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, Rectangle

    path.parent.mkdir(parents=True, exist_ok=True)
    height = max(5.0, len(layer_rows) * 1.05)
    fig, ax = plt.subplots(figsize=(8.5, height))
    ax.set_title(title)
    ax.axis("off")

    y_positions = list(reversed(range(len(layer_rows))))
    for row, y_pos in zip(layer_rows, y_positions):
        rect = Rectangle((0.18, y_pos - 0.28), 0.64, 0.56, facecolor="#edf4fb", edgecolor="#2f5f8f", linewidth=1.2)
        ax.add_patch(rect)
        label = f"{row['layer']}\n{row['type']} | params={row['params']}"
        ax.text(0.5, y_pos, label, ha="center", va="center", fontsize=9)
        if y_pos > min(y_positions):
            arrow = FancyArrowPatch((0.5, y_pos - 0.30), (0.5, y_pos - 0.70), arrowstyle="->", mutation_scale=12, color="#333333")
            ax.add_patch(arrow)

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.8, len(layer_rows) - 0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_model_summary(model_name: str, output_dir: Path) -> None:
    import tensorflow as tf

    config = load_json(MODEL_CONFIGS[model_name])
    artifact_dir = repo_path(config["artifact_dir"])
    model_path = artifact_dir / "model_float32.keras"
    model = tf.keras.models.load_model(model_path, compile=False)

    lines: List[str] = []
    model.summary(print_fn=lines.append)
    (output_dir / "model_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    layer_rows = []
    for layer in model.layers:
        layer_rows.append(
            {
                "layer": layer.name,
                "type": layer.__class__.__name__,
                "output_shape": str(getattr(layer, "output_shape", "")),
                "params": int(layer.count_params()),
            }
        )
    write_csv(output_dir / "layer_table.csv", layer_rows)
    plot_bar(
        output_dir / "plots/layer_parameter_counts.png",
        [row["layer"] for row in layer_rows],
        [row["params"] for row in layer_rows],
        f"{model_name} layer parameter counts",
        "Parameters",
    )
    plot_layer_architecture(output_dir / "plots/model_architecture.png", layer_rows, f"{model_name} model architecture")


def classifier_report(model_name: str, output_root: Path) -> Dict:
    rows = predict_dataframe(model_name, default_input_csv(model_name))
    output_dir = output_root / model_name
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "predictions.csv", rows)
    write_model_summary(model_name, output_dir)

    true_labels = [str(row["true_label"]) for row in rows]
    pred_labels = [str(row["predicted_label"]) for row in rows]
    labels = sorted(set(true_labels) | set(pred_labels))
    label_index = {label: index for index, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]
    for true_label, pred_label in zip(true_labels, pred_labels):
        matrix[label_index[true_label]][label_index[pred_label]] += 1

    correct = sum(1 for true_label, pred_label in zip(true_labels, pred_labels) if true_label == pred_label)
    accuracy = correct / len(rows) if rows else 0.0
    plot_confusion_matrix(output_dir / "plots/confusion_matrix.png", labels, matrix, f"{model_name} confusion matrix")
    plot_histogram(
        output_dir / "plots/fault_confidence_histogram.png",
        [float(row["fault_confidence"]) for row in rows],
        f"{model_name} fault confidence",
        "Confidence",
    )

    true_counts = [true_labels.count(label) for label in labels]
    pred_counts = [pred_labels.count(label) for label in labels]
    plot_bar(output_dir / "plots/true_class_distribution.png", labels, true_counts, f"{model_name} true class distribution", "Rows")
    plot_bar(output_dir / "plots/predicted_class_distribution.png", labels, pred_counts, f"{model_name} predicted class distribution", "Rows")

    action_labels = sorted(set(str(row["predicted_action"]) for row in rows))
    action_counts = [sum(1 for row in rows if str(row["predicted_action"]) == label) for label in action_labels]
    plot_bar(output_dir / "plots/predicted_action_distribution.png", action_labels, action_counts, f"{model_name} action distribution", "Rows")

    report = {
        "model_name": model_name,
        "mode": "classifier",
        "rows": len(rows),
        "accuracy": accuracy,
        "output_dir": str(output_dir),
    }
    write_json(output_dir / "evaluation_report.json", report)
    return report


def anomaly_report(model_name: str, output_root: Path) -> Dict:
    rows = predict_dataframe(model_name, default_input_csv(model_name))
    output_dir = output_root / model_name
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "predictions.csv", rows)
    write_model_summary(model_name, output_dir)

    errors = [float(row["reconstruction_error"]) for row in rows]
    anomalies = [int(row["predicted_anomaly"]) for row in rows]
    plot_histogram(output_dir / "plots/reconstruction_error_histogram.png", errors, f"{model_name} reconstruction error", "MSE")
    plot_bar(
        output_dir / "plots/anomaly_decision_counts.png",
        ["normal", "anomaly"],
        [anomalies.count(0), anomalies.count(1)],
        f"{model_name} anomaly decisions",
        "Rows",
    )

    report = {
        "model_name": model_name,
        "mode": "autoencoder",
        "rows": len(rows),
        "mean_reconstruction_error": sum(errors) / len(errors) if errors else 0.0,
        "predicted_anomalies": sum(anomalies),
        "output_dir": str(output_dir),
    }
    write_json(output_dir / "evaluation_report.json", report)
    return report


def write_summary_plots(output_root: Path, reports: List[Dict]) -> None:
    classifier_reports = [report for report in reports if report["mode"] == "classifier"]
    if classifier_reports:
        plot_bar(
            output_root / "plots/classifier_accuracy_summary.png",
            [report["model_name"] for report in classifier_reports],
            [float(report["accuracy"]) for report in classifier_reports],
            "Classifier accuracy summary",
            "Accuracy",
        )
    anomaly_reports = [report for report in reports if report["mode"] == "autoencoder"]
    if anomaly_reports:
        plot_bar(
            output_root / "plots/anomaly_error_summary.png",
            [report["model_name"] for report in anomaly_reports],
            [float(report["mean_reconstruction_error"]) for report in anomaly_reports],
            "Anomaly reconstruction error summary",
            "Mean MSE",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate all trained TensorFlow models and write plots.")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "ai_ml/evaluation_outputs")
    parser.add_argument("--model", action="append", help="Evaluate only this model. Can be repeated.")
    args = parser.parse_args()

    require_tensorflow_deps()
    output_root = repo_path(args.output_dir)
    selected = set(args.model or [])
    reports: List[Dict] = []

    for model_name in CLASSIFIER_MODELS:
        if selected and model_name not in selected:
            continue
        reports.append(classifier_report(model_name, output_root))
        print(f"{model_name}: wrote evaluation batch to {output_root / model_name}")

    for model_name in ANOMALY_MODELS:
        if selected and model_name not in selected:
            continue
        reports.append(anomaly_report(model_name, output_root))
        print(f"{model_name}: wrote evaluation batch to {output_root / model_name}")

    if selected and not reports:
        raise SystemExit(f"No models matched: {', '.join(sorted(selected))}")

    write_json(output_root / "evaluation_summary.json", {"reports": reports})
    write_summary_plots(output_root, reports)
    print(f"wrote evaluation summary to {output_root / 'evaluation_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
