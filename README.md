# Porter Doctor

Repository: Porter-Doctor-Dataset-Creator

Porter Doctor is the dataset-generation and embedded fault-diagnosis workspace for RoboMoE-Diag.

## Goal

Build a modular robot fault diagnosis system using multiple expert datasets and expert models.

## Expert Folders

PORTER DOCTOR/
  power_expert_logger/
  motor_expert_logger/
  motor_driver_expert_logger/
  esp32_expert_logger/
  lighting_expert_logger/
  router_dataset_builder/

## Recommended Build Order

1. power_expert_logger
2. motor_expert_logger
3. motor_driver_expert_logger
4. esp32_expert_logger
5. lighting_expert_logger
6. router_dataset_builder

Start with the Power Expert because it only needs ESP32, INA226 and microSD.

## Local Zephyr Workspace

This repo is intended to be the Zephyr workspace root. From this folder:

```powershell
west init -l .
west update
west zephyr-export
python -m pip install -r zephyr/scripts/requirements.txt
west build -b esp32_devkitc_wroom power_expert_logger -d build/power_expert_logger
```

The `west.yml` manifest pulls Zephyr into this same `Porter Doctor` directory.
Downloaded Zephyr workspace folders are ignored by git.
