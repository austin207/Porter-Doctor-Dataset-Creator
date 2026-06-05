from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a lightweight deployment manifest for a trained model.")
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--output", default=None, type=Path)
    args = parser.parse_args()

    artifact_dir = args.artifact_dir
    metrics_path = artifact_dir / "metrics.json"
    feature_path = artifact_dir / "feature_columns.json"
    if not metrics_path.exists() or not feature_path.exists():
        raise SystemExit("Train the model before exporting a manifest.")

    metrics = json.loads(metrics_path.read_text(encoding="ascii"))
    features = json.loads(feature_path.read_text(encoding="ascii"))
    manifest = {
        "model_name": metrics.get("model_name"),
        "model_type": metrics.get("model_type"),
        "feature_count": len(features.get("feature_columns", [])),
        "artifact_format": "joblib_offline_baseline",
        "embedded_export_status": "not_exported",
        "safety_note": "Do not deploy directly to safety-critical firmware without validation and embedded export.",
    }

    output = args.output or artifact_dir / "deployment_manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
