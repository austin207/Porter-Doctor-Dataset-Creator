# Repository Guidelines

## Project Structure

This repo is the Porter Doctor / RoboMoE-Diag workspace.

`data_collectors/` contains Zephyr firmware dataset loggers, shared C helpers,
hardware configuration, and overlay generation scripts. Each logger lives in
`data_collectors/<expert>_logger/` with `src/`, `boards/`, `CMakeLists.txt`,
`prj.conf`, and a README.

`ai_ml/` contains sample datasets, merge tools, router dataset tooling,
TensorFlow/Keras model training, inference wrappers, evaluation/report
generation, hyperparameter tuning, ESP32 feasibility checks, and Zephyr export
scripts.

`zephyr_inference/` is the standalone embedded inference export area. It stays
outside `data_collectors/`. Its `generated/` folder contains C arrays converted
from INT8 `.tflite` files and is ignored by git. `zephyr_inference/smoke_app/`
is a small Zephyr build target that compiles all generated model C arrays and
metadata for hardware smoke testing.

`docs/` holds architecture notes. `zephyr/`, `modules/`, `bootloader/`, and
`tools/` are west-managed dependencies and should not be edited casually.

## Core Commands

Run commands from the repository root:

```powershell
cd "C:\Users\austi\OneDrive\Desktop\career\VirtusCo (Startup)\Porter Doctor"
```

Create the Python environment:

```powershell
python -m pip install --user uv
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
```

Initialize or refresh Zephyr:

```powershell
.\init_local_west.ps1
west update
west zephyr-export
python -m pip install -r zephyr\scripts\requirements.txt
```

Build firmware loggers:

```powershell
.\data_collectors\build_logger.ps1 -Expert power_expert_logger
.\data_collectors\build_logger.ps1 -Expert motor_expert_logger
.\data_collectors\build_logger.ps1 -Expert motor_driver_expert_logger
.\data_collectors\build_logger.ps1 -Expert esp32_expert_logger
.\data_collectors\build_logger.ps1 -Expert lighting_expert_logger
```

Build and flash one logger:

```powershell
.\data_collectors\build_logger.ps1 -Expert power_expert_logger -Flash
```

Build directly with west:

```powershell
west build -b esp32_devkitc/esp32/procpu data_collectors/power_expert_logger -d build/power_expert_logger
```

Dataset utilities:

```powershell
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --expert all
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --per-expert
.\.venv\Scripts\python.exe ai_ml\router_dataset_builder\build_router_dataset.py
```

Train all current TensorFlow models:

```powershell
powershell -ExecutionPolicy Bypass -File .\train.ps1 -Python .\.venv\Scripts\python.exe
```

Train one model:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\power_expert\train.py
```

Tune and build best candidates:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\tune_hyperparameters.py --model power_expert --max-combinations 4 --repeats 1
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --model power_expert
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --full
```

Evaluate and generate graphs:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\evaluate_all_models.py
.\.venv\Scripts\python.exe ai_ml\models\evaluate_all_models.py --model power_expert
```

Run Python inference:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\power_expert\infer.py
.\.venv\Scripts\python.exe ai_ml\models\power_expert\infer.py --input ai_ml\datasets\merged\power_expert_raw_merged.csv --limit 5 --top-k 3
```

Check ESP32 feasibility:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\check_esp32_feasibility.py
```

Export TFLite models to Zephyr C arrays:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --model power_expert
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --source artifacts
```

Build the Zephyr inference smoke app:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py
west build -b esp32_devkitc/esp32/procpu zephyr_inference/smoke_app -d build/zephyr_inference_smoke
west flash -d build/zephyr_inference_smoke
```

If `west` fails with `ModuleNotFoundError: colorama`, repair the system Python
environment used by `west.exe`:

```powershell
python -m pip install colorama
```

## Coding Style

Use ASCII-only text. Prefer snake_case for C and Python identifiers, lowercase
folder names, and explicit expert names such as `motor_driver_expert`.

Keep board-specific pins in `data_collectors/hardware_config.json` and generated
Zephyr overlays, not in portable `src/main.c`. Use Zephyr APIs for firmware.
Do not hand-edit `data_collectors/<expert_logger>/boards/generated.overlay`.

For generated Zephyr inference code, the Python exporter must convert
`model_int8.tflite` into C byte arrays in
`zephyr_inference/generated/<model>_model_data.c`. Global C initializers must
use compile-time constants, preferably generated `#define` values, not `extern
const` variables.

## Testing Guidelines

For Python changes, run `py_compile` on touched scripts:

```powershell
.\.venv\Scripts\python.exe -m py_compile ai_ml\models\export_zephyr_inference.py
```

For dataset changes, run the relevant merge/router command:

```powershell
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --expert all
.\.venv\Scripts\python.exe ai_ml\router_dataset_builder\build_router_dataset.py
```

For model changes, run a focused train/evaluate/export path:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\power_expert\train.py
.\.venv\Scripts\python.exe ai_ml\models\evaluate_all_models.py --model power_expert
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --model power_expert
```

For firmware logger changes, run the matching `west build` or
`data_collectors/build_logger.ps1` command. For Zephyr inference export changes,
run:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py
west build -b esp32_devkitc/esp32/procpu zephyr_inference/smoke_app -d build/zephyr_inference_smoke
```

## Generated Files And Git Hygiene

Do not commit generated overlays, build outputs, Python caches, model artifacts,
evaluation outputs, best-candidate packages, or generated Zephyr model arrays.
Ignored/generated paths include:

```text
.venv/
.west/
zephyr/
modules/
bootloader/
tools/
build/
**/boards/generated.overlay
**/artifacts/
**/best_candidate/
ai_ml/evaluation_outputs/
ai_ml/models/tuning_summary.json
ai_ml/models/*_hyperparameter_candidates.csv
zephyr_inference/generated/
__pycache__/
```

Clean Python caches when needed:

```powershell
Get-ChildItem ai_ml,data_collectors -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

## Commit And PR Guidance

Use short imperative commit messages, for example `add Zephyr inference export
smoke app`. Keep commits focused. PRs should describe the changed subsystem,
commands run, hardware assumptions, generated outputs, and safety impact.

## Safety And Security

Never add unsafe fault-generation code that can damage motors, motor drivers,
batteries, wiring, or lighting hardware. Never add ML emergency-stop execution.
ML may only request bounded actions for later firmware handling.
