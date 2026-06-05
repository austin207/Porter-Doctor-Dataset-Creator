# Training Pipelines

Placeholder training pipeline folders for RoboMoE-Diag.

These scripts are planning scaffolds. They intentionally do not implement full
ML training yet. They document the expected pipeline steps from raw logs to
features, evaluation, and INT8 export.

Each model folder should eventually contain:

```text
build_features.py
train_model.py
evaluate_model.py
export_tflite_int8.py
```

Rules:

- Read raw CSV logs.
- Use event markers to assign labels.
- Build 1 second sliding-window features with 50 percent overlap.
- Split train, validation, and test sets by `run_id`.
- Train a baseline model for comparison.
- Train compact MLP architecture for embedded deployment.
- Export feature order, label map, normalization stats, and INT8 model.
- Do not implement embedded inference here.
