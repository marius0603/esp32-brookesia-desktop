cmake_minimum_required(VERSION 3.16)
set(PROJECT_VER "0.2.1-app-check")
set(COMPONENTS main esp_psram)
set(EXTRA_COMPONENT_DIRS
    "${CMAKE_CURRENT_LIST_DIR}/../components/codex_quota_app"
    "${CMAKE_CURRENT_LIST_DIR}/../../vendor/ESP32-S3-Touch-AMOLED-2.16-main/examples/esp-idf/03_esp-brookesia/components/brookesia_core"
)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(codex_quota_brookesia_compile_check)
