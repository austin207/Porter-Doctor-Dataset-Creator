# Dataset Tools

Small Python tools for working with Porter Doctor datasets.

## Merge Raw Runs

Each logger writes one raw CSV per run. Use `merge_raw_runs.py` to combine them.

Merge all experts into one wide CSV:

```powershell
python ai_ml/dataset_tools/merge_raw_runs.py --expert all
```

Output:

```text
ai_ml/datasets/merged/all_experts_raw_merged.csv
```

Merge one expert:

```powershell
python ai_ml/dataset_tools/merge_raw_runs.py --expert power_expert
```

Output:

```text
ai_ml/datasets/merged/power_expert_raw_merged.csv
```

Create one merged CSV per expert:

```powershell
python ai_ml/dataset_tools/merge_raw_runs.py --per-expert
```

The all-experts merged file uses the union of all expert columns. Columns that
do not apply to a row are left empty. A `source_file` column is added so every
merged row can be traced back to its original run file.

