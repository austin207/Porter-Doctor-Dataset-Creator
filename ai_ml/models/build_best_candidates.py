#!/usr/bin/env python3
"""Build locked best-candidate models with reports for ESP32 deployment."""

from __future__ import annotations

import argparse
import html
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

from common.training_utils import load_json, write_json


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path(sys.executable)
MODELS = [
    "power_expert",
    "motor_expert",
    "motor_driver_expert",
    "esp32_expert",
    "lighting_expert",
    "router",
    "anomaly_detector",
]
QUICK_MAX_COMBINATIONS = 8
QUICK_REPEATS = 1


def model_dir(model_name: str) -> Path:
    return ROOT / "ai_ml/models" / model_name


def config_path(model_name: str) -> Path:
    return model_dir(model_name) / "config.json"


def artifact_dir(model_name: str) -> Path:
    return model_dir(model_name) / "artifacts"


def best_candidate_dir(model_name: str) -> Path:
    return model_dir(model_name) / "best_candidate"


def run_command(args: List[str]) -> None:
    print(" ".join(args))
    completed = subprocess.run(args, cwd=ROOT)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def selected_models(requested: Iterable[str] | None) -> List[str]:
    requested_set = set(requested or [])
    if not requested_set:
        return MODELS
    unknown = sorted(requested_set - set(MODELS))
    if unknown:
        raise SystemExit(f"Unknown model(s): {', '.join(unknown)}")
    return [model for model in MODELS if model in requested_set]


def tuning_limits(args: argparse.Namespace) -> tuple[int | None, int | None, str]:
    if args.full:
        return args.max_combinations, args.repeats, "full"
    max_combinations = args.max_combinations if args.max_combinations is not None else QUICK_MAX_COMBINATIONS
    repeats = args.repeats if args.repeats is not None else QUICK_REPEATS
    return max_combinations, repeats, "quick"


def tune_model(model_name: str, max_combinations: int | None, repeats: int | None) -> None:
    args = [str(PYTHON), "ai_ml/models/tune_hyperparameters.py", "--model", model_name]
    if max_combinations is not None:
        args.extend(["--max-combinations", str(max_combinations)])
    if repeats is not None:
        args.extend(["--repeats", str(repeats)])
    run_command(args)


