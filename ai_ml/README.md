# AI ML

Dataset examples and offline tooling for Porter Doctor / RoboMoE-Diag.

This folder contains:

```text
  datasets/
  dataset_tools/
  models/
  router_dataset_builder/
```

No embedded ML inference is implemented here yet. Current tooling is focused on:

- sample dataset layout
- merging raw run CSV files
- building the first rule-based MoE router dataset
- baseline training code for anomaly, router, and subsystem expert models

Merge all raw run files:

```powershell
python ai_ml/dataset_tools/merge_raw_runs.py --expert all
```

Build the router dataset:

```powershell
python ai_ml/router_dataset_builder/build_router_dataset.py
```

Train baseline models:

```powershell
python ai_ml/models/train_all_baselines.py
```

Train one model:

```powershell
python ai_ml/models/power_expert/train.py
python ai_ml/models/anomaly_detector/train.py
```
