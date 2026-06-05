cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(porter_zephyr_inference_smoke)

add_subdirectory(.. ${CMAKE_CURRENT_BINARY_DIR}/porter_zephyr_inference)
target_sources(app PRIVATE src/main.c)
