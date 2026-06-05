# Router Dataset Builder

This folder builds the first MoE router dataset for Porter Doctor / RoboMoE-Diag.
It is Python tooling, not Zephyr firmware.

The router dataset is for expert routing only. It decides which subsystem expert
should inspect a telemetry window. It is not the final fault classifier.

## Inputs

The builder reads feature CSV files from:

```text
ai_ml/datasets/<expert_name>/features/*.csv
```

Expected useful input columns:

```csv
run_id,window_start_s,window_end_s,fault_label,fault_subsystem,severity
```

If a feature file uses `start_s`, `end_s`, or `elapsed_s`, the script will use
those as fallback window times.

## Output Columns

```csv
run_id,window_start_s,window_end_s,power_score,motor_score,driver_score,esp32_score,lighting_score,target_expert,fault_label,fault_subsystem,severity
```

## Usage

From the workspace root:

```powershell
python ai_ml/router_dataset_builder/build_router_dataset.py --dataset-root ai_ml/datasets --output-dir ai_ml/router_dataset_builder/output
```

Generated files:

```text
ai_ml/router_dataset_builder/output/router_dataset.csv
ai_ml/router_dataset_builder/output/train_runs.txt
ai_ml/router_dataset_builder/output/val_runs.txt
ai_ml/router_dataset_builder/output/test_runs.txt
```

Run splits are made by full `run_id`. The script does not randomly shuffle rows
across runs.

## Label Mapping

Edit:

```text
ai_ml/router_dataset_builder/config/router_labels.json
```

The first version uses rule-based mapping from `fault_label` to `target_expert`.
Later versions can replace the fixed scores with anomaly scores and expert
confidence outputs.

