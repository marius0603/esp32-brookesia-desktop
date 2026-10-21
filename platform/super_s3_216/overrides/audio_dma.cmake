# Build local variants without modifying Component Manager's vendor sources.
function(s3_audio_source_override component relative needle replacement)
    idf_component_get_property(component_dir ${component} COMPONENT_DIR)
    idf_component_get_property(component_lib ${component} COMPONENT_LIB)
    set(original "${component_dir}/${relative}")
    file(READ "${original}" content)
    string(FIND "${content}" "${needle}" found)
    if(found EQUAL -1)
        message(FATAL_ERROR "S3 audio override no longer matches ${original}")
    endif()
    string(REPLACE "${needle}" "${replacement}" content "${content}")
    get_filename_component(basename "${relative}" NAME)
    get_filename_component(header_dir "${original}" DIRECTORY)
    set(output "${CMAKE_BINARY_DIR}/s3_audio_overrides/${basename}")
    file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/s3_audio_overrides")
    file(WRITE "${output}" "${content}")
    get_target_property(sources ${component_lib} SOURCES)
    set(filtered)
    set(removed 0)
    foreach(source IN LISTS sources)
        get_filename_component(source_name "${source}" NAME)
        if(source_name STREQUAL basename)
            math(EXPR removed "${removed}+1")
        else()
            list(APPEND filtered "${source}")
        endif()
    endforeach()
    if(NOT removed EQUAL 1)
        message(FATAL_ERROR "Expected one ${basename} in ${component}, found ${removed}")
    endif()
    set_property(TARGET ${component_lib} PROPERTY SOURCES "${filtered};${output}")
    target_include_directories(${component_lib} PRIVATE "${header_dir}")
endfunction()

# Keep six descriptors, reduce each frame buffer from 240 to 128 samples.
# At 16kHz this provides 48ms of DMA buffering with substantially lower RAM use.
s3_audio_source_override(espressif__esp_board_manager "peripherals/periph_i2s/periph_i2s.c"
    "chan_cfg.auto_clear = true;"
    "chan_cfg.auto_clear = true;\n    chan_cfg.dma_frame_num = 128;")

# A failed TX slot/DMA reconfiguration must never enable a channel whose
# descriptors were freed by the driver. Propagate both reconfigure/enable errors.
s3_audio_source_override(espressif__esp_codec_dev "platform/audio_codec_data_i2s.c"
    "ret = set_drv_fs(channel, true, bits_per_sample, i2s_data->clk_src, fs);\n        _i2s_drv_enable(paired, true, true);"
    "ret = set_drv_fs(channel, true, bits_per_sample, i2s_data->clk_src, fs);\n        if (ret != ESP_CODEC_DEV_OK) {\n            return ret;\n        }\n        ret = _i2s_drv_enable(paired, true, true);")