def apply_recommended_config(model_name: str) -> Dict:
    patch_path = artifact_dir(model_name) / "recommended_config_patch.json"
    if not patch_path.exists():
        raise SystemExit(f"Missing recommendation patch: {patch_path}. Run tuning first.")

    patch = load_json(patch_path)
    config_file = config_path(model_name)
    config = load_json(config_file)
    selected_fields = patch["recommended_fields"]
    config.update(selected_fields)
    config["architecture_locked"] = True
    config["architecture_lock_source"] = "ai_ml/models/build_best_candidates.py"
    config["architecture_locked_at_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    write_json(config_file, config)
    return selected_fields


def train_model(model_name: str) -> None:
    run_command([str(PYTHON), f"ai_ml/models/{model_name}/train.py"])


def evaluate_model(model_name: str) -> None:
    run_command([str(PYTHON), "ai_ml/models/evaluate_all_models.py", "--model", model_name])


def check_esp32() -> None:
    run_command([str(PYTHON), "ai_ml/models/check_esp32_feasibility.py"])


def copy_tree_contents(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)


def cleanup_after_success(model_name: str, keep_evaluation_outputs: bool = False) -> None:
    transient_files = [
        ROOT / "ai_ml/models/tuning_summary.json",
        ROOT / f"ai_ml/models/{model_name}_hyperparameter_candidates.csv",
    ]
    for path in transient_files:
        if path.exists():
            path.unlink()

    if not keep_evaluation_outputs:
        eval_dir = ROOT / "ai_ml/evaluation_outputs" / model_name
        if eval_dir.exists():
            shutil.rmtree(eval_dir)
        summary_path = ROOT / "ai_ml/evaluation_outputs/evaluation_summary.json"
        if summary_path.exists():
            summary_path.unlink()


def plot_cards(report_dir: Path) -> str:
    plots_dir = report_dir / "evaluation/plots"
    if not plots_dir.exists():
        return ""
    cards = []
    for plot in sorted(plots_dir.glob("*.png")):
        rel = plot.relative_to(report_dir).as_posix()
        title = plot.stem.replace("_", " ").title()
        cards.append(
            f'<figure class="plot"><img src="{html.escape(rel)}" alt="{html.escape(title)}">'
            f"<figcaption>{html.escape(title)}</figcaption></figure>"
        )
    return "\n".join(cards)


def read_optional_json(path: Path) -> Dict:
    return load_json(path) if path.exists() else {}


def create_html_report(model_name: str, selected_fields: Dict | None) -> None:
    report_dir = best_candidate_dir(model_name)
    report_dir.mkdir(parents=True, exist_ok=True)
    metrics = read_optional_json(report_dir / "artifacts/metrics.json")
    tuning = read_optional_json(report_dir / "artifacts/hyperparameter_tuning_results.json")
    evaluation = read_optional_json(report_dir / "evaluation/evaluation_report.json")
    feasibility = read_optional_json(ROOT / "ai_ml/evaluation_outputs/esp32_feasibility/esp32_feasibility_report.json")
    model_feasibility = {}
    for row in feasibility.get("models", []):
        if row.get("model_name") == model_name:
            model_feasibility = row
            break

    status = "PASS" if model_feasibility.get("fits_esp32") else "WARN"
    selected_fields = selected_fields or read_optional_json(report_dir / "artifacts/recommended_config_patch.json").get("recommended_fields", {})
    plot_html = plot_cards(report_dir)

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(model_name)} Best Candidate Report</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #f5f7fa; color: #18212f; }}
    header {{ background: #14213d; color: white; padding: 28px 36px; }}
    main {{ padding: 28px 36px; max-width: 1180px; margin: 0 auto; }}
    h1 {{ margin: 0 0 8px 0; }}
    h2 {{ margin-top: 34px; border-bottom: 1px solid #ccd4df; padding-bottom: 8px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }}
    .card {{ background: white; border: 1px solid #dbe2ea; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(20, 33, 61, 0.08); }}
    .label {{ font-size: 12px; color: #667085; text-transform: uppercase; letter-spacing: 0.04em; }}
    .value {{ font-size: 22px; font-weight: 700; margin-top: 6px; }}
    .pass {{ color: #157347; }}
    .warn {{ color: #b45309; }}
    pre {{ background: #101828; color: #e6edf3; padding: 14px; border-radius: 8px; overflow-x: auto; }}
    .plots {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px; }}
    figure.plot {{ background: white; border: 1px solid #dbe2ea; border-radius: 8px; padding: 12px; margin: 0; }}
    figure.plot img {{ width: 100%; height: auto; display: block; }}
    figcaption {{ font-size: 13px; color: #475467; margin-top: 8px; }}
    a {{ color: #175cd3; }}
  </style>
</head>
<body>
<header>
  <h1>{html.escape(model_name)} Best Candidate Report</h1>
  <div>Generated {datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}</div>
</header>
<main>
  <div class="grid">
    <section class="card"><div class="label">ESP32 Status</div><div class="value {'pass' if status == 'PASS' else 'warn'}">{status}</div></section>
    <section class="card"><div class="label">Parameters</div><div class="value">{metrics.get('parameter_count', model_feasibility.get('parameter_count', 'n/a'))}</div></section>
    <section class="card"><div class="label">INT8 TFLite Size</div><div class="value">{model_feasibility.get('int8_tflite_bytes', 'n/a')} B</div></section>
    <section class="card"><div class="label">Evaluation Rows</div><div class="value">{evaluation.get('rows', 'n/a')}</div></section>
    <section class="card"><div class="label">Eval Accuracy / MSE</div><div class="value">{evaluation.get('accuracy', evaluation.get('mean_reconstruction_error', 'n/a'))}</div></section>
    <section class="card"><div class="label">Best Embedded Score</div><div class="value">{tuning.get('best_embedded_score', 'n/a')}</div></section>
  </div>

  <h2>Locked Architecture</h2>
  <pre>{html.escape(str(selected_fields))}</pre>

  <h2>Tuning Result</h2>
  <pre>{html.escape(str(tuning))}</pre>

  <h2>ESP32 Feasibility</h2>
  <pre>{html.escape(str(model_feasibility))}</pre>

  <h2>Graphs</h2>
  <div class="plots">
    {plot_html}
  </div>

  <h2>Files</h2>
  <ul>
    <li><a href="selected_parameters.json">Selected parameter JSON</a></li>
    <li><a href="selected_parameters.yaml">Selected parameter YAML</a></li>
    <li><a href="artifacts/hyperparameter_candidates.csv">Candidate ranking CSV</a></li>
    <li><a href="artifacts/hyperparameter_tuning_results.json">Tuning JSON</a></li>
    <li><a href="artifacts/model_card.json">Model card</a></li>
    <li><a href="evaluation/predictions.csv">Predictions CSV</a></li>
    <li><a href="evaluation/model_summary.txt">Keras model summary</a></li>
  </ul>
</main>
</body>
</html>
"""
    (report_dir / "candidate_report.html").write_text(html_text, encoding="utf-8")


def write_selected_parameter_files(model_name: str, selected_fields: Dict | None) -> None:
    import yaml

    report_dir = best_candidate_dir(model_name)
    selected_fields = selected_fields or read_optional_json(report_dir / "artifacts/recommended_config_patch.json").get("recommended_fields", {})
    config = load_json(config_path(model_name))
    metrics = read_optional_json(report_dir / "artifacts/metrics.json")
    tuning = read_optional_json(report_dir / "artifacts/hyperparameter_tuning_results.json")
    payload = {
        "model_name": model_name,
        "config_path": str(config_path(model_name).relative_to(ROOT)),
        "selected_parameters": selected_fields,
        "locked_config_fields": {
            "hidden_layers": config.get("hidden_layers"),
            "learning_rate": config.get("learning_rate"),
            "batch_size": config.get("batch_size"),
            "epochs": config.get("epochs"),
            "architecture_locked": config.get("architecture_locked", False),
            "architecture_locked_at_utc": config.get("architecture_locked_at_utc"),
        },
        "candidate_selection": {
            "best_score": tuning.get("best_score"),
            "best_score_std": tuning.get("best_score_std"),
            "best_embedded_score": tuning.get("best_embedded_score"),
            "score_metric": tuning.get("score_metric"),
            "candidate_count": tuning.get("candidate_count"),
            "repeats": tuning.get("repeats"),
        },
        "esp32_feasibility": metrics.get("esp32_feasibility", {}),
    }
    write_json(report_dir / "selected_parameters.json", payload)
    (report_dir / "selected_parameters.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=True),
        encoding="ascii",
    )


def build_candidate(model_name: str, args: argparse.Namespace) -> None:
    selected_fields = None
    if not args.skip_tune:
        max_combinations, repeats, _mode = tuning_limits(args)
        tune_model(model_name, max_combinations, repeats)
    if not args.no_apply:
        selected_fields = apply_recommended_config(model_name)
        print(f"{model_name}: locked selected config {selected_fields}")
    if not args.skip_train:
        train_model(model_name)
    if not args.skip_evaluate:
        evaluate_model(model_name)
    check_esp32()

    report_dir = best_candidate_dir(model_name)
    if report_dir.exists():
        shutil.rmtree(report_dir)
    copy_tree_contents(artifact_dir(model_name), report_dir / "artifacts")
    copy_tree_contents(ROOT / "ai_ml/evaluation_outputs" / model_name, report_dir / "evaluation")
    copy_tree_contents(ROOT / "ai_ml/evaluation_outputs/esp32_feasibility", report_dir / "esp32_feasibility")
    write_selected_parameter_files(model_name, selected_fields)
    create_html_report(model_name, selected_fields)
    if not args.keep_intermediates:
        cleanup_after_success(model_name, keep_evaluation_outputs=args.keep_evaluation_outputs)
    print(f"{model_name}: wrote best candidate report to {report_dir / 'candidate_report.html'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Tune, lock, train, evaluate, and report best model candidates.")
    parser.add_argument("--model", action="append", help="Build only this model. Can be repeated.")
    parser.add_argument("--max-combinations", type=int, help="Override tuning max combinations.")
    parser.add_argument("--repeats", type=int, help="Override tuning repeats.")
    parser.add_argument("--full", action="store_true", help="Use YAML tuning defaults. Without this, builder uses a quick search by default.")
    parser.add_argument("--skip-tune", action="store_true")
    parser.add_argument("--no-apply", action="store_true", help="Do not lock recommended fields into config.json.")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--skip-evaluate", action="store_true")
    parser.add_argument("--keep-intermediates", action="store_true", help="Keep tuning summaries and temporary evaluation outputs.")
    parser.add_argument("--keep-evaluation-outputs", action="store_true", help="Keep ai_ml/evaluation_outputs/<model> after copying it into best_candidate.")
    args = parser.parse_args()

    models = selected_models(args.model)
    max_combinations, repeats, mode = tuning_limits(args)
    if args.skip_tune:
        print(f"selected models: {', '.join(models)}")
        print("tuning skipped")
    elif mode == "full":
        print(f"selected models: {', '.join(models)}")
        print("tuning mode: full YAML defaults")
    else:
        print(f"selected models: {', '.join(models)}")
        print(f"tuning mode: quick max_combinations={max_combinations} repeats={repeats}")
        print("use --full for the slower YAML search")

    for model_name in models:
        build_candidate(model_name, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
