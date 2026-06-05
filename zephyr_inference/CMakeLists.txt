# Generated model sources are emitted into generated/.
# Include this file from a Zephyr app CMakeLists.txt after adding TFLite Micro.

zephyr_library_named(porter_zephyr_inference)
zephyr_library_include_directories(include generated)
zephyr_library_sources(
  src/porter_inference.c
  generated/power_expert_model_data.c
  generated/power_expert_metadata.c
  generated/power_expert_bundle.c
  generated/motor_expert_model_data.c
  generated/motor_expert_metadata.c
  generated/motor_expert_bundle.c
  generated/motor_driver_expert_model_data.c
  generated/motor_driver_expert_metadata.c
  generated/motor_driver_expert_bundle.c
  generated/esp32_expert_model_data.c
  generated/esp32_expert_metadata.c
  generated/esp32_expert_bundle.c
  generated/lighting_expert_model_data.c
  generated/lighting_expert_metadata.c
  generated/lighting_expert_bundle.c
  generated/router_model_data.c
  generated/router_metadata.c
  generated/router_bundle.c
)
