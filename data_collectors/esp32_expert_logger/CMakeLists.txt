cmake_minimum_required(VERSION 3.20.0)

execute_process(
    COMMAND python ${CMAKE_CURRENT_LIST_DIR}/../scripts/generate_zephyr_overlay.py
            --config ${CMAKE_CURRENT_LIST_DIR}/../hardware_config.json
            --expert esp32
            --out ${CMAKE_CURRENT_LIST_DIR}/boards/generated.overlay
    RESULT_VARIABLE OVERLAY_GEN_RESULT
)
if(NOT OVERLAY_GEN_RESULT EQUAL 0)
    message(FATAL_ERROR "Failed to generate esp32_expert_logger devicetree overlay")
endif()

set(DTC_OVERLAY_FILE boards/generated.overlay)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(esp32_expert_logger)

target_include_directories(app PRIVATE ../common)
target_sources(app PRIVATE
    src/main.c
    ../common/dataset_commands.c
    ../common/uart_line_parser.c
    ../common/csv_logger.c
)
