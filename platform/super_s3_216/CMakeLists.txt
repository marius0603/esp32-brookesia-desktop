# The following lines of boilerplate have to be in your project's CMakeLists
# in this exact order for cmake to work correctly

# Force Ninja to use response files to completely solve the 32KB Windows command line length limit
if("${CMAKE_GENERATOR}" MATCHES "Ninja")
    set(CMAKE_NINJA_FORCE_RESPONSE_FILE 1 CACHE INTERNAL "")
endif()

cmake_minimum_required(VERSION 3.16)

option(CCACHE_ENABLE "Use ccache to accelerate repeat ESP-IDF builds" ON)

set(PROJECT_VER "0.8.3-s3.31")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)

# Work around esp-idf-configdep mapping CONFIG_ESP_LVGL_ADAPTER_PARTIAL_AUX_IMG_CACHE
# to a Windows-invalid path containing the reserved device name "aux".
# Only force this off on Windows: elsewhere it makes idf.py's default
# `-DCONFIGDEP_ENABLE=True` permanently disagree with the forced cache value, which
# makes idf.py re-run CMake configure on every build/flash (~24s each time).
if(CMAKE_HOST_WIN32)
    set(CONFIGDEP_ENABLE 0 CACHE BOOL "Disable esp-idf-configdep for Windows AUX path compatibility" FORCE)
endif()

project(brookesia_s3_216)

include(${CMAKE_CURRENT_LIST_DIR}/overrides/audio_dma.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/overrides/esp_sr_sd.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/overrides/i2s_peer.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/overrides/lvgl_rle.cmake)

# Temporary workaround for `espressif__mcp-c-sdk` stringop-truncation warning
idf_build_set_property(COMPILE_OPTIONS -Wno-error=stringop-truncation APPEND)

brookesia_system_super_apply_compile_policy()

# Keep the service framework small, but optimize the software rasterizer and
# font engine for speed. A global -O2 build is too large for this 8 MB PSRAM S3.
foreach(render_component lvgl__lvgl brookesia_gui_lvgl)
    idf_component_get_property(render_lib ${render_component} COMPONENT_LIB)
    target_compile_options(${render_lib} PRIVATE -O2)
endforeach()
target_compile_options(freetype PRIVATE -O2)

# esp_xiaozhi 0.1.2 uses this bool in C expressions, where disabled Kconfig
# symbols are otherwise undefined. Keep its task stack internal on this board.
if(NOT CONFIG_XIAOZHI_STACK_IN_PSRAM)
    idf_component_get_property(xiaozhi_lib espressif__esp_xiaozhi COMPONENT_LIB)
    target_compile_definitions(${xiaozhi_lib} PRIVATE CONFIG_XIAOZHI_STACK_IN_PSRAM=0)
endif()

# ESP-SR static libraries print directly; silence only their worker console so USB JSON remains framed.
target_link_options(${CMAKE_PROJECT_NAME}.elf PRIVATE "-Wl,--wrap=printf,--wrap=puts")
