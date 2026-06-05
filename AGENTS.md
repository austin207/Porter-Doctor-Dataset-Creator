# Repository Guidelines

## Project Structure & Module Organization

This repo is the Porter Doctor / RoboMoE-Diag workspace. `data_collectors/`
contains Zephyr firmware loggers, shared C helpers, hardware configuration, and
overlay generation scripts. Each logger lives in
`data_collectors/<expert>_logger/` with `src/`, `boards/`, `CMakeLists.txt`,
`prj.conf`, and a README. `ai_ml/` contains sample datasets, merge tools,
router dataset tooling, baseline model code, and future training scaffolds.
`docs/` holds architecture notes. `zephyr/`, `modules/`, `bootloader/`, and
`tools/` are west-managed dependencies and should not be edited casually.

## Build, Test, and Development Commands

Initialize or refresh the local Zephyr workspace:

```powershell
.\init_local_west.ps1
west update
west zephyr-export
python -m pip install -r zephyr/scripts/requirements.txt
```

Build a logger through the helper:

```powershell
.\data_collectors\build_logger.ps1 -Expert power_expert_logger
```

Build directly with west:

```powershell
west build -b esp32_devkitc/esp32/procpu data_collectors/power_expert_logger -d build/power_expert_logger
```

Dataset utilities:

```powershell
python ai_ml/dataset_tools/merge_raw_runs.py --expert all
python ai_ml/router_dataset_builder/build_router_dataset.py
python ai_ml/models/train_all_baselines.py
```

## Coding Style & Naming Conventions

Use ASCII-only text. Keep board-specific pins in
`data_collectors/hardware_config.json` and generated Zephyr overlays, not in
portable `src/main.c`. Use Zephyr APIs for firmware. Prefer snake_case for C and
Python identifiers, lowercase folder names, and explicit expert names such as
`motor_driver_expert`.

## Testing Guidelines

For Python changes, run `python -m py_compile` on touched scripts and run the
relevant dataset tool. For firmware changes, run the matching `west build`.
Current ML training files under `ai_ml/training/` are scaffolds unless explicitly
implemented later.

## Commit & Pull Request Guidelines

Recent commits use short imperative messages, for example `organize workspace
and add baseline model training`. Keep commits focused. PRs should describe the
changed subsystem, commands run, hardware assumptions, and any safety impact.
Never add ML emergency-stop execution; ML may only request bounded actions.

## Security & Configuration Tips

Do not commit generated overlays, build outputs, `__pycache__`, or model
artifacts. Edit `data_collectors/hardware_config.json` for board and pin changes.
Do not add unsafe fault-generation code that can damage motors, drivers,
batteries, wiring, or lighting hardware.
