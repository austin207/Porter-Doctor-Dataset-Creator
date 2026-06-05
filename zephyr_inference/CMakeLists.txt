# Generated model sources are emitted into generated/.
# Include this file from a Zephyr app CMakeLists.txt via add_subdirectory().
# Sources are added directly to 'app' so they are available at link time.
# (zephyr_library_named registers with ZEPHYR_LIBS too late when called after
# find_package(Zephyr), so the library would build but not link.)

target_sources(app PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/src/porter_inference.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/power_expert_model_data.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/power_expert_metadata.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/power_expert_bundle.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/motor_expert_model_data.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/motor_expert_metadata.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/motor_expert_bundle.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/motor_driver_expert_model_data.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/motor_driver_expert_metadata.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/motor_driver_expert_bundle.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/esp32_expert_model_data.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/esp32_expert_metadata.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/esp32_expert_bundle.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/lighting_expert_model_data.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/lighting_expert_metadata.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/lighting_expert_bundle.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/router_model_data.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/router_metadata.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/router_bundle.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/anomaly_detector_model_data.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/anomaly_detector_metadata.c
  ${CMAKE_CURRENT_SOURCE_DIR}/generated/anomaly_detector_bundle.c
)
target_include_directories(app PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
  ${CMAKE_CURRENT_SOURCE_DIR}/generated
)
